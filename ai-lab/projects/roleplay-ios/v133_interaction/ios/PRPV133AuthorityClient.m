// Native private-server transport. No gameplay hooks or identity inference.
#import "PRPV133AuthorityClient.h"
#import "PRPV133TLSCommon.h"
#import <Security/SecProtocolMetadata.h>
#import <Security/SecProtocolOptions.h>
#include <string.h>
#include "rp_v133_authority_client.h"
#include "rp_v133_authority_social.h"

static const char RP_AUTH_ALPN[] = "police-rp-authority/1";
static const char RP_ACCOUNT_ALPN[] = "police-rp-account/1";
static NSString *const RP_AUTH_CONFIG = @"PoliceRP-Authority-PRIVATE.json";
static NSString *const RP_AUTH_LOG = @"PoliceRP-v13.3-Authority.txt";
void prp_install_authority_panel(void);

typedef NS_ENUM(NSUInteger, RPSocialProbePhase) {
    RPSocialOpening, RPSocialOptingIn, RPSocialAwaitingGreet, RPSocialAwaitingReceipt
};

@interface PRPV133AuthorityClient : NSObject {
@public
    rp_authority_client state;
    rp_consent_probe_phase consentProbePhase;
    rp_authority_social social;
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
@property(nonatomic) BOOL playerPanel;
@property(nonatomic) BOOL accountMode;
@property(nonatomic) BOOL authenticating;
@property(nonatomic, strong) NSData *accountFrame;
@property(nonatomic) uint64_t socialPeer;
@property(nonatomic) RPSocialProbePhase socialPhase;
@property(nonatomic) BOOL verified;
@property(nonatomic) BOOL done;
@property(nonatomic, copy) NSString *result;
@property(nonatomic) uint64_t panelConsentNonce;
@property(nonatomic) uint8_t lastPanelReceipt;
@property(nonatomic, copy) NSString *lastPanelEvent;
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
- (void)advanceSocialProbe;
- (void)consumeSocial:(uint8_t)kind payload:(NSData *)payload;
- (const uint64_t *)member:(uint64_t)identity;
- (void)submitPanelAction:(uint32_t)interaction;
@end

static PRPV133AuthorityClient *authorityClient;
static dispatch_queue_t authorityQueue;
static nw_endpoint_t accountEndpoint;
static nw_parameters_t accountParameters;

static NSTimeInterval rp_uptime(void) {
    return NSProcessInfo.processInfo.systemUptime;
}

@implementation PRPV133AuthorityClient
- (const uint64_t *)member:(uint64_t)identity {
    for (uint32_t i = 0; i < state.member_count; ++i) {
        if (state.members[i][0] == identity) return state.members[i];
    }
    return NULL;
}

- (NSDictionary *)status {
    NSMutableArray *members = [NSMutableArray array];
    for (uint32_t i = 0; i < state.member_count; ++i) {
        const uint64_t *row = state.members[i];
        [members addObject:@{@"rp_id": [NSString stringWithFormat:@"%llu", (unsigned long long)row[0]],
            @"role": @(row[1]), @"consent": @(row[2]), @"duty": @(row[3]), @"custody": @(row[4])}];
    }
    const uint64_t *subject = [self member:self.expectedID];
    const uint64_t *peer = [self member:self.socialPeer];
    return @{@"connected": @(!self.done && self.verified && state.ready),
             @"pending": @(state.pending || self.panelConsentNonce), @"revision": @(state.revision),
             @"result": self.result ?: @"starting", @"members": members,
             @"panel_ready": @(self.playerPanel && social.ready && subject != NULL),
             @"account_mode": @(self.accountMode), @"auth_busy": @(self.authenticating),
             @"account_active": @(self.accountMode && !self.done && state.ready),
             @"profile_expired": @([NSDate date].timeIntervalSince1970 >= self.expires),
             @"panel_consented": @(subject && subject[2]),
             @"panel_peer_consented": @(peer && peer[2]),
             @"panel_social_pending": @(social.pending_nonce != 0),
             @"panel_receipt": @(self.lastPanelReceipt),
             @"panel_event": self.lastPanelEvent ?: @"",
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
    self.authenticating = NO;
    self.accountFrame = nil;
    self.panelConsentNonce = 0;
    self.lastPanelReceipt = 0;
    self.lastPanelEvent = nil;
    rp_authority_client_stop(&state);
    rp_authority_social_stop(&social);
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
    if (kind == RP_AUTHORITY_SOCIAL_STATE || kind == RP_AUTHORITY_SOCIAL_EVENT ||
            kind == RP_AUTHORITY_SOCIAL_RESULT) {
        [self consumeSocial:kind payload:payload];
        [self readRecord];
        return;
    }
    if (!rp_authority_client_receive(&state, kind, payload.bytes, payload.length)) {
        [self finish:@"protocol_rejected"];
        return;
    }
    if (kind == RP_AUTHORITY_WELCOME) {
        self.authenticating = NO;
        [self report:@"authority_ready"];
        if (self.socialPeer) {
            uint8_t open[RP_AUTHORITY_HEADER_BYTES];
            if (!rp_authority_social_open(&social, &state, open, sizeof open)) {
                [self finish:@"social_open_rejected"];
                return;
            }
            [self send:[NSData dataWithBytes:open length:sizeof open]];
        }
    }
    else if (kind == RP_AUTHORITY_ACK) {
        if (state.last_ack.outcome != RP_POLICE_TX_APPLIED) self.panelConsentNonce = 0;
        if (!self.panelConsentNonce) self.requestDeadline = 0;
        [self report:state.last_ack.outcome == RP_POLICE_TX_APPLIED ? @"decision_applied" : @"decision_denied"];
    } else if (kind == RP_AUTHORITY_SNAPSHOT) {
        const uint64_t *subject = self.panelConsentNonce ? [self member:self.expectedID] : NULL;
        if (subject && subject[9] == self.panelConsentNonce && !state.pending) {
            self.panelConsentNonce = 0;
            self.requestDeadline = 0;
        }
        [self report:@"snapshot_received"];
    }
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
    if (self.socialPeer && !self.playerPanel) [self advanceSocialProbe];
    [self readRecord];
}

- (void)advanceSocialProbe {
    if (!social.ready || !state.revision || state.pending || self.done) return;
    const uint64_t *selfRow = [self member:state.expected_id];
    if (!selfRow) { [self finish:@"social_subject_missing"]; return; }
    if (self.socialPhase == RPSocialOpening) {
        uint8_t request[RP_AUTHORITY_REQUEST_BYTES];
        if (selfRow[2] || !rp_authority_client_request(&state, RP_POLICE_OPT_IN, state.expected_id,
                                                       request, sizeof request)) {
            [self finish:@"social_opt_in_rejected"];
            return;
        }
        self.socialPhase = RPSocialOptingIn;
        self.requestDeadline = rp_uptime() + 5.0;
        [self send:[NSData dataWithBytes:request length:sizeof request]];
    } else if (self.socialPhase == RPSocialOptingIn) {
        if (state.last_ack.outcome != RP_POLICE_TX_APPLIED) {
            [self finish:@"social_opt_in_denied"];
            return;
        }
        if (selfRow[2] && selfRow[9] == state.last_ack.command.nonce) {
            self.socialPhase = RPSocialAwaitingGreet;
            [self report:@"awaiting_private_greet"];
        }
    } else if (!selfRow[2]) {
        [self finish:@"social_consent_lost"];
    }
}

- (void)consumeSocial:(uint8_t)kind payload:(NSData *)payload {
    uint8_t receipt[RP_AUTHORITY_SOCIAL_RECEIPT_BYTES];
    if (!self.socialPeer || !rp_authority_social_receive(&social, kind, payload.bytes, payload.length,
                                                        receipt, sizeof receipt)) {
        [self finish:@"social_protocol_rejected"];
        return;
    }
    if (self.playerPanel) {
        if (kind == RP_AUTHORITY_SOCIAL_EVENT) {
            const uint64_t *subject = [self member:self.expectedID];
            if (!subject || !subject[2] || social.last_sender != self.socialPeer) return;
            self.lastPanelEvent = social.last_kind == RP_V133_GREET ?
                @"Đã nhận lời chào" : @"Đã nhận yêu cầu kiểm tra giấy tờ";
            [self send:[NSData dataWithBytes:receipt length:sizeof receipt]];
        } else if (kind == RP_AUTHORITY_SOCIAL_RESULT) {
            self.requestDeadline = 0;
            self.lastPanelReceipt = social.last_result;
        }
        return;
    }
    if (kind == RP_AUTHORITY_SOCIAL_STATE) {
        [self advanceSocialProbe];
    } else if (kind == RP_AUTHORITY_SOCIAL_EVENT) {
        uint8_t request[RP_AUTHORITY_SOCIAL_REQUEST_BYTES];
        if (self.socialPhase != RPSocialAwaitingGreet || social.last_sender != self.socialPeer ||
                social.last_kind != RP_V133_GREET ||
                !rp_authority_social_request(&social, RP_V133_DOCUMENTS, self.socialPeer, request, sizeof request)) {
            [self finish:@"unexpected_social_greet"];
            return;
        }
        self.socialPhase = RPSocialAwaitingReceipt;
        self.requestDeadline = rp_uptime() + 5.0;
        [self send:[NSData dataWithBytes:receipt length:sizeof receipt]];
        [self send:[NSData dataWithBytes:request length:sizeof request]];
        [self report:@"greet_received_documents_sent"];
    } else {
        [self finish:(self.socialPhase == RPSocialAwaitingReceipt && social.last_result == 2) ?
                     @"social_round_trip_passed" : @"documents_receipt_rejected"];
    }
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
    if (self.done || !self.verified || !state.ready || self.consentProbe ||
        (self.socialPeer && !self.playerPanel)) return;
    if (self.playerPanel) {
        const uint64_t *subject = [self member:self.expectedID];
        if (!social.ready || !subject || social.pending_nonce || self.panelConsentNonce || target != self.expectedID ||
            (operation != RP_POLICE_OPT_IN && operation != RP_POLICE_OPT_OUT) ||
            (subject[2] != 0) == (operation == RP_POLICE_OPT_IN)) return;
    }
    uint8_t request[RP_AUTHORITY_REQUEST_BYTES];
    if (!rp_authority_client_request(&state, (rp_police_operation)operation, target,
                                     request, sizeof request)) {
        [self report:@"request_not_ready_or_invalid"];
        return;
    }
    self.lastPanelReceipt = 0;
    self.lastPanelEvent = nil;
    if (self.playerPanel) self.panelConsentNonce = state.pending_command.nonce;
    self.requestDeadline = rp_uptime() + 5.0;
    [self send:[NSData dataWithBytes:request length:sizeof request]];
}

- (void)submitPanelAction:(uint32_t)interaction {
    const uint64_t *subject = [self member:self.expectedID];
    const uint64_t *peer = [self member:self.socialPeer];
    uint8_t request[RP_AUTHORITY_SOCIAL_REQUEST_BYTES];
    if (!self.playerPanel || self.done || state.pending || self.panelConsentNonce ||
        !subject || !subject[2] || !peer || !peer[2] ||
        (interaction != RP_V133_GREET && interaction != RP_V133_DOCUMENTS) ||
        !rp_authority_social_request(&social, (rp_v133_interaction_kind)interaction, self.socialPeer,
                                     request, sizeof request)) return;
    self.lastPanelReceipt = 0;
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
            !protocol || strcmp(protocol, self.accountMode ? RP_ACCOUNT_ALPN : RP_AUTH_ALPN) ||
            !rp_authority_client_init(&state, self.expectedID)) {
        [self finish:@"tls_protocol_rejected"];
        return;
    }
    self.verified = YES; // RP certificate channel only; never RAGE/player auth.
    if (self.accountMode) {
        if (!self.accountFrame) { [self finish:@"account_request_missing"]; return; }
        [self send:self.accountFrame];
        self.accountFrame = nil;
        // The pre-admission reply is exactly one byte in a five-byte record header.
        [self read:6 then:^(NSData *answer) {
            const uint8_t expected[] = {15, 0, 0, 0, 1, 1};
            if (answer.length != sizeof expected || memcmp(answer.bytes, expected, sizeof expected)) {
                [self finish:@"account_denied"];
                return;
            }
            [self readRecord];
        }];
        return;
    }
    if (self.consentProbe) self.consentProbeDeadline = rp_uptime() + 12.0;
    if (self.socialPeer && !self.playerPanel) self.consentProbeDeadline = rp_uptime() + 60.0;
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
            id panel = config[@"interface"];
            BOOL useSocial = [diagnostic isEqual:@"social-round-trip-v1"];
            BOOL usePanel = [panel isEqual:@"rp-panel-v1"];
            id account = config[@"account_ui"];
            BOOL deviceAccount = [account isEqual:@"device-account-v1"];
            uint64_t identityID = 0, socialPeer = 0;
            NSTimeInterval now = [NSDate date].timeIntervalSince1970;
            if (![config[@"schema"] isEqual:@"prp-authority-client-v1"] || !prp_is_local_ip(host) ||
                ![port isKindOfClass:[NSNumber class]] || port.doubleValue != port.unsignedIntValue ||
                port.unsignedIntValue < 1024 || port.unsignedIntValue > 65535 ||
                ![expires isKindOfClass:[NSNumber class]] || !(expires.doubleValue > now && expires.doubleValue <= now + 1230) ||
                !prp_parse_id(config[@"rp_id"], &identityID) ||
                (diagnostic && !useSocial && ![diagnostic isEqual:@"consent-round-trip-v1"]) ||
                (panel && (!usePanel || diagnostic)) ||
                (account && (!deviceAccount || !usePanel)) ||
                ((useSocial || usePanel) &&
                    (!prp_parse_id(config[@"rp_peer_id"], &socialPeer) || socialPeer == identityID))) {
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
                sec_protocol_options_add_tls_application_protocol(options, deviceAccount ? RP_ACCOUNT_ALPN : RP_AUTH_ALPN);
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
            client.consentProbe = [diagnostic isEqual:@"consent-round-trip-v1"];
            client.playerPanel = usePanel;
            client.accountMode = deviceAccount;
            client.socialPeer = socialPeer;
            client.expires = expires.doubleValue;
            nw_endpoint_t endpoint = nw_endpoint_create_host(host.UTF8String, port.stringValue.UTF8String);
            if (deviceAccount) {
                accountEndpoint = endpoint;
                accountParameters = parameters;
                dispatch_async(dispatch_get_main_queue(), ^{ prp_install_authority_panel(); });
                return;
            }
            client.channel = nw_connection_create(endpoint, parameters);
            if (client.channel) {
                if (usePanel) dispatch_async(dispatch_get_main_queue(), ^{ prp_install_authority_panel(); });
                [client start];
            }
            else [client finish:@"connection_setup_failed"];
        });
    });
}

