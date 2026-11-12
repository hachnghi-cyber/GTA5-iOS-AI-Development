#ifndef PRP_CANDIDATE_CARRIER_H
#define PRP_CANDIDATE_CARRIER_H
#include <stdint.h>
#include <stddef.h>
#include "prp_engine_binding.h"
#ifdef __cplusplus
extern "C" {
#endif
/* 244 is the size observed in MacportJobSend -> CScriptedGameEvent in GTA5 v12.
 * THIS IS AN EXPERIMENTAL APPLICATION ENVELOPE, NOT an accepted RAGE packet.
 * Do not replace/modify native MPJ2 packets. The actual GTA event sender and
 * receiver must be implemented and verified separately. */
#define PRP_CANDIDATE_CARRIER_SIZE 244u
#define PRP_CANDIDATE_PAYLOAD_OFFSET 8u
#define PRP_CANDIDATE_CRC_OFFSET 64u

typedef struct {
    /* ALL metadata must be supplied by the authenticated RAGE dispatcher;
     * no field may be copied from any user-supplied serialized payload. */
    uint64_t trusted_session_id;
    uint64_t trusted_sender_id;
    uint8_t authenticated;
} PRP_TrustedDelivery;

int prp_carrier_pack(uint8_t out[PRP_CANDIDATE_CARRIER_SIZE],
                     const uint8_t wire[PRP_WIRE_SIZE]);
/* Validates fully before copying payload. Does not prove engine authentication. */
int prp_carrier_unpack(uint8_t wire[PRP_WIRE_SIZE],
                       const uint8_t *data, size_t n,
                       const PRP_TrustedDelivery *trusted);
/* Queues for game thread. The caller is responsible for obtaining trusted
 * metadata from game transport, and only after actual RAGE event dispatch. */
int prp_carrier_enqueue(PRP_GameBridge *bridge, const uint8_t *data, size_t n,
                        const PRP_TrustedDelivery *trusted);
#ifdef __cplusplus
}
#endif
#endif
