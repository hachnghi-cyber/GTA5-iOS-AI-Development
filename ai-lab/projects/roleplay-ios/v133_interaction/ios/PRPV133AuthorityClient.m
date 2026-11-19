// Native private-server transport. No gameplay hooks or identity inference.
#import "PRPV133AuthorityClient.h"
#import "PRPV133TLSCommon.h"
#import <Security/SecProtocolMetadata.h>
#import <Security/SecProtocolOptions.h>
#include <string.h>
#include "rp_v133_authority_client.h"

static const char RP_AUTH_ALPN[] = "police-rp-authority/1";
static NSString *const RP_AUTH_CONFIG = @"PoliceRP-Authority-PRIVATE.json";
static NSString *const RP_AUTH_LOG = @"PoliceRP-v13.3-Authority.txt";

@interface PRPV133AuthorityClient : NSObject {
@public
    rp_authority_client state;
    rp_consent_probe_phase consentProbePhase;
}
@property(nonatomic, strong) nw_connection_t channel;
@property(nonatomic, strong) dispatch_queue_t queue;
@property(nonatomic, strong) dispatch_source_t timer;
@property(nonatomic, copy) NSString *folder;
@property(nonatomic) uint64_t expectedID;
@property(nonatomic) NSTimeInterval expires;
@property(nonatomic) NSTimeInterval readDeadline;
@property(nonatomic) NSTimeInterval requestDeadline;
@property(nonatomic) NSTimeInterval nextPing;
@property(nonatomic) NSTimeInterval consentProbeDeadline;
@property(nonatomic) BOOL consentProbe;
@property(nonatomic) BOOL verified;
@property(nonatomic) BOOL done;
@property(nonatomic, copy) NSString *result;
- (void)start;
- (void)finish:(NSString *)result;
- (void)submit:(uint32_t)operation target:(uint64_t)target;
- (NSDictionary *)status;
- (void)report:(NSString *)result;
- (void)send:(NSData *)bytes;
- (void)read:(size_t)size then:(void (^)(NSData *))next;
- (void)consume:(uint8_t)kind payload:(NSData *)payload;
- (void)readRecord;
- (void)ready;
@end

static PRPV133AuthorityClient *authorityClient;
static dispatch_queue_t authorityQueue;

static NSTimeInterval rp_uptime(void) {
    return NSProcessInfo.processInfo.systemUptime;
}

@implementation PRPV133AuthorityClient
- (NSDictionary *)status {
    NSMutableArray *members = [NSMutableArray array];
    for (uint32_t i = 0; i < state.member_count; ++i) {
        const uint64_t *row = state.members[i];
        [members addObject:@{@"rp_id": [NSString stringWithFormat:@"%llu", (unsigned long long)row[0]],
            @"role": @(row[1]), @"consent": @(row[2]), @"duty": @(row[3]), @"custody": @(row[4])}];
    }
    return @{@"connected": @(!self.done && self.verified && state.ready),
             @"pending": @(state.pending), @"revision": @(state.revision),
             @"result": self.result ?: @"starting", @"members": members,
             @"gameplay_enabled": @NO};
}

- (void)report:(NSString *)result {
    self.result = result;
    NSString *text = [NSString stringWithFormat:
        @"schema=prp-authority-client-v1\ntime=%@\nresult=%@\n"
         "rp_tls_verified=%d\nconnected=%d\nmember_count=%u\nrevision=%llu\n"
         "engine_player_binding_verified=0\ngameplay_rp_enabled=0\n",
         [NSDate date], result, self.verified ? 1 : 0,
         (!self.done && state.ready) ? 1 : 0, state.member_count,
         (unsigned long long)state.revision];
    [text writeToFile:[self.folder stringByAppendingPathComponent:RP_AUTH_LOG]
           atomically:YES encoding:NSUTF8StringEncoding error:NULL];
}

