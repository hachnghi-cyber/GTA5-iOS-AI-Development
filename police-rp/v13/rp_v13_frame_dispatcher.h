#ifndef RP_V13_FRAME_DISPATCHER_H
#define RP_V13_FRAME_DISPATCHER_H

#include "rp_v13_session_gate.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Adapter contract ONLY. A later GTA5 integrator must provide a callback
 * authenticated by the exact v13 game engine; no RAGE hook is provided here.
 * Return EXACTLY 1 only when a source-only RP frame completed successfully.
 * Never call it on a networking/background thread. */
typedef int (*RP_V13_ProcessGameFrame)(void *ctx);

typedef enum {
    RP_V13_DISPATCH_BLOCKED = 0,
    RP_V13_DISPATCH_PROCESSED = 1,
    RP_V13_DISPATCH_RELEASE_PENDING = 2,
    RP_V13_DISPATCH_RELEASED = 3
} RP_V13_DispatchResult;

typedef struct {
    RP_V13_SessionGate gate;
    RP_V13_ProcessGameFrame process;
    RP_V13_SessionStopLocal stop_local;
    void *ctx;
} RP_V13_FrameDispatcher;

/* Initialize once BEFORE any RP gameplay. Do not reinitialize a live RP
 * dispatcher because it would discard a pending release. Set callbacks only
 * on the trusted GTA game thread. Both callbacks must be non-NULL to dispatch.
 * Actual session metadata must be produced by an independent trusted adapter,
 * never by remote player packets/config. */
void rp_v13_dispatcher_init(RP_V13_FrameDispatcher *d,
                            RP_V13_ProcessGameFrame process,
                            RP_V13_SessionStopLocal stop_local,
                            void *ctx);

/* Called from the engine's verified game-frame entry point. A bridge failure
 * immediately requests local release; it may only call stop_local when the
 * supplied evidence confirms game-thread execution. A successful stop is NOT
 * an automatic rearm: a fresh trusted tick is required to proceed. */
RP_V13_DispatchResult rp_v13_dispatcher_tick(
    RP_V13_FrameDispatcher *d,
    const RP_V13_IdentityEvidence *binary,
    const RP_V13_SessionEvidence *session);

#ifdef __cplusplus
}
#endif
#endif
