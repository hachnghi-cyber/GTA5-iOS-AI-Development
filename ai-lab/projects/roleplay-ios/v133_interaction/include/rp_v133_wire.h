#ifndef RP_V133_WIRE_H
#define RP_V133_WIRE_H
/*
 * Clean-room v13.3 RP diagnostic wire format. Exactly 40 bytes, versioned,
 * endian-stable, NOT an authentication layer.
 * Actor/sender identity MUST come from authenticated native transport metadata.
 *
 * Offset  Size  Meaning
 * 0       4     "PRP3"
 * 4       1     wire version (1)
 * 5       1     interaction kind (GREET=1, DOCUMENTS=2)
 * 6       2     reserved zero
 * 8       8     session id (little-endian uint64)
 * 16      8     receiver player id (little-endian uint64)
 * 24      8     session epoch (little-endian uint64)
 * 32      8     nonce (little-endian uint64)
 */
#include <stddef.h>
#include <stdint.h>
#include "rp_v133_interact_gate.h"

#ifdef __cplusplus
extern "C" {
#endif
#define RP_V133_WIRE_BYTES 40u
#define RP_V133_WIRE_VERSION 1u

/* Return 1 only for valid input and exact output size.
 * The output buffer is left unchanged on failure. */
int rp_v133_wire_encode(const rp_v133_action *action,
                        uint8_t *out, size_t out_len);

/* Fail-closed parser. Requires exactly 40 bytes. Zeroes *out on failure.
 * Parsing a packet NEVER authenticates sender identity. */
int rp_v133_wire_decode(const uint8_t *bytes, size_t size,
                        rp_v133_action *out);

/* Only call from authenticated native game-thread transport dispatch.
 * The delivery argument MUST be populated from engine-owned metadata. */
rp_v133_result rp_v133_wire_deliver(rp_v133_gate *gate,
                                     const rp_v133_delivery *delivery,
                                     const uint8_t *bytes, size_t size);
#ifdef __cplusplus
}
#endif
#endif
