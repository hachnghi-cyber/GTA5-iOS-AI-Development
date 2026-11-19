// Optional native iPhone-to-host diagnostic. No game callback or mailbox binding.
#import <Foundation/Foundation.h>
#import <Network/Network.h>
#import <Security/Security.h>
#import <Security/SecProtocolMetadata.h>
#import <Security/SecProtocolOptions.h>
#import <CommonCrypto/CommonDigest.h>
#include <arpa/inet.h>
#include <string.h>
#include "rp_v133_wire.h"
#include "PRPV133TLSCommon.h"

static const char PRP_ALPN[] = "prp3-pair/1";
static NSString *const PRP_CONFIG = @"PRP3TLS-Probe-PRIVATE.json";
static NSString *const PRP_LOG = @"PoliceRP-v13.3-TLS-Probe.txt";

typedef struct {
    uint64_t local, peer, session, epoch;
} prp_pairing;

bool prp_parse_id(id value, uint64_t *out) {
    if (![value isKindOfClass:[NSString class]] || [value length] == 0 || [value length] > 20)
        return false;
    uint64_t n = 0;
    for (NSUInteger i = 0; i < [value length]; ++i) {
        unichar ch = [value characterAtIndex:i];
        if (ch < '0' || ch > '9' || n > (UINT64_MAX - (ch - '0')) / 10u)
            return false;
        n = n * 10u + (ch - '0');
    }
    *out = n;
    return n != 0;
}

bool prp_is_local_ip(NSString *host) {
    struct in_addr address;
    if (![host isKindOfClass:[NSString class]] || host.length > 15 ||
        strlen(host.UTF8String) != host.length || inet_pton(AF_INET, host.UTF8String, &address) != 1)
        return false;
    uint32_t ip = ntohl(address.s_addr);
    return (ip >> 24) == 10u || (ip >> 20) == 0xac1u || (ip >> 16) == 0xc0a8u;
}

NSData *prp_b64(NSDictionary *config, NSString *key, NSUInteger limit) {
    id value = config[key];
    if (![value isKindOfClass:[NSString class]] || [value length] > 2 * limit)
        return nil;
    NSData *data = [[NSData alloc] initWithBase64EncodedString:value options:0];
    return data.length > 0 && data.length <= limit ? data : nil;
}

sec_identity_t prp_import_identity(NSData *data, NSString *password) {
    if (!data || ![password isKindOfClass:[NSString class]] || password.length < 24 ||
        password.length > 96) return nil;
    CFArrayRef raw = NULL;
    if (SecPKCS12Import((__bridge CFDataRef)data, (__bridge CFDictionaryRef)@{
        (__bridge NSString *)kSecImportExportPassphrase: password
    }, &raw) != errSecSuccess) {
        if (raw) CFRelease(raw);
        return nil;
    }
    NSArray *items = CFBridgingRelease(raw);
    if (items.count != 1) return nil;
    SecIdentityRef identity = (__bridge SecIdentityRef)items.firstObject[(__bridge NSString *)kSecImportItemIdentity];
    return identity ? sec_identity_create(identity) : nil;
}

bool prp_verify_trust(sec_trust_t trust, NSString *hostname, NSArray *anchors, NSData *pin) {
    SecTrustRef ref = sec_trust_copy_ref(trust);
    if (!ref) return false;
    SecPolicyRef policy = SecPolicyCreateSSL(true, (__bridge CFStringRef)hostname);
    bool passed = policy && SecTrustSetPolicies(ref, policy) == errSecSuccess &&
        SecTrustSetAnchorCertificates(ref, (__bridge CFArrayRef)anchors) == errSecSuccess &&
        SecTrustSetAnchorCertificatesOnly(ref, true) == errSecSuccess &&
        SecTrustSetNetworkFetchAllowed(ref, false) == errSecSuccess &&
        SecTrustEvaluateWithError(ref, NULL);
    if (passed) {
        NSArray *certs = CFBridgingRelease(SecTrustCopyCertificateChain(ref));
        SecCertificateRef leaf = (__bridge SecCertificateRef)certs.firstObject;
        NSData *data = leaf ? CFBridgingRelease(SecCertificateCopyData(leaf)) : nil;
        passed = data.length > 0 && data.length <= 16384;
        if (passed) {
            uint8_t hash[CC_SHA256_DIGEST_LENGTH];
            CC_SHA256(data.bytes, (CC_LONG)data.length, hash);
            passed = [pin isEqualToData:[NSData dataWithBytes:hash length:sizeof hash]];
        }
    }
    if (policy) CFRelease(policy);
    CFRelease(ref);
    return passed;
}

