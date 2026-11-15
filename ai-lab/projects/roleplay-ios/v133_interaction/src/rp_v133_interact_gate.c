#include "rp_v133_interact_gate.h"

static bool supported(rp_v133_interaction_kind kind) {
    return kind == RP_V133_GREET || kind == RP_V133_DOCUMENTS;
}

static bool ready(rp_v133_gate *g, rp_v133_snapshot *snap) {
    if (!g || !g->bound || g->busy || !g->cb.on_game_thread ||
        !g->cb.read_engine_snapshot || !g->cb.authenticated_channel_ready ||
        !g->cb.attest_build || !g->cb.on_game_thread(g->cb.ctx) ||
        !g->cb.attest_build(g->cb.ctx, RP_V133_TARGET_UUID,
                            RP_V133_TARGET_SHA256) ||
        !g->cb.read_engine_snapshot(g->cb.ctx, snap) ||
        !g->cb.authenticated_channel_ready(g->cb.ctx) ||
        !snap->online || !snap->opted_in || !snap->session_id ||
        !snap->local_player_id || !snap->peer_epoch ||
        snap->session_id != g->last_session ||
        snap->peer_epoch != g->last_peer_epoch)
        return false;
    return true;
}

static rp_v133_result deny(rp_v133_gate *g) {
    if (g) ++g->denied;
    return RP_V133_DENIED;
}

void rp_v133_gate_init(rp_v133_gate *g, const rp_v133_gate_callbacks *cb) {
    if (!g) return;
    __builtin_memset(g, 0, sizeof *g);
    if (cb) g->cb = *cb;
}

void rp_v133_gate_stop(rp_v133_gate *g) {
    if (!g) return;
    g->bound = 0;
    g->last_session = 0;
    g->last_peer_epoch = 0;
    g->last_outgoing_nonce = 0;
    __builtin_memset(g->incoming, 0, sizeof g->incoming);
    /* Preserve busy during a reentrant callback. Never reset callbacks here. */
}

bool rp_v133_gate_rebind(rp_v133_gate *g) {
    if (!g || g->busy || !g->cb.on_game_thread || !g->cb.read_engine_snapshot ||
        !g->cb.attest_build || !g->cb.authenticated_channel_ready ||
        !g->cb.on_game_thread(g->cb.ctx) ||
        !g->cb.attest_build(g->cb.ctx, RP_V133_TARGET_UUID,
                            RP_V133_TARGET_SHA256)) return false;
    rp_v133_snapshot snap = {0};
    if (!g->cb.read_engine_snapshot(g->cb.ctx, &snap) || !snap.online ||
        !snap.opted_in || !snap.local_player_id || !snap.session_id ||
        !snap.peer_epoch || !g->cb.authenticated_channel_ready(g->cb.ctx)) {
        rp_v133_gate_stop(g);
        return false;
    }
    if (g->last_session != snap.session_id ||
        g->last_peer_epoch != snap.peer_epoch) {
        rp_v133_gate_stop(g);
    }
    g->last_session = snap.session_id;
    g->last_peer_epoch = snap.peer_epoch;
    g->bound = 1;
    return true;
}

rp_v133_result rp_v133_gate_request(rp_v133_gate *g, uint64_t target,
                                     rp_v133_interaction_kind kind, uint64_t nonce) {
    rp_v133_snapshot snap = {0};
    if (!ready(g, &snap) || !g->cb.target_is_trusted_nearby ||
        !g->cb.emit_interaction || !supported(kind) || !target ||
        target == snap.local_player_id || !nonce ||
        nonce <= g->last_outgoing_nonce) return deny(g);
    if (!g->cb.target_is_trusted_nearby(g->cb.ctx, target,
                                         snap.peer_epoch, RP_V133_MAX_INTERACT_CM))
        return deny(g);
    if (!g->bound || g->last_session != snap.session_id ||
        g->last_peer_epoch != snap.peer_epoch) return deny(g);
    rp_v133_action act = {snap.session_id, target, nonce, snap.peer_epoch, kind};
    g->busy = 1;
    bool emitted = g->cb.emit_interaction(g->cb.ctx, &act);
    g->busy = 0;
    /* If a callback stopped the gate, never report success from the stale emit. */
    if (!g->bound || g->last_session != snap.session_id ||
        g->last_peer_epoch != snap.peer_epoch || !emitted) return deny(g);
    g->last_outgoing_nonce = nonce;
    ++g->accepted;
    return RP_V133_ATTEMPTED;
}

rp_v133_result rp_v133_gate_deliver(rp_v133_gate *g,
                                     const rp_v133_delivery *meta,
                                     const rp_v133_action *act) {
    rp_v133_snapshot snap = {0};
    if (!ready(g, &snap) || !meta || !act || !meta->authenticated ||
        !meta->transport_sender || meta->transport_sender == snap.local_player_id ||
        meta->transport_session != snap.session_id ||
        meta->transport_epoch != snap.peer_epoch ||
        act->session_id != snap.session_id ||
        act->epoch != snap.peer_epoch ||
        act->receiver != snap.local_player_id ||
        !supported(act->kind) || !act->nonce ||
        !g->cb.observe_interaction || !g->cb.target_is_trusted_nearby)
        return deny(g);
    unsigned ledger = RP_V133_MAX_TRACKED_PEERS;
    unsigned free_slot = RP_V133_MAX_TRACKED_PEERS;
    for (unsigned i = 0; i < RP_V133_MAX_TRACKED_PEERS; ++i) {
        if (g->incoming[i].sender == meta->transport_sender) {
            ledger = i;
            break;
        }
        if (!g->incoming[i].sender && free_slot == RP_V133_MAX_TRACKED_PEERS)
            free_slot = i;
    }
    if (ledger == RP_V133_MAX_TRACKED_PEERS) ledger = free_slot;
    if (ledger == RP_V133_MAX_TRACKED_PEERS ||
        (g->incoming[ledger].sender == meta->transport_sender &&
         act->nonce <= g->incoming[ledger].nonce)) return deny(g);
    if (!g->cb.target_is_trusted_nearby(g->cb.ctx,
                  meta->transport_sender, snap.peer_epoch,
                  RP_V133_MAX_INTERACT_CM)) return deny(g);
    if (!g->bound || g->last_session != snap.session_id ||
        g->last_peer_epoch != snap.peer_epoch) return deny(g);
    g->busy = 1;
    g->cb.observe_interaction(g->cb.ctx, meta->transport_sender, act->kind);
    g->busy = 0;
    if (!g->bound || g->last_session != snap.session_id ||
        g->last_peer_epoch != snap.peer_epoch) return deny(g);
    g->incoming[ledger].sender = meta->transport_sender;
    g->incoming[ledger].nonce = act->nonce;
    ++g->accepted;
    return RP_V133_RECEIVED;
}
