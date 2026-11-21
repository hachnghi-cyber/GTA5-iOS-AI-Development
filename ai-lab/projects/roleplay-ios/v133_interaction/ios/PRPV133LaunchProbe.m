// GTA V iOS v13.3 — safe startup diagnostics, no game/network hooks.
// This initializer runs ONLY if the app's Mach-O explicitly loads the dylib.
// It proves dylib load and exact GTA5 UUID; does not prove Police RP works.
#import <Foundation/Foundation.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <stdio.h>
#include <string.h>
#include "PRPV133AuthorityClient.h"

void prp_start_tls_probe(NSString *folder);

#define PRP_EXPECTED_UUID "EB122C35-96F4-307F-91C3-A2255DD9C685"

static NSString *prp_uuid_of_main_image(void) {
    const struct mach_header *head = _dyld_get_image_header(0);
    if (!head || head->magic != MH_MAGIC_64 ||
        head->cputype != CPU_TYPE_ARM64) return nil;
    const struct mach_header_64 *h = (const struct mach_header_64 *)head;
    if (h->sizeofcmds > 1024 * 1024 || h->ncmds > 4096) return nil;
    const uint8_t *ptr = (const uint8_t *)h + sizeof(*h);
    const uint8_t *end = ptr + h->sizeofcmds;
    for (uint32_t i=0; i<h->ncmds; ++i) {
        if ((size_t)(end - ptr) < sizeof(struct load_command)) return nil;
        const struct load_command *cmd = (const struct load_command *)ptr;
        if (cmd->cmdsize < sizeof(*cmd) || cmd->cmdsize > (size_t)(end - ptr)) return nil;
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

__attribute__((constructor))
static void prp_phase8_launch_probe(void) {
    @autoreleasepool {
        NSString *uuid = prp_uuid_of_main_image();
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
        NSString *documents = [NSHomeDirectory() stringByAppendingPathComponent:@"Documents"];
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