- (void)finish:(NSString *)result {
    if (self.done) return;
    self.done = YES;
    rp_authority_client_stop(&state);
    if (self.timer) dispatch_source_cancel(self.timer);
    self.timer = nil;
    if (self.channel) nw_connection_cancel(self.channel);
    self.channel = nil;
    [self report:result];
}

- (void)send:(NSData *)bytes {
    if (self.done || !self.channel) return;
    dispatch_data_t content = dispatch_data_create(bytes.bytes, bytes.length,
                                                    self.queue, ^{ (void)bytes; });
    __weak PRPV133AuthorityClient *weakSelf = self;
    nw_connection_send(self.channel, content, NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT, true,
        ^(nw_error_t error) {
            PRPV133AuthorityClient *client = weakSelf;
            if (error && client && !client.done) [client finish:@"send_failed"];
        });
}

- (void)read:(size_t)size then:(void (^)(NSData *))next {
    if (self.done || !self.channel) return;
    if (!size || size > 4096) { [self finish:@"invalid_receive_size"]; return; }
    __weak PRPV133AuthorityClient *weakSelf = self;
    nw_connection_receive(self.channel, (uint32_t)size, (uint32_t)size,
        ^(dispatch_data_t content, nw_content_context_t context, bool complete, nw_error_t error) {
            (void)context; (void)complete;
            PRPV133AuthorityClient *client = weakSelf;
            if (!client || client.done) return;
            if (error || !content || dispatch_data_get_size(content) != size) {
                [client finish:@"short_or_failed_receive"];
                return;
            }
            const void *buffer = NULL;
            size_t count = 0;
            __attribute__((objc_precise_lifetime)) dispatch_data_t mapped =
                dispatch_data_create_map(content, &buffer, &count);
            if (!mapped || !buffer || count != size) [client finish:@"invalid_receive"];
            else next([NSData dataWithBytes:buffer length:count]);
        });
}

- (void)consume:(uint8_t)kind payload:(NSData *)payload {
    if (self.done) return;
    if (!rp_authority_client_receive(&state, kind, payload.bytes, payload.length)) {
        [self finish:@"protocol_rejected"];
        return;
    }
    if (kind == RP_AUTHORITY_WELCOME) [self report:@"authority_ready"];
    else if (kind == RP_AUTHORITY_ACK) {
        self.requestDeadline = 0;
        [self report:state.last_ack.outcome == RP_POLICE_TX_APPLIED ? @"decision_applied" : @"decision_denied"];
    } else if (kind == RP_AUTHORITY_SNAPSHOT) [self report:@"snapshot_received"];
    if (self.consentProbe) {
        uint8_t request[RP_AUTHORITY_REQUEST_BYTES];
        rp_consent_probe_result result = rp_authority_consent_probe_step(
            &state, &consentProbePhase, request, sizeof request);
        if (result == RP_CONSENT_PROBE_FAILED || result == RP_CONSENT_PROBE_PASSED) {
            [self finish:result == RP_CONSENT_PROBE_PASSED ? @"consent_round_trip_passed" : @"consent_round_trip_rejected"];
            return;
        }
        if (result == RP_CONSENT_PROBE_SEND) {
            self.requestDeadline = rp_uptime() + 5.0;
            [self send:[NSData dataWithBytes:request length:sizeof request]];
        }
    }
    [self readRecord];
}

- (void)readRecord {
    if (self.done) return;
    self.readDeadline = rp_uptime() + 12.0;
    [self read:5 then:^(NSData *header) {
        uint8_t kind = 0;
        uint32_t length = 0;
        if (!rp_authority_record_header(header.bytes, header.length, &kind, &length)) {
            [self finish:@"record_header_rejected"];
            return;
        }
        // The deadline is not renewed between header and body.
        if (!length) [self consume:kind payload:[NSData data]];
        else [self read:length then:^(NSData *body) { [self consume:kind payload:body]; }];
    }];
}

