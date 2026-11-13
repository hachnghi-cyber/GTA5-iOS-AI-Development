#include "rp_v13_frame_dispatcher.h"
#include <string.h>

void rp_v13_dispatcher_init(RP_V13_FrameDispatcher *d,
                            RP_V13_ProcessGameFrame process,
                            RP_V13_SessionStopLocal stop_local,
                            void *ctx) {
    if (!d) return;
    memset(d, 0, sizeof(*d));
    rp_v13_session_gate_init(&d->gate);
    d->process = process;
    d->stop_local = stop_local;
    d->ctx = ctx;
}

static void request_release(RP_V13_SessionGate *gate) {
    if (!gate || !gate->ready) return;
    gate->ready = 0u;
    gate->release_pending = 1u;
}

static int on_verified_game_thread(const RP_V13_SessionEvidence *s) {
    return s && s->abi == RP_V13_SESSION_ABI &&
           s->game_thread_verified == 1u;
}

RP_V13_DispatchResult rp_v13_dispatcher_tick(
    RP_V13_FrameDispatcher *d,
    const RP_V13_IdentityEvidence *binary,
    const RP_V13_SessionEvidence *session) {
    if (!d) return RP_V13_DISPATCH_BLOCKED;

    /* Missing mandatory callbacks are never permission to run gameplay. */
    if (!d->process || !d->stop_local) request_release(&d->gate);

    RP_V13_SessionDecision gate_decision =
        rp_v13_session_gate_update(&d->gate, binary, session);

    if (gate_decision == RP_V13_SESSION_RELEASE_REQUIRED) {
        /* Never invoke GTA controls from a thread that has not been verified.
         * Keep release latched until a verified game-thread tick arrives. */
        if (!on_verified_game_thread(session))
            return RP_V13_DISPATCH_RELEASE_PENDING;
        if (rp_v13_session_gate_release_with_stop(&d->gate,
                                                  d->stop_local, d->ctx))
            return RP_V13_DISPATCH_RELEASED;
        return RP_V13_DISPATCH_RELEASE_PENDING;
    }

    if (gate_decision != RP_V13_SESSION_READY || !d->process ||
        !d->stop_local) return RP_V13_DISPATCH_BLOCKED;

    if (d->process(d->ctx) == 1) return RP_V13_DISPATCH_PROCESSED;

    /* A failing frame must not leave the local ped under stale RP controls.
     * The helper only acknowledges a release after stop_local succeeded. */
    request_release(&d->gate);
    if (rp_v13_session_gate_release_with_stop(&d->gate,
                                              d->stop_local, d->ctx))
        return RP_V13_DISPATCH_RELEASED;
    return RP_V13_DISPATCH_RELEASE_PENDING;
}
