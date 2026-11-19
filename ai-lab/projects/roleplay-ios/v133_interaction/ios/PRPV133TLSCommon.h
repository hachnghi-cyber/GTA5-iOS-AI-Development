#ifndef PRP_V133_TLS_COMMON_H
#define PRP_V133_TLS_COMMON_H
#import <Foundation/Foundation.h>
#import <Network/Network.h>
#import <Security/Security.h>
#include <stdbool.h>
#include <stdint.h>

// Shared, existing diagnostic trust implementation. No engine metadata.
bool prp_parse_id(id value, uint64_t *out);
bool prp_is_local_ip(NSString *host);
NSData *prp_b64(NSDictionary *config, NSString *key, NSUInteger limit);
sec_identity_t prp_import_identity(NSData *data, NSString *password);
bool prp_verify_trust(sec_trust_t trust, NSString *hostname, NSArray *anchors, NSData *pin);
#endif