- (void)submit:(uint32_t)operation target:(uint64_t)target {
    if (self.done || !self.verified || !state.ready || self.consentProbe) return;
    uint8_t request[45];
    if (!rp_authority_client_request(&state, (rp_police_operation)operation, target,
                                     request, sizeof request)) {
        [self report:@"request_not_ready_or_invalid"];
        return;
    }
    self.requestDeadline = rp_uptime() + 5.0;
    [self send:[NSData dataWithBytes:request length:sizeof request]];
}

- (void)ready {
    nw_protocol_metadata_t layer = nw_connection_copy_protocol_metadata(
        self.channel, nw_protocol_copy_tls_definition());
    sec_protocol_metadata_t security = layer ? nw_tls_copy_sec_protocol_metadata(layer) : nil;
    // Match the existing probe's deployment-compatible, non-owning getter.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    const char *protocol = security ? sec_protocol_metadata_get_negotiated_protocol(security) : NULL;
#pragma clang diagnostic pop
    if (!security || sec_protocol_metadata_get_negotiated_tls_protocol_version(security) != tls_protocol_version_TLSv13 ||
            !protocol || strcmp(protocol, RP_AUTH_ALPN) ||
            !rp_authority_client_init(&state, self.expectedID)) {
        [self finish:@"tls_protocol_rejected"];
        return;
    }
    self.verified = YES; // RP certificate channel only; never RAGE/player auth.
    if (self.consentProbe) self.consentProbeDeadline = rp_uptime() + 12.0;
    self.nextPing = rp_uptime() + 3.0;
    [self readRecord];
}

- (void)start {
    self.readDeadline = rp_uptime() + 12.0;
    nw_connection_set_queue(self.channel, self.queue);
    __weak PRPV133AuthorityClient *weakSelf = self;
    nw_connection_set_state_changed_handler(self.channel, ^(nw_connection_state_t value, nw_error_t error) {
        (void)error;
        PRPV133AuthorityClient *client = weakSelf;
        if (!client || client.done) return;
        if (value == nw_connection_state_ready && !client.verified) [client ready];
        else if (value == nw_connection_state_failed || value == nw_connection_state_cancelled)
            [client finish:@"connection_failed"];
    });
    self.timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, self.queue);
    dispatch_source_set_timer(self.timer, dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), NSEC_PER_SEC, NSEC_PER_MSEC * 50);
    dispatch_source_set_event_handler(self.timer, ^{
        PRPV133AuthorityClient *client = weakSelf;
        if (!client || client.done) return;
        NSTimeInterval now = rp_uptime();
        if ([NSDate date].timeIntervalSince1970 >= client.expires || now >= client.readDeadline ||
                (client.requestDeadline && now >= client.requestDeadline) ||
                (client.consentProbeDeadline && now >= client.consentProbeDeadline)) {
            [client finish:@"expired_or_deadline"];
            return;
        }
        if (client->state.ready && now >= client.nextPing) {
            uint8_t ping[5];
            if (!rp_authority_client_ping(&client->state, ping, sizeof ping)) {
                [client finish:@"heartbeat_state_invalid"];
                return;
            }
            client.nextPing = now + 3.0;
            [client send:[NSData dataWithBytes:ping length:sizeof ping]];
        }
    });
    dispatch_resume(self.timer);
    nw_connection_start(self.channel);
}
@end

