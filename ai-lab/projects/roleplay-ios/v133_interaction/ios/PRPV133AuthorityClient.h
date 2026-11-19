#ifndef PRP_V133_AUTHORITY_CLIENT_H
#define PRP_V133_AUTHORITY_CLIENT_H
#import <Foundation/Foundation.h>
#include <stdint.h>

// Starts only with a valid local private config. A transport client, not a
// RAGE adapter: no player pointers, game natives or stock event replacement.
void prp_start_authority_client(NSString *folder);
// Future native UI entry. RP target is a server principal, never a game slot.
void prp_authority_submit(uint32_t operation, uint64_t target);
// Copies transport state to main queue. A snapshot is not a native effect.
void prp_authority_read_status(void (^reply)(NSDictionary *status));
#endif