static void prp_report(NSString *folder, NSString *result, bool pinned) {
    NSString *body = [NSString stringWithFormat:
        @"time=%@\nschema=prp3-tls-probe-v1\nresult=%@\npaired_tls_verified=%d\n"
         "engine_sender_mapping_verified=0\ngameplay_rp_enabled=0\n",
         [NSDate date], result, pinned ? 1 : 0];
    [body writeToFile:[folder stringByAppendingPathComponent:PRP_LOG]
           atomically:YES encoding:NSUTF8StringEncoding error:NULL];
    NSLog(@"[PRP3_TLS_PROBE] %@ (diagnostic only)", result);
}

static NSData *prp_hello(prp_pairing ids, bool incoming) {
    uint8_t bytes[40] = "PRP3TLS1";
    uint64_t values[] = {incoming ? ids.peer : ids.local, incoming ? ids.local : ids.peer,
                         ids.session, ids.epoch};
    for (size_t i = 0; i < 4; ++i)
        for (size_t n = 0; n < 8; ++n)
            bytes[8 + 8 * i + n] = (uint8_t)(values[i] >> (56 - 8 * n));
    return [NSData dataWithBytes:bytes length:sizeof bytes];
}

@interface PRPV133TLSProbe : NSObject
@property(nonatomic, strong) nw_connection_t channel;
@property(nonatomic, strong) dispatch_queue_t queue;
@property(nonatomic, copy) NSString *folder;
@property(nonatomic) prp_pairing ids;
@property(nonatomic) bool startedExchange;
@property(nonatomic) bool paired;
@property(nonatomic) bool done;
- (void)start;
@end

@implementation PRPV133TLSProbe
- (void)finish:(NSString *)result {
    if (self.done) return;
    self.done = true;
    nw_connection_t channel = self.channel;
    self.channel = nil;
    if (channel) nw_connection_cancel(channel);
    prp_report(self.folder, result, self.paired);
}

- (void)send:(NSData *)bytes then:(dispatch_block_t)next {
    if (self.done) return;
    // Dispatch data owns the NSData through the destructor block.
    dispatch_data_t content = dispatch_data_create(bytes.bytes, bytes.length, self.queue, ^{
        (void)[bytes length];
    });
    nw_connection_send(self.channel, content, NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT, true,
        ^(nw_error_t error) {
            if (self.done) return;
            if (error) [self finish:@"send_failed"];
            else next();
        });
}

- (void)read:(uint32_t)size then:(void (^)(NSData *))next {
    if (self.done) return;
    nw_connection_receive(self.channel, size, size,
        ^(dispatch_data_t content, nw_content_context_t context, bool complete, nw_error_t error) {
            (void)context; (void)complete;
            if (self.done) return;
            if (error || !content || dispatch_data_get_size(content) != size) {
                [self finish:@"short_or_failed_receive"];
                return;
            }
            const void *buffer = NULL;
            size_t count = 0;
            __attribute__((objc_precise_lifetime)) dispatch_data_t mapped =
                dispatch_data_create_map(content, &buffer, &count);
            if (!mapped || !buffer || count != size) [self finish:@"invalid_receive"];
            else next([NSData dataWithBytes:buffer length:count]);
        });
}

- (void)exchange {
    nw_protocol_metadata_t layer = nw_connection_copy_protocol_metadata(
        self.channel, nw_protocol_copy_tls_definition());
    sec_protocol_metadata_t security = layer ? nw_tls_copy_sec_protocol_metadata(layer) : nil;
    if (!security || sec_protocol_metadata_get_negotiated_tls_protocol_version(security) !=
                         tls_protocol_version_TLSv13) {
        [self finish:@"wrong_tls_version"];
        return;
    }
    // The non-owning getter is available across the deployment target range.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    const char *protocol = sec_protocol_metadata_get_negotiated_protocol(security);
#pragma clang diagnostic pop
    if (!protocol || strcmp(protocol, PRP_ALPN) != 0) {
        [self finish:@"wrong_tls_protocol"];
        return;
    }
    prp_pairing ids = self.ids;
    [self send:prp_hello(ids, false) then:^{
        [self read:40 then:^(NSData *echo) {
            if (![echo isEqualToData:prp_hello(ids, true)]) {
                [self finish:@"pairing_mismatch"];
                return;
            }
            self.paired = true;
            rp_v133_action action = { .session_id=ids.session, .receiver=ids.peer,
                .nonce=1, .epoch=ids.epoch, .kind=RP_V133_GREET };
            uint8_t wire[RP_V133_WIRE_BYTES];
            if (!rp_v133_wire_encode(&action, wire, sizeof wire)) {
                [self finish:@"encode_failed"];
                return;
            }
            [self send:[NSData dataWithBytes:wire length:sizeof wire] then:^{
                [self read:RP_V133_WIRE_BYTES then:^(NSData *reply) {
                    rp_v133_action received;
                    bool ok = rp_v133_wire_decode(reply.bytes, reply.length, &received) &&
                        received.session_id == ids.session && received.epoch == ids.epoch &&
                        received.receiver == ids.local && received.nonce == 1 &&
                        received.kind == RP_V133_DOCUMENTS;
                    [self finish:ok ? @"greet_sent_documents_received" : @"unexpected_response"];
                }];
            }];
        }];
    }];
}

