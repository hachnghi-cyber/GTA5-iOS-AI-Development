/* EXPERIMENTAL / no engine or iPhone runtime verification.
 * Hashes sourced from CitizenFX natives and GTANetworkDev NativeHashes,
 * not guessed from offsets. Names also occur in shipped SHV's strings.
 * BEGIN_TEXT_COMMAND_PRINT 0xB87A37EEB7FAA67D
 * ADD_TEXT_COMPONENT_SUBSTRING_PLAYER_NAME 0x6C188BE134E074AA
 * END_TEXT_COMMAND_PRINT 0x9D77056A530643F6
 * ScriptHookV-native hash handling in this iOS port remains unverified.
 */
#include "rbp_native_adapter.h"
#ifdef RBP_FREESTANDING_ARM64
typedef __UINTPTR_TYPE__ rbp_uintptr;
#else
#include <stdint.h>
typedef uintptr_t rbp_uintptr;
#endif
#define RBP_BEGIN_PRINT UINT64_C(0xB87A37EEB7FAA67D)
#define RBP_ADD_PLAYER_NAME UINT64_C(0x6C188BE134E074AA)
#define RBP_END_PRINT UINT64_C(0x9D77056A530643F6)

static int show_hud_experimental(const rbp_native_api *api, const char *text) {
    static const char label[] = "STRING";

    if (!api || !api->init || !api->push || !api->call) return -1;
    api->init(RBP_BEGIN_PRINT);
    api->push((uint64_t)(rbp_uintptr)label);
    (void)api->call();
    api->init(RBP_ADD_PLAYER_NAME);
    api->push((uint64_t)(rbp_uintptr)text);
    (void)api->call();
    api->init(RBP_END_PRINT);
    api->push(1500);   /* milliseconds */
    api->push(1);      /* draw now */
    (void)api->call();
    return 1;
}

int rbp_diagnostic_game_tick_with_event(rbp_handoff *queue, const rbp_native_api *api,
                                        rbp_diag_event *receipt) {
    if (!queue || !api || !api->init || !api->push || !api->call) return -1;
    rbp_diag_event event = {0};
    int result = rbp_handoff_pop_on_game_thread(queue, &event);
    if (result != 1) return result;
    if (event.type != 1 || !event.sequence) return -1;
    result = show_hud_experimental(api, "RBP1 REMOTE E3 PING");
    if (result == 1 && receipt) *receipt=event;
    return result;
}
int rbp_diagnostic_game_tick_receipt(rbp_handoff *queue, const rbp_native_api *api, uint64_t *sequence) {
    rbp_diag_event receipt = {0};
    int result=rbp_diagnostic_game_tick_with_event(queue,api,&receipt);
    if (result==1 && sequence) *sequence=receipt.sequence;
    return result;
}

/* E1: same verified target-side ABI candidate without requiring transport. */
int rbp_local_probe_action(const rbp_native_api *api) {
    return show_hud_experimental(api, "RBP1 LOCAL E1 PING");
}

int rbp_diagnostic_game_tick(rbp_handoff *queue, const rbp_native_api *api) {
    return rbp_diagnostic_game_tick_receipt(queue,api,(uint64_t*)0);
}