void prp_authority_submit(uint32_t operation, uint64_t target) {
    if (!authorityQueue) return;
    dispatch_async(authorityQueue, ^{ [authorityClient submit:operation target:target]; });
}

void prp_authority_panel_consent(BOOL enabled) {
    if (!authorityQueue) return;
    dispatch_async(authorityQueue, ^{
        PRPV133AuthorityClient *client = authorityClient;
        if (client.playerPanel) [client submit:enabled ? RP_POLICE_OPT_IN : RP_POLICE_OPT_OUT
                                       target:client.expectedID];
    });
}

void prp_authority_panel_send(uint32_t interaction) {
    if (!authorityQueue) return;
    dispatch_async(authorityQueue, ^{ [authorityClient submitPanelAction:interaction]; });
}

void prp_authority_account(BOOL create, NSString *name, NSString *password) {
    if (!authorityQueue) return;
    NSData *user = [name dataUsingEncoding:NSUTF8StringEncoding];
    NSData *secret = [password dataUsingEncoding:NSUTF8StringEncoding];
    if (!user.length || user.length > 32 || !secret.length || secret.length > 512) return;
    dispatch_async(authorityQueue, ^{
        PRPV133AuthorityClient *old = authorityClient;
        if (!old.accountMode || old.authenticating || old->state.ready ||
            [NSDate date].timeIntervalSince1970 >= old.expires) return;
        // Every attempt has its own connection and callbacks. A late completion
        // from a retired connection cannot overwrite the new client's state.
        PRPV133AuthorityClient *client = [[PRPV133AuthorityClient alloc] init];
        client.folder = old.folder;
        client.queue = authorityQueue;
        client.expectedID = old.expectedID;
        client.socialPeer = old.socialPeer;
        client.expires = old.expires;
        client.playerPanel = client.accountMode = client.authenticating = YES;
        client.channel = nw_connection_create(accountEndpoint, accountParameters);
        authorityClient = client;
        if (!client.channel) { [client finish:@"connection_setup_failed"]; return; }
        uint32_t n = (uint32_t)(user.length + 1 + secret.length);
        const uint8_t header[] = {(uint8_t)(create ? 14 : 13), 0, 0, (uint8_t)(n >> 8), (uint8_t)n};
        uint8_t separator = 0;
        NSMutableData *frame = [NSMutableData dataWithBytes:header length:sizeof header];
        [frame appendData:user];
        [frame appendBytes:&separator length:1];
        [frame appendData:secret];
        client.accountFrame = frame;
        [client start];
    });
}

void prp_authority_logout(void) {
    if (!authorityQueue) return;
    dispatch_async(authorityQueue, ^{
        if (authorityClient.accountMode) [authorityClient finish:@"signed_out"];
    });
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
