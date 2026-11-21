#ifndef RP_V133_AUTHORITY_SOCIAL_H
#define RP_V133_AUTHORITY_SOCIAL_H

#include "rp_v133_authority_client.h"
#include "rp_v133_wire.h"

#define RP_AUTHORITY_SOCIAL_REQUEST_BYTES 45u
#define RP_AUTHORITY_SOCIAL_RECEIPT_BYTES 21u

typedef struct {
    uint64_t self, session, epoch;
    bool ready;
    uint64_t last_nonce, pending_nonce;
    uint64_t last_sender;
    rp_v133_interaction_kind last_kind;
    uint8_t last_result; /* 1 denied; 2 recipient received; 3 cancelled */
    struct { uint64_t sender, nonce; } seen[RP_V133_POLICE_CAPACITY];
} rp_authority_social;

/* Separate opt-in protocol on an already authenticated private authority
 * socket. Never maps an RP ID to a GTA player or dispatches a GTA event. */
bool rp_authority_social_open(rp_authority_social *social, const rp_authority_client *client,
                              uint8_t *out, size_t size);
bool rp_authority_social_request(rp_authority_social *social, rp_v133_interaction_kind kind,
                                 uint64_t target, uint8_t *out, size_t size);
/* On success, a SOCIAL_EVENT writes the full receipt; other kinds leave it
 * unchanged. The caller sends it only after local consent and peer checks. */
bool rp_authority_social_receive(rp_authority_social *social, uint8_t kind,
                                 const uint8_t *payload, size_t size,
                                 uint8_t *receipt, size_t receipt_size);
void rp_authority_social_stop(rp_authority_social *social);

#endif
