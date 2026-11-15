#include "rp_v133_interact_gate.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Entirely SYNTHETIC two-client transport harness. No GTA network bridge. */
typedef struct network network;
typedef struct endpoint {
    rp_v133_gate gate;
    rp_v133_snapshot snap;
    network *net;
    int on_thread, build_verified, channel_authenticated, opted_in;
    uint32_t distance_cm;
    unsigned observed;
    uint64_t last_sender;
    rp_v133_interaction_kind last_kind;
} endpoint;
struct network {
    endpoint a, b;
    rp_v133_action queued;
    uint64_t trusted_sender_from_transport;
    unsigned pending;
};

static bool build(void *ctx,const char *uuid,const char *sha) {
    endpoint *e=(endpoint*)ctx;
    return e->build_verified && strcmp(uuid,RP_V133_TARGET_UUID)==0 &&
           strcmp(sha,RP_V133_TARGET_SHA256)==0;
}
static bool on_thread(void *ctx) {return ((endpoint*)ctx)->on_thread != 0;}
static bool snapshot(void *ctx,rp_v133_snapshot *out) {
    endpoint *e=(endpoint*)ctx;
    *out=e->snap;
    out->opted_in=(uint8_t)e->opted_in;
    return true;
}
static bool trusted_near(void *ctx,uint64_t other,uint64_t epoch,uint32_t radius) {
    endpoint *e=(endpoint*)ctx;
    uint64_t want=e == &e->net->a ? e->net->b.snap.local_player_id : e->net->a.snap.local_player_id;
    return other==want && epoch==e->snap.peer_epoch && e->distance_cm<=radius;
}
static bool channel(void *ctx){return ((endpoint*)ctx)->channel_authenticated != 0;}
static bool emit(void *ctx,const rp_v133_action *action) {
    endpoint *e=(endpoint*)ctx;
    if(e!=&e->net->a || e->net->pending) return false;
    e->net->queued=*action;
    /* Only fixture-owned identity; real sender MUST come from authenticated engine metadata. */
    e->net->trusted_sender_from_transport=e->snap.local_player_id;
    e->net->pending=1;
    return true;
}
static void observe(void *ctx,uint64_t sender,rp_v133_interaction_kind kind) {
    endpoint *e=(endpoint*)ctx;
    ++e->observed;
    e->last_sender=sender;
    e->last_kind=kind;
}
static void init_endpoint(endpoint *e,network *n,uint64_t self) {
    memset(e,0,sizeof(*e));
    e->net=n;
    e->snap=(rp_v133_snapshot){.session_id=4002,.local_player_id=self,
             .peer_epoch=3,.local_frame=1,.online=1,.opted_in=1};
    e->on_thread=e->build_verified=e->channel_authenticated=e->opted_in=1;
    e->distance_cm=250;
    rp_v133_gate_callbacks cb={build,on_thread,snapshot,trusted_near,channel,emit,observe,e};
    rp_v133_gate_init(&e->gate,&cb);
    assert(rp_v133_gate_rebind(&e->gate));
}
static rp_v133_result receive_b(network *n) {
    assert(n->pending);
    rp_v133_delivery meta={.transport_sender=n->trusted_sender_from_transport,
         .transport_session=n->b.snap.session_id,.transport_epoch=n->b.snap.peer_epoch,
         .authenticated=1};
    n->pending=0;
    return rp_v133_gate_deliver(&n->b.gate,&meta,&n->queued);
}
int main(void) {
    network n;
    memset(&n,0,sizeof(n));
    init_endpoint(&n.a,&n,101);
    init_endpoint(&n.b,&n,202);
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_GREET,1)==RP_V133_ATTEMPTED);
    assert(n.pending==1);
    assert(receive_b(&n)==RP_V133_RECEIVED);
    assert(n.b.observed==1 && n.b.last_sender==101 && n.b.last_kind==RP_V133_GREET);
    n.pending=1;
    assert(receive_b(&n)==RP_V133_DENIED); /* replay */
    assert(n.b.observed==1);
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_DOCUMENTS,2)==RP_V133_ATTEMPTED);
    assert(receive_b(&n)==RP_V133_RECEIVED);
    assert(n.b.observed==2 && n.b.last_kind==RP_V133_DOCUMENTS);
    n.a.distance_cm=410;
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_GREET,3)==RP_V133_DENIED);
    n.a.distance_cm=250;
    n.a.snap.session_id=n.b.snap.session_id=5010;
    n.a.snap.peer_epoch=n.b.snap.peer_epoch=4;
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_GREET,3)==RP_V133_DENIED);
    assert(rp_v133_gate_rebind(&n.a.gate));
    assert(rp_v133_gate_rebind(&n.b.gate));
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_GREET,1)==RP_V133_ATTEMPTED);
    assert(receive_b(&n)==RP_V133_RECEIVED);
    assert(n.b.observed==3);
    n.b.opted_in=0;
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_GREET,2)==RP_V133_ATTEMPTED);
    assert(receive_b(&n)==RP_V133_DENIED);
    assert(n.b.observed==3);
    printf("v13.3 two-endpoint SYNTHETIC transport: PASS (greet/documents, replay, distance, migration, consent)\n");
    return 0;
}
