#ifndef RBP_NATIVE_ADAPTER_H
#define RBP_NATIVE_ADAPTER_H
#include "rbp_handoff.h"
/* Do not run this on a transport callback. Integration must call from a
 * RAGE-compatible script/game tick that is RUNTIME VERIFIED on the device.
 * Function-pointer signatures are inferred from ScriptHookV exports and
 * public SHV SDK conventions; ABI/runtime behavior still needs validation.
 */
typedef void (*rbp_native_init_fn)(uint64_t hash);
typedef void (*rbp_native_push64_fn)(uint64_t arg);
typedef uint64_t *(*rbp_native_call_fn)(void);
typedef struct {
    rbp_native_init_fn init;
    rbp_native_push64_fn push;
    rbp_native_call_fn call;
} rbp_native_api;
/* Returns -1 if no API, 0 no event, 1 if native sequence was INVOKED.
 * Return 1 does NOT mean a HUD notification was VISUALLY OBSERVED.
 */
int rbp_diagnostic_game_tick(rbp_handoff *queue, const rbp_native_api *api);
int rbp_diagnostic_game_tick_receipt(rbp_handoff *queue, const rbp_native_api *api, uint64_t *sequence);
/* Same game-thread-only native call, but returns sequence and nonce ONLY AFTER
 * three native calls were attempted. Does not mean the HUD was visible.
 * Caller must never send this receipt on the game thread. */
int rbp_diagnostic_game_tick_with_event(rbp_handoff *queue, const rbp_native_api *api,
                                        rbp_diag_event *receipt);
/* Returns 1 if native invocation was attempted, not if visually observed. */
int rbp_local_probe_action(const rbp_native_api *api);
#endif
