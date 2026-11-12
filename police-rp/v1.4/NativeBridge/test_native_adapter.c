#include "police_rp_adapter.h"
#include <assert.h>
#include <stdio.h>

typedef struct { int cuff, restriction, cuff_calls, restrict_calls; } Mock;
static void cuff(void *p,int x){ Mock*m=p;m->cuff=x;m->cuff_calls++; }
static void restrict_local(void *p,int x){Mock*m=p;m->restriction=x;m->restrict_calls++;}
int main(void){
    PR_Adapter a;pr_adapter_init(&a);
    Mock m={0};PR_Callbacks cb={PR_ABI_VERSION,&m,cuff,restrict_local};
    PR_EngineView v={.abi_version=PR_ADAPTER_ABI,.monotonic_ms=1000,
        .online=1,.session_verified=1,.local_opt_in=1,.verified_session_id=101,
        .local_player_id=700,.native_job=0,.on_shift=1};
    PR_AuthenticatedStatus s={.abi_version=PR_ADAPTER_ABI,.session_id=101,
        .local_player_id=700,.status=PR_CUFFED,.authenticated=1};
    // Reject untrusted state, wrong target and wrong session.
    PR_AuthenticatedStatus bad=s;bad.authenticated=0;
    assert(!pr_adapter_accept(&a,&v,&bad));
    bad=s;bad.local_player_id=999;assert(!pr_adapter_accept(&a,&v,&bad));
    bad=s;bad.session_id=500;assert(!pr_adapter_accept(&a,&v,&bad));
    assert(pr_adapter_can_arrest(&a,&v));
    v.native_job=3;assert(!pr_adapter_can_arrest(&a,&v));v.native_job=0;
    v.on_shift=0;assert(!pr_adapter_can_arrest(&a,&v));v.on_shift=1;
    assert(pr_adapter_accept(&a,&v,&s));
    for(unsigned long long i=0;i<120;i++) {
        v.monotonic_ms=1000+i*16;
        pr_adapter_tick(&a,&v,&cb);
        assert(m.cuff&&m.restriction);
    }
    assert(m.cuff_calls==1);
    assert(m.restrict_calls==120); // Must re-apply control lock each frame.
    v.monotonic_ms=6001;pr_adapter_tick(&a,&v,&cb);
    assert(!m.cuff&&!m.restriction&&a.reason==PR_DROP_STALE);
    assert(pr_adapter_accept(&a,&v,&s));pr_adapter_tick(&a,&v,&cb);
    assert(m.cuff);
    v.verified_session_id=102;pr_adapter_tick(&a,&v,&cb);
    assert(!m.cuff&&!m.restriction&&a.reason==PR_DROP_CONTEXT_CHANGED);
    // stale status for room 101 rejected even though sender is authenticated
    assert(!pr_adapter_accept(&a,&v,&s));
    s.session_id=102;assert(pr_adapter_accept(&a,&v,&s));
    pr_adapter_tick(&a,&v,&cb);assert(m.cuff);
    v.local_opt_in=0;pr_adapter_tick(&a,&v,&cb);
    assert(!m.cuff&&!m.restriction&&a.reason==PR_DROP_NO_OPT_IN);
    // Opt back in doesn't magically restore stale cuffs.
    v.local_opt_in=1;pr_adapter_tick(&a,&v,&cb);assert(!m.cuff);
    assert(a.reason==PR_DROP_NO_AUTH_STATUS);
    assert(pr_adapter_accept(&a,&v,&s));pr_adapter_tick(&a,&v,&cb);
    assert(m.cuff);
    v.online=0;pr_adapter_tick(&a,&v,&cb);assert(!m.cuff);
    assert(a.reason==PR_DROP_NO_SESSION);
    // Server-provided 'jailed' state does not lead to teleport or remote ped changes.
    v.online=1;s.status=PR_JAILED;
    assert(pr_adapter_accept(&a,&v,&s));pr_adapter_tick(&a,&v,&cb);assert(m.cuff);
    pr_adapter_stop(&a,&cb);assert(!m.cuff&&!m.restriction);
    puts("PASS: native RP session, opt-in, stale, 120-frame control and local-only adapter");
    return 0;
}
