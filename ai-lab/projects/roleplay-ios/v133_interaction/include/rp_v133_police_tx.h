#ifndef RP_V133_POLICE_TX_H
#define RP_V133_POLICE_TX_H

#include <stddef.h>
#include "rp_v133_police.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RP_POLICE_TX_BYTES 40u

typedef enum {
    RP_POLICE_TX_DENIED = 1,
    RP_POLICE_TX_APPLIED
} rp_police_tx_outcome;

typedef struct {
    rp_police_command command;
    rp_police_tx_outcome outcome;
} rp_police_ack;

/* Separate protocol from PRP3 GREET/DOCUMENTS. No sender field. */
bool rp_police_tx_encode(const rp_police_command *command, uint8_t *out, size_t size);
/* Authority-only. Returns a decision ACK for a new authenticated transaction,
 * or the cached ACK for an exact retry of the latest transaction. Does not
 * acknowledge a wrong session, unknown sender, malformed frame or old nonce.
 * ACK reports the original decision, not current native gameplay or state.
 */
bool rp_police_tx_dispatch(rp_police_world *world, const rp_v133_delivery *delivery,
                          const rp_police_observation *observation,
                          const uint8_t *wire, size_t wire_size,
                          uint8_t *ack, size_t ack_size);
/* Use only on an authenticated authority channel. Parsing never authenticates. */
bool rp_police_tx_decode_ack(const uint8_t *wire, size_t size,
                            const rp_police_command *pending, rp_police_ack *out);

#ifdef __cplusplus
}
#endif
#endif
