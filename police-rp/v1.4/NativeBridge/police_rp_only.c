#include "police_rp_only.h"
#include <stddef.h>
static int valid(const PR_Frame *s) {
    return s && s->abi_version == PR_ABI_VERSION && s->online &&
           s->player_opted_in && s->session_verified;
}
int pr_can_send_police_action(const PR_Frame *s) {
    return valid(s) && s->on_shift && (s->native_job == 0 ||
           s->native_job == 1 || s->native_job == 2);
}
void pr_reset(PR_Core *core, const PR_Callbacks *cb) {
    if (!core) return;
    if (cb && cb->abi_version == PR_ABI_VERSION) {
        if (core->was_restricted && cb->set_local_controls_restricted)
            cb->set_local_controls_restricted(cb->userdata, 0);
        if (core->was_cuffed && cb->set_local_cuffed)
            cb->set_local_cuffed(cb->userdata, 0);
    }
    core->was_restricted = 0;
    core->was_cuffed = 0;
}
void pr_tick(PR_Core *core, const PR_Frame *frame, const PR_Callbacks *cb) {
    if (!core || !cb || cb->abi_version != PR_ABI_VERSION) return;
    // Fail open when offline, not opted in, session is not proven, or server is stale.
    if (!valid(frame) || !frame->authoritative_state ||
        frame->status_age_ms > PR_STATUS_TTL_MS ||
        frame->local_status > PR_JAILED || frame->local_status < PR_FREE) {
        pr_reset(core, cb);
        return;
    }
    int restricted = (frame->local_status == PR_CUFFED ||
         frame->local_status == PR_ESCORTED || frame->local_status == PR_JAILED);
    // Do not attempt to change a remote ped. The adapter must use its own local player.
    if (restricted != core->was_cuffed && cb->set_local_cuffed)
        cb->set_local_cuffed(cb->userdata, restricted);
    // GTA DISABLE_CONTROL_ACTION is frame-scoped: call on EVERY game tick
    // while restricted, but issue a single release when leaving the state.
    if (cb->set_local_controls_restricted && (restricted || core->was_restricted))
        cb->set_local_controls_restricted(cb->userdata, restricted);
    core->was_cuffed = (uint8_t)restricted;
    core->was_restricted = (uint8_t)restricted;
}
