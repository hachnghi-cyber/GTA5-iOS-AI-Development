// Startup routing for the v13.3 diagnostic and the R85 private account panel.
#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <stdio.h>
#include <string.h>
#include "PRPV133AuthorityClient.h"

void prp_start_tls_probe(NSString *folder);

#define PRP_EXPECTED_UUID "EB122C35-96F4-307F-91C3-A2255DD9C685"

static NSString *prp_image_uuid(const struct mach_header *head, size_t available) {
    if (!head || available < sizeof(struct mach_header_64) || head->magic != MH_MAGIC_64 ||
        head->cputype != CPU_TYPE_ARM64 || head->filetype != MH_EXECUTE) return nil;
    const struct mach_header_64 *h = (const struct mach_header_64 *)head;
    if (h->sizeofcmds > available - sizeof(*h) || h->sizeofcmds > 1024 * 1024 || h->ncmds > 4096) return nil;
    const uint8_t *ptr = (const uint8_t *)h + sizeof(*h);
    const uint8_t *end = ptr + h->sizeofcmds;
    for (uint32_t i=0; i<h->ncmds; ++i) {
        if ((size_t)(end - ptr) < sizeof(struct load_command)) return nil;
        const struct load_command *cmd = (const struct load_command *)ptr;
        if (cmd->cmdsize < sizeof(*cmd) || (cmd->cmdsize & 7) || cmd->cmdsize > (size_t)(end - ptr)) return nil;
        if (cmd->cmd == LC_UUID && cmd->cmdsize >= sizeof(struct uuid_command)) {
            const struct uuid_command *u = (const struct uuid_command *)ptr;
            const uint8_t *v = u->uuid;
            return [NSString stringWithFormat:
                    @"%02X%02X%02X%02X-%02X%02X-%02X%02X-%02X%02X-%02X%02X%02X%02X%02X%02X",
                    v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],
                    v[8],v[9],v[10],v[11],v[12],v[13],v[14],v[15]];
        }
        ptr += cmd->cmdsize;
    }
    return nil;
}

// Check the guest executable via NSBundle so a container host's dyld image 0
// cannot identify a different GTA build. The patrol page survives re-signing.
static BOOL prp_is_r85_account_host(void) {
    NSURL *url = NSBundle.mainBundle.executableURL;
    if (![url.lastPathComponent isEqualToString:@"GTA5"]) return NO;
    NSFileHandle *file = [NSFileHandle fileHandleForReadingFromURL:url error:NULL];
    if (!file) return NO;
    NSData *prefix = [file readDataUpToLength:0x4000 error:NULL];
    [file closeAndReturnError:NULL];
    if (prefix.length != 0x4000 ||
        ![prp_image_uuid(prefix.bytes, prefix.length) isEqualToString:@"DC32A27A-E407-320F-8F52-76515044B1A9"])
        return NO;
    uint8_t digest[CC_SHA256_DIGEST_LENGTH];
    const uint8_t expected[CC_SHA256_DIGEST_LENGTH] = {
        0x88, 0xD5, 0xF2, 0xC6, 0x33, 0x33, 0xF0, 0x3E, 0x40, 0x2F, 0x17, 0x77, 0x58, 0xEB, 0x41, 0xB0,
        0xCA, 0x9F, 0x9D, 0x28, 0xAA, 0x65, 0x3B, 0x7C, 0xE0, 0xFA, 0x27, 0x81, 0xFA, 0x5D, 0xED, 0x75
    };
    CC_SHA256((const uint8_t *)prefix.bytes + 0x3000, 0x1000, digest);
    return memcmp(digest, expected, sizeof expected) == 0;
}

__attribute__((constructor))
static void prp_phase8_launch_probe(void) {
    @autoreleasepool {
        NSString *documents = [NSHomeDirectory() stringByAppendingPathComponent:@"Documents"];
        if (prp_is_r85_account_host()) {
            prp_start_r85_account_panel(documents);
            return;
        }
        NSString *uuid = prp_image_uuid(_dyld_get_image_header(0), SIZE_MAX);
        BOOL exact = uuid && [uuid isEqualToString:@PRP_EXPECTED_UUID];
        NSString *entry = [NSString stringWithFormat:
            @"schema=prp-v133-launch-probe-v1\n"
             "phase=launch\n"
             "source_revision=tls-probe-opt-in\n"
             "gta5_uuid=%@\n"
             "expected_uuid=%@\n"
             "gta5_uuid_matches=%d\n"
             "engine_game_thread_verified=0\n"
             "authenticated_network_sender_verified=0\n"
             "rp_network_enabled=0\n"
             "cuff_or_escort_enabled=0\n",
             uuid ?: @"UNKNOWN", @PRP_EXPECTED_UUID, exact ? 1 : 0];
        NSLog(@"[PRP_V133_PHASE8] %@",entry);
        const char *msg = "[PRP_V133_PHASE8] startup diagnostic executed (NO GAMEPLAY HOOKS)\n";
        fwrite(msg, 1, strlen(msg), stderr);
        // Never put private networking identifiers or a token in logs.
        // Best effort only: Documents may be inaccessible without File Sharing.
        NSString *destination = [documents stringByAppendingPathComponent:@"PoliceRP-v13.3-Phase8.txt"];
        NSError *error = nil;
        [[NSFileManager defaultManager] createDirectoryAtPath:documents
                                  withIntermediateDirectories:YES
                                                   attributes:nil error:&error];
        if (!error) {
            NSString *result = [NSString stringWithFormat:@"time=%@\n%@",
                           [NSDate date], entry];
            [result writeToFile:destination atomically:YES
                       encoding:NSUTF8StringEncoding error:&error];
        }
        if (error) NSLog(@"[PRP_V133_PHASE8] file write unavailable; see device console");
        if (exact) {
            prp_start_tls_probe(documents);
            prp_start_authority_client(documents);
        }
    }
}
