#ifndef RP_V133_CARRIER_H
#define RP_V133_CARRIER_H
#include "rp_v133_mailbox.h"

/* Candidate CScriptedGameEvent envelope, SOURCE ONLY, NOT registered with GTA.
 * Exact v13.3 CEventNetworkScriptEvent can overwrite payload bytes 8..11 with
 * an engine slot. Bare PRP3 puts session_id there and must NEVER be used here.
 * Reserve that scratch field; sender/session trust MUST come from the adapter.
 * The marker is an independent experimental namespace, not a Winstom protocol.
 */
#define RP_V133_CARRIER_HEADER_BYTES 16u
#define RP_V133_CARRIER_BYTES (RP_V133_CARRIER_HEADER_BYTES + RP_V133_WIRE_BYTES)

typedef enum {
    RP_V133_CARRIER_DENIED = -1,
    RP_V133_CARRIER_NOT_OURS = 0,
    RP_V133_CARRIER_QUEUED = 1
} rp_v133_carrier_result;

int rp_v133_carrier_encode(const rp_v133_action *action,
                           uint8_t *out, size_t size);

/* Observer only: does not mutate or suppress the original engine event.
 * Call only AFTER an actual trusted adapter has validated remote connection,
 * session generation and sender identity. A struct/boolean alone is not proof.
 * No retained engine pointers: mailbox copies metadata and inner frame.
 */
rp_v133_carrier_result rp_v133_carrier_enqueue(
    rp_v133_mailbox *box, const rp_v133_delivery *trusted,
    const uint8_t *payload, size_t size);
#endif