- (void)start {
    nw_connection_set_queue(self.channel, self.queue);
    __weak PRPV133TLSProbe *weakSelf = self;
    nw_connection_set_state_changed_handler(self.channel, ^(nw_connection_state_t state, nw_error_t error) {
        (void)error;
        PRPV133TLSProbe *probe = weakSelf;
        if (!probe || probe.done) return;
        if (state == nw_connection_state_ready && !probe.startedExchange) {
            probe.startedExchange = true;
            [probe exchange];
        } else if (state == nw_connection_state_failed || state == nw_connection_state_cancelled) {
            [probe finish:@"connection_failed"];
        }
    });
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 15 * NSEC_PER_SEC), self.queue, ^{
        [self finish:@"deadline"];
    });
    nw_connection_start(self.channel);
}
@end

void prp_start_tls_probe(NSString *folder) {
    dispatch_queue_t queue = dispatch_queue_create("prp3.tls.probe", DISPATCH_QUEUE_SERIAL);
    dispatch_async(queue, ^{
        NSString *path = [folder stringByAppendingPathComponent:PRP_CONFIG];
        NSFileHandle *file = [NSFileHandle fileHandleForReadingAtPath:path];
        if (!file) return; // No private test configuration, no network activity.
        NSData *data = [file readDataUpToLength:16385 error:NULL];
        [file closeAndReturnError:NULL];
        id json = data.length && data.length <= 16384
            ? [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL] : nil;
        NSDictionary *config = [json isKindOfClass:[NSDictionary class]] ? json : nil;
        NSString *host = config[@"host"];
        NSNumber *port = config[@"port"], *expires = config[@"expires"];
        NSTimeInterval now = [[NSDate date] timeIntervalSince1970];
        prp_pairing ids = {0};
        if (![config[@"schema"] isEqual:@"prp3-tls-probe-v1"] || !prp_is_local_ip(host) ||
            ![port isKindOfClass:[NSNumber class]] || port.doubleValue != port.unsignedIntValue ||
            port.unsignedIntValue < 1024 || port.unsignedIntValue > 65535 ||
            ![expires isKindOfClass:[NSNumber class]] ||
            !(expires.doubleValue > now && expires.doubleValue <= now + 1230) ||
            !prp_parse_id(config[@"local_id"], &ids.local) ||
            !prp_parse_id(config[@"peer_id"], &ids.peer) || ids.local == ids.peer ||
            !prp_parse_id(config[@"session"], &ids.session) ||
            !prp_parse_id(config[@"epoch"], &ids.epoch)) {
            prp_report(folder, @"invalid_or_expired_config", false);
            return;
        }
        NSData *pin = prp_b64(config, @"server_pin", 32);
        NSData *root = prp_b64(config, @"anchor", 4096);
        sec_identity_t identity = prp_import_identity(prp_b64(config, @"identity", 8192),
                                                      config[@"passphrase"]);
        SecCertificateRef issuer = root ? SecCertificateCreateWithData(NULL, (__bridge CFDataRef)root) : NULL;
        if (!identity || !issuer || pin.length != CC_SHA256_DIGEST_LENGTH) {
            if (issuer) CFRelease(issuer);
            prp_report(folder, @"identity_or_certificate_invalid", false);
            return;
        }
        NSArray *anchors = @[CFBridgingRelease(issuer)];
        nw_parameters_t parameters = nw_parameters_create_secure_tcp(^(nw_protocol_options_t tls) {
            sec_protocol_options_t options = nw_tls_copy_sec_protocol_options(tls);
            sec_protocol_options_set_min_tls_protocol_version(options, tls_protocol_version_TLSv13);
            sec_protocol_options_set_max_tls_protocol_version(options, tls_protocol_version_TLSv13);
            sec_protocol_options_add_tls_application_protocol(options, PRP_ALPN);
            sec_protocol_options_set_local_identity(options, identity);
            sec_protocol_options_set_tls_resumption_enabled(options, false);
            sec_protocol_options_set_peer_authentication_required(options, true);
            sec_protocol_options_set_verify_block(options, ^(sec_protocol_metadata_t metadata,
                sec_trust_t trust, sec_protocol_verify_complete_t done) {
                (void)metadata;
                done(prp_verify_trust(trust, host, anchors, pin));
            }, queue);
        }, NW_PARAMETERS_DEFAULT_CONFIGURATION);
        NSString *service = port.stringValue;
        nw_endpoint_t endpoint = nw_endpoint_create_host(host.UTF8String, service.UTF8String);
        PRPV133TLSProbe *probe = [[PRPV133TLSProbe alloc] init];
        probe.folder = folder;
        probe.queue = queue;
        probe.ids = ids;
        probe.channel = nw_connection_create(endpoint, parameters);
        if (probe.channel) [probe start];
        else prp_report(folder, @"connection_setup_failed", false);
    });
}
