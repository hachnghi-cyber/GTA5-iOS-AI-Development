#include "rp_v133_interact_gate.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    rp_v133_gate *gate;
    rp_v133_snapshot snap;
    bool build_ok, thread_ok, channel_ok, near_ok, emit_ok;
    bool stop_during_emit, stop_during_near, stop_during_observe;
    int emits, receives;
    uint64_t last_sender;
    rp_v133_action last_emit;
} harness;

static bool build(void *ctx,const char *uuid,const char *sha) {
    harness *h=(harness *)ctx;
    return h->build_ok && strcmp(uuid,RP_V133_TARGET_UUID)==0 &&
        strcmp(sha,RP_V133_TARGET_SHA256)==0;
}
static bool thread(void *ctx) {return ((harness *)ctx)->thread_ok;}
static bool snap(void *ctx,rp_v133_snapshot *out) {
    *out=((harness *)ctx)->snap;
    return true;
}
static bool nearby(void *ctx,uint64_t peer,uint64_t epoch,uint32_t radius) {
    harness *h=(harness *)ctx;
    if (h->stop_during_near) rp_v133_gate_stop(h->gate);
    return h->near_ok && peer && epoch==h->snap.peer_epoch &&
        radius==400;
}
static bool channel(void *ctx) {return ((harness *)ctx)->channel_ok;}
static bool emit(void *ctx,const rp_v133_action *act) {
    harness *h=(harness *)ctx;
    ++h->emits;
    h->last_emit=*act;
    if (h->stop_during_emit) rp_v133_gate_stop(h->gate);
    return h->emit_ok;
}
static void observe(void *ctx,uint64_t sender,rp_v133_interaction_kind kind) {
    harness *h=(harness *)ctx;
    (void)kind;
    h->last_sender=sender;
    ++h->receives;
    if(h->stop_during_observe) rp_v133_gate_stop(h->gate);
}
static void setup(rp_v133_gate *gate,harness *h) {
    memset(h,0,sizeof *h);
    h->snap=(rp_v133_snapshot){.session_id=0xA110,.local_player_id=101,
                    .peer_epoch=99,.local_frame=888,.online=1,.opted_in=1};
    h->build_ok=h->thread_ok=h->channel_ok=h->near_ok=h->emit_ok=1;
    h->gate=gate;
    rp_v133_gate_callbacks cb={build,thread,snap,nearby,channel,emit,observe,h};
    rp_v133_gate_init(gate,&cb);
    assert(rp_v133_gate_rebind(gate));
}
int main(void) {
    rp_v133_gate g;
    harness h;
    setup(&g,&h);
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,10)==RP_V133_ATTEMPTED);
    assert(h.emits==1 && h.last_emit.receiver==202 && h.last_emit.session_id==0xA110);
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,10)==RP_V133_DENIED);
    assert(rp_v133_gate_request(&g,202,(rp_v133_interaction_kind)3,11)==RP_V133_DENIED);
    assert(rp_v133_gate_request(&g,101,RP_V133_DOCUMENTS,11)==RP_V133_DENIED);
    h.near_ok=false;
    assert(rp_v133_gate_request(&g,202,RP_V133_DOCUMENTS,12)==RP_V133_DENIED);
    h.near_ok=true;
    h.thread_ok=false;
    assert(rp_v133_gate_request(&g,202,RP_V133_DOCUMENTS,12)==RP_V133_DENIED);
    h.thread_ok=true;
    h.build_ok=false;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,12)==RP_V133_DENIED);
    h.build_ok=true;
    h.channel_ok=false;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,12)==RP_V133_DENIED);
    h.channel_ok=true;
    h.snap.opted_in=false;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,12)==RP_V133_DENIED);
    h.snap.opted_in=true;
    h.emit_ok=false;
    assert(rp_v133_gate_request(&g,202,RP_V133_DOCUMENTS,12)==RP_V133_DENIED);
    h.emit_ok=true;
    assert(rp_v133_gate_request(&g,202,RP_V133_DOCUMENTS,12)==RP_V133_ATTEMPTED);

    rp_v133_action act={0xA110,101,100,99,RP_V133_GREET};
    rp_v133_delivery dl={202,0xA110,99,1};
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_RECEIVED);
    assert(h.last_sender==202 && h.receives==1);
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_DENIED);
    dl.authenticated=0;
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_DENIED);
    dl.authenticated=1;
    dl.transport_session=0xA111;
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_DENIED);
    dl.transport_session=0xA110;
    act.receiver=500;
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_DENIED);
    act.receiver=101;
    /* Separate peer nonce ledger. Switching between senders cannot replay old events. */
    dl.transport_sender=303;
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_RECEIVED);
    dl.transport_sender=202;
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_DENIED);
    act.nonce=101;
    assert(rp_v133_gate_deliver(&g,&dl,&act)==RP_V133_RECEIVED);

    /* Session/epoch invalidation */
    h.snap.peer_epoch=100;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,13)==RP_V133_DENIED);
    assert(rp_v133_gate_rebind(&g));
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,1)==RP_V133_ATTEMPTED);
    h.snap.session_id=0xA220;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,2)==RP_V133_DENIED);
    assert(rp_v133_gate_rebind(&g));
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,2)==RP_V133_ATTEMPTED);

    /* Reentrant stop cannot report success */
    h.stop_during_emit=true;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,3)==RP_V133_DENIED);
    assert(!g.bound);
    h.stop_during_emit=false;
    assert(rp_v133_gate_rebind(&g));
    h.stop_during_near=true;
    assert(rp_v133_gate_request(&g,202,RP_V133_GREET,4)==RP_V133_DENIED);
    h.stop_during_near=false;
    assert(rp_v133_gate_rebind(&g));
    h.stop_during_observe=true;
    rp_v133_delivery newdl={202,0xA220,100,1};
    rp_v133_action newact={0xA220,101,1,100,RP_V133_GREET};
    assert(rp_v133_gate_deliver(&g,&newdl,&newact)==RP_V133_DENIED);
    assert(!g.bound);
    printf("v13.3 source-only interaction gate: PASS, denied=%u, emitted=%d, observed=%d\n",
            g.denied,h.emits,h.receives);
    return 0;
}