void prp_start_authority_client(NSString *folder) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        authorityQueue = dispatch_queue_create("police.rp.authority", DISPATCH_QUEUE_SERIAL);
        dispatch_async(authorityQueue, ^{
            NSFileHandle *file = [NSFileHandle fileHandleForReadingAtPath:
                                 [folder stringByAppendingPathComponent:RP_AUTH_CONFIG]];
            if (!file) return;
            NSData *data = [file readDataUpToLength:16385 error:NULL];
            [file closeAndReturnError:NULL];
            id parsed = data.length && data.length <= 16384 ?
                [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL] : nil;
            NSDictionary *config = [parsed isKindOfClass:[NSDictionary class]] ? parsed : nil;
            PRPV133AuthorityClient *client = [[PRPV133AuthorityClient alloc] init];
            client.folder = folder;
            client.queue = authorityQueue;
            authorityClient = client;
            NSString *host = config[@"host"];
            NSNumber *port = config[@"port"], *expires = config[@"expires"];
            id diagnostic = config[@"diagnostic"];
            uint64_t identityID = 0;
            NSTimeInterval now = [NSDate date].timeIntervalSince1970;
            if (![config[@"schema"] isEqual:@"prp-authority-client-v1"] || !prp_is_local_ip(host) ||
                ![port isKindOfClass:[NSNumber class]] || port.doubleValue != port.unsignedIntValue ||
                port.unsignedIntValue < 1024 || port.unsignedIntValue > 65535 ||
                ![expires isKindOfClass:[NSNumber class]] || !(expires.doubleValue > now && expires.doubleValue <= now + 1230) ||
                !prp_parse_id(config[@"rp_id"], &identityID) ||
                (diagnostic && ![diagnostic isEqual:@"consent-round-trip-v1"])) {
                [client finish:@"invalid_or_expired_config"];
                return;
            }
            NSData *pin = prp_b64(config, @"server_pin", 32);
            NSData *root = prp_b64(config, @"anchor", 4096);
            sec_identity_t identity = prp_import_identity(prp_b64(config, @"identity", 8192), config[@"passphrase"]);
            SecCertificateRef issuer = root ? SecCertificateCreateWithData(NULL, (__bridge CFDataRef)root) : NULL;
            if (!identity || !issuer || pin.length != 32) {
                if (issuer) CFRelease(issuer);
                [client finish:@"identity_or_certificate_invalid"];
                return;
            }
            NSArray *anchors = @[CFBridgingRelease(issuer)];
            nw_parameters_t parameters = nw_parameters_create_secure_tcp(^(nw_protocol_options_t tls) {
                sec_protocol_options_t options = nw_tls_copy_sec_protocol_options(tls);
                sec_protocol_options_set_min_tls_protocol_version(options, tls_protocol_version_TLSv13);
                sec_protocol_options_set_max_tls_protocol_version(options, tls_protocol_version_TLSv13);
                sec_protocol_options_add_tls_application_protocol(options, RP_AUTH_ALPN);
                sec_protocol_options_set_local_identity(options, identity);
                sec_protocol_options_set_tls_resumption_enabled(options, false);
                sec_protocol_options_set_peer_authentication_required(options, true);
                sec_protocol_options_set_verify_block(options, ^(sec_protocol_metadata_t metadata,
                    sec_trust_t trust, sec_protocol_verify_complete_t done) {
                    (void)metadata;
                    done(prp_verify_trust(trust, host, anchors, pin));
                }, authorityQueue);
            }, NW_PARAMETERS_DEFAULT_CONFIGURATION);
            client.expectedID = identityID;
            client.consentProbe = diagnostic != nil;
            client.expires = expires.doubleValue;
            nw_endpoint_t endpoint = nw_endpoint_create_host(host.UTF8String, port.stringValue.UTF8String);
            client.channel = nw_connection_create(endpoint, parameters);
            if (client.channel) [client start];
            else [client finish:@"connection_setup_failed"];
        });
    });
}

void prp_authority_submit(uint32_t operation, uint64_t target) {
    if (!authorityQueue) return;
    dispatch_async(authorityQueue, ^{ [authorityClient submit:operation target:target]; });
}

void prp_authority_read_status(void (^reply)(NSDictionary *)) {
    if (!reply) return;
    if (!authorityQueue) {
        dispatch_async(dispatch_get_main_queue(), ^{ reply(@{@"connected": @NO, @"gameplay_enabled": @NO}); });
        return;
    }
    dispatch_async(authorityQueue, ^{
        NSDictionary *copy = authorityClient ? [authorityClient status] : @{@"connected": @NO, @"gameplay_enabled": @NO};
        dispatch_async(dispatch_get_main_queue(), ^{ reply(copy); });
    });
}
