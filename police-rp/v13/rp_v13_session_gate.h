#ifndef RP_V13_SESSION_GATE_H
#define RP_V13_SESSION_GATE_H

#include <stdint.h>
#include "rp_v13_identity_gate.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RP_V13_SESSION_ABI 1u

/* These fields must come from an independently verified GTA game-thread and
 * authenticated session adapter, NEVER a wire payload, menu or INI file.
 * There is NO such engine adapter supplied in this source-only module. */
typedef struct {
    uint32_t abi;
    uint64_t session_id;
    uint64_t local_player_id;
    uint64_t host_player_id;
    uint64_t monotonic_ms;
    uint32_t peer_generation;
    uint8_t online;
    uint8_t game_thread_verified;
    uint8_t session_verified;
    uint8_t carrier_authenticated;
    uint8_t local_peer_connected;
    uint8_t host_peer_connected;
} RP_V13_SessionEvidence;

typedef enum {
    RP_V13_SESSION_BLOCKED = 0,
    RP_V13_SESSION_READY = 1,
    RP_V13_SESSION_RELEASE_REQUIRED = 2
} RP_V13_SessionDecision;

typedef struct {
    uint64_t session_id;
    uint64_t local_player_id;
    uint64_t host_player_id;
    uint64_t last_monotonic_ms;
    uint32_t peer_generation;
    uint8_t ready;
    uint8_t release_pending;
} RP_V13_SessionGate;

void rp_v13_session_gate_init(RP_V13_SessionGate *gate);
/* Called ON THE VERIFIED GAME THREAD before each RP bridge frame.
 * READY means metadata contract passed, NOT roleplay opt-in or permission.
 * RELEASE_REQUIRED means call prp_port_stop()/release local restraints
 * before acknowledge_released(). Do NOT auto-rearm until that returns.
 * Any missing evidence while ready or a session/host/generation change
 * requires a release; returning to valid evidence alone cannot rearm. */
RP_V13_SessionDecision rp_v13_session_gate_update(
    RP_V13_SessionGate *gate,
    const RP_V13_IdentityEvidence *binary,
    const RP_V13_SessionEvidence *session);
/* ONLY call after the game-thread release/bridge stop actually completed.
 * An acknowledgement cannot verify the engine callback itself. */
void rp_v13_session_gate_acknowledge_released(RP_V13_SessionGate *gate);
int rp_v13_session_gate_is_ready(const RP_V13_SessionGate *gate);

#ifdef __cplusplus
}
#endif
#endif
