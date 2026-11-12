#include "police_rp_adapter.h"
#include <stddef.h>

static int session_ok(const PR_EngineView *v) {
    return v && v->abi_version==PR_ADAPTER_ABI && v->online &&
           v->session_verified && v->verified_session_id && v->local_player_id;
}
static int player_ok(const PR_EngineView *v) {
    return session_ok(v) && v->local_opt_in;
}
void pr_adapter_init(PR_Adapter *a) {
    if (!a) return;
    PR_Adapter empty={0};
    *a=empty;
    a->reason=PR_DROP_NO_SESSION;
}
void pr_adapter_stop(PR_Adapter *a, const PR_Callbacks *cb) {
    if (!a) return;
    pr_reset(&a->core, cb);
    a->has_status=0;
    a->bound_session=0;
    a->bound_player=0;
    a->last_received_ms=0;
    PR_AuthenticatedStatus empty={0};
    a->last=empty;
    a->reason=PR_DROP_NO_SESSION;
}
int pr_adapter_accept(PR_Adapter *a,const PR_EngineView *v,
                      const PR_AuthenticatedStatus *s) {
    if (!a || !player_ok(v) || !s || s->abi_version!=PR_ADAPTER_ABI ||
        !s->authenticated || s->session_id!=v->verified_session_id ||
        s->local_player_id!=v->local_player_id ||
        s->status<PR_FREE || s->status>PR_JAILED)
        return 0;
    // Old state from a previous game session must never be accepted after
    // the transport reconnects; the caller must discard queued messages.
    a->last=*s;
    a->last_received_ms=v->monotonic_ms;
    a->bound_session=v->verified_session_id;
    a->bound_player=v->local_player_id;
    a->has_status=1;
    return 1;
}
void pr_adapter_tick(PR_Adapter *a,const PR_EngineView *v,
                     const PR_Callbacks *cb) {
    if (!a) return;
    if (!session_ok(v)) {
        pr_adapter_stop(a,cb);
        a->reason=PR_DROP_NO_SESSION;
        return;
    }
    if (!v->local_opt_in) {
        pr_adapter_stop(a,cb);
        a->reason=PR_DROP_NO_OPT_IN;
        return;
    }
    // Ownership/room changed -> discard immediately, even when the last
    // network packet was only milliseconds ago.
    if (a->has_status && (v->verified_session_id!=a->bound_session ||
                          v->local_player_id!=a->bound_player)) {
        pr_adapter_stop(a,cb);
        a->reason=PR_DROP_CONTEXT_CHANGED;
        return;
    }
    if (!a->has_status) {
        pr_reset(&a->core,cb);
        a->reason=PR_DROP_NO_AUTH_STATUS;
        return;
    }
    if (v->monotonic_ms<a->last_received_ms ||
        v->monotonic_ms-a->last_received_ms>PR_STATUS_TTL_MS) {
        pr_adapter_stop(a,cb);
        a->reason=PR_DROP_STALE;
        return;
    }
    PR_Frame f={0};
    f.abi_version=PR_ABI_VERSION;
    f.online=1;
    f.player_opted_in=1;
    f.native_job=v->native_job;
    f.on_shift=v->on_shift;
    f.session_verified=1;
    f.authoritative_state=1;
    f.status_age_ms=(uint32_t)(v->monotonic_ms-a->last_received_ms);
    f.local_status=a->last.status;
    a->reason=PR_DROP_NONE;
    pr_tick(&a->core,&f,cb);
}
int pr_adapter_can_arrest(const PR_Adapter *a,const PR_EngineView *v) {
    if (!a || !player_ok(v)) return 0;
    PR_Frame frame={0};
    frame.abi_version=PR_ABI_VERSION;
    frame.online=1;
    frame.player_opted_in=1;
    frame.session_verified=1;
    frame.native_job=v->native_job;
    frame.on_shift=v->on_shift;
    return pr_can_send_police_action(&frame);
}
