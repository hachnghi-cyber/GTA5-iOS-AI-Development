#include "police_rp_only.h"
#include <assert.h>
#include <stdio.h>
typedef struct {int cuff_calls, restriction_calls, cuff, restricted;} Mock;
static void cuff(void *p,int n){Mock*m=p;m->cuff=n;m->cuff_calls++;}
static void restrict_local(void *p,int n){Mock*m=p;m->restricted=n;m->restriction_calls++;}
int main(void){
    PR_Core core={0};Mock mock={0};
    PR_Callbacks cb={PR_ABI_VERSION,&mock,cuff,restrict_local};
    PR_Frame f={.abi_version=PR_ABI_VERSION,.online=1,.player_opted_in=1,
                .native_job=0,.on_shift=1,.session_verified=1,
                .authoritative_state=1,.local_status=PR_FREE,.status_age_ms=50};
    assert(pr_can_send_police_action(&f));
    for(int i=-1;i<17;i++){f.native_job=i;assert(pr_can_send_police_action(&f)==(i>=0&&i<=2));}
    f.native_job=0;f.on_shift=0;assert(!pr_can_send_police_action(&f));
    f.on_shift=1;f.online=0;assert(!pr_can_send_police_action(&f));
    f.online=1;f.player_opted_in=0;assert(!pr_can_send_police_action(&f));
    f.player_opted_in=1;f.session_verified=0;assert(!pr_can_send_police_action(&f));
    f.session_verified=1;assert(pr_can_send_police_action(&f));
    pr_tick(&core,&f,&cb);assert(mock.cuff_calls==0);
    f.local_status=PR_CUFFED;pr_tick(&core,&f,&cb);
    assert(mock.cuff && mock.restricted && mock.cuff_calls==1 && mock.restriction_calls==1);
    pr_tick(&core,&f,&cb);assert(mock.cuff_calls==1);
    assert(mock.restriction_calls==2); // must reapply disabled controls each frame
    f.status_age_ms=5000;pr_tick(&core,&f,&cb);
    assert(!mock.cuff&&!mock.restricted&&mock.cuff_calls==2);
    f.status_age_ms=50;f.local_status=PR_JAILED;pr_tick(&core,&f,&cb);
    assert(mock.cuff&&mock.restricted);
    f.player_opted_in=0;pr_tick(&core,&f,&cb);assert(!mock.cuff&&!mock.restricted);
    f.player_opted_in=1;f.session_verified=0;pr_tick(&core,&f,&cb);
    assert(!mock.cuff&&!mock.restricted);
    f.session_verified=1;f.authoritative_state=0;pr_tick(&core,&f,&cb);
    assert(!mock.cuff&&!mock.restricted);
    f.authoritative_state=1;f.local_status=(PR_Status)77;pr_tick(&core,&f,&cb);
    assert(!mock.cuff&&!mock.restricted);
    f.local_status=PR_ESCORTED;pr_tick(&core,&f,&cb);assert(mock.cuff);
    f.online=0;pr_tick(&core,&f,&cb);assert(!mock.cuff&&!mock.restricted);
    PR_Callbacks wrong=cb;wrong.abi_version=5;
    f.online=1;pr_tick(&core,&f,&wrong);assert(!mock.cuff);
    puts("PASS: native police-only policy tests; no ScriptHook/Menyoo dependency");
    return 0;
}
