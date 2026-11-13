#include "rp_v13_session_gate.h"
#include <string.h>

void rp_v13_session_gate_init(RP_V13_SessionGate *gate) {
    if (gate) memset(gate, 0, sizeof(*gate));
}

static int trusted_session(const RP_V13_SessionEvidence *session) {
    return session && session->abi == RP_V13_SESSION_ABI &&
        session->online == 1u && session->game_thread_verified == 1u &&
        session->session_verified == 1u &&
        session->carrier_authenticated == 1u &&
        session->local_peer_connected == 1u &&
        session->host_peer_connected == 1u &&
        session->session_id != 0u && session->local_player_id != 0u &&
        session->host_player_id != 0u && session->peer_generation != 0u;
}

RP_V13_SessionDecision rp_v13_session_gate_update(
    RP_V13_SessionGate *gate,
    const RP_V13_IdentityEvidence *binary,
    const RP_V13_SessionEvidence *session) {
    if (!gate) return RP_V13_SESSION_BLOCKED;
    if (gate->release_pending) return RP_V13_SESSION_RELEASE_REQUIRED;

    if (rp_v13_identity_check(binary) != RP_V13_IDENTITY_MATCH ||
        !trusted_session(session)) {
        if (gate->ready) {
            gate->ready = 0;
            gate->release_pending = 1;
            return RP_V13_SESSION_RELEASE_REQUIRED;
        }
        return RP_V13_SESSION_BLOCKED;
    }

    if (!gate->ready) {
        gate->session_id = session->session_id;
        gate->local_player_id = session->local_player_id;
        gate->host_player_id = session->host_player_id;
        gate->peer_generation = session->peer_generation;
        gate->last_monotonic_ms = session->monotonic_ms;
        gate->ready = 1;
        return RP_V13_SESSION_READY;
    }

    if (gate->session_id != session->session_id ||
        gate->local_player_id != session->local_player_id ||
        gate->host_player_id != session->host_player_id ||
        gate->peer_generation != session->peer_generation ||
        session->monotonic_ms < gate->last_monotonic_ms) {
        gate->ready = 0;
        gate->release_pending = 1;
        return RP_V13_SESSION_RELEASE_REQUIRED;
    }
    gate->last_monotonic_ms = session->monotonic_ms;
    return RP_V13_SESSION_READY;
}

void rp_v13_session_gate_acknowledge_released(RP_V13_SessionGate *gate) {
    if (!gate || !gate->release_pending) return;
    /* Retain no old identity state across a host/session migration. */
    memset(gate, 0, sizeof(*gate));
}

int rp_v13_session_gate_is_ready(const RP_V13_SessionGate *gate) {
    return gate && gate->ready == 1u && gate->release_pending == 0u;
}
