#include "rp_v133_wire.h"
#ifdef RP_TEST_CARRIER
#include "rp_v133_carrier.h"
#define TEST_PACKET_BYTES RP_V133_CARRIER_BYTES
#define TEST_INNER_OFFSET RP_V133_CARRIER_HEADER_BYTES
#else
#define TEST_PACKET_BYTES RP_V133_WIRE_BYTES
#define TEST_INNER_OFFSET 0u
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Entirely SYNTHETIC two-client transport harness. No GTA network bridge. */
typedef struct network network;
typedef struct endpoint {
    rp_v133_gate gate;
#ifdef RP_TEST_CARRIER
    rp_v133_mailbox mailbox;
#endif
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
    uint8_t packet[TEST_PACKET_BYTES];
    size_t packet_bytes;
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
#ifdef RP_TEST_CARRIER
    if (!rp_v133_carrier_encode(action,e->net->packet,sizeof(e->net->packet)))
#else
    if (!rp_v133_wire_encode(action,e->net->packet,sizeof(e->net->packet)))
#endif
        return false;
    e->net->packet_bytes=sizeof(e->net->packet);
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
#ifdef RP_TEST_CARRIER
    rp_v133_mailbox_init(&e->mailbox);
#endif
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
#ifdef RP_TEST_CARRIER
    /* Model ONLY the observed payload write, not real engine execution. */
    n->packet[8]=5;
    n->packet[9]=n->packet[10]=n->packet[11]=0;
    if (rp_v133_carrier_enqueue(&n->b.mailbox,&meta,n->packet,n->packet_bytes)
        != RP_V133_CARRIER_QUEUED) return RP_V133_DENIED;
    rp_v133_pump_report report;
    if (!rp_v133_mailbox_pump(&n->b.mailbox,&n->b.gate,&report)) return RP_V133_DENIED;
    return report.accepted == 1 ? RP_V133_RECEIVED : RP_V133_DENIED;
#else
    return rp_v133_wire_deliver(&n->b.gate,&meta,n->packet,n->packet_bytes);
#endif
}
int main(void) {
    network n;
    memset(&n,0,sizeof(n));
    init_endpoint(&n.a,&n,101);
    init_endpoint(&n.b,&n,202);
    assert(rp_v133_gate_request(&n.a.gate,202,RP_V133_GREET,1)==RP_V133_ATTEMPTED);
    assert(n.pending==1 && n.packet_bytes==TEST_PACKET_BYTES);
    assert(receive_b(&n)==RP_V133_RECEIVED);
    assert(n.b.observed==1 && n.b.last_sender==101 && n.b.last_kind==RP_V133_GREET);
    /* A sender field in the payload would not be trustworthy. Even an increased
     * nonce must fail without transport-owned authentication or peer provenance. */
    uint8_t attack[RP_V133_WIRE_BYTES];
    memcpy(attack,n.packet+TEST_INNER_OFFSET,sizeof attack);
    attack[32]=9;
    rp_v133_delivery invalid_meta={101,4002,3,0};
    assert(rp_v133_wire_deliver(&n.b.gate,&invalid_meta,attack,sizeof attack)==RP_V133_DENIED);
    invalid_meta.authenticated=1;
    invalid_meta.transport_sender=303; /* foreign peer */
    assert(rp_v133_wire_deliver(&n.b.gate,&invalid_meta,attack,sizeof attack)==RP_V133_DENIED);
    invalid_meta.transport_sender=101;
    invalid_meta.transport_epoch=4; /* wrong epoch */
    assert(rp_v133_wire_deliver(&n.b.gate,&invalid_meta,attack,sizeof attack)==RP_V133_DENIED);
    assert(n.b.observed==1);
    n.pending=1;
    assert(receive_b(&n)==RP_V133_DENIED); /* replay */
    n.packet[TEST_INNER_OFFSET+6]=1; /* reserved byte tamper */
    n.pending=1;
    assert(receive_b(&n)==RP_V133_DENIED);
    n.packet[TEST_INNER_OFFSET+6]=0;
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
    printf("v13.3 two-endpoint SYNTHETIC transport: PASS (packet=%u, greet/documents, replay, distance, migration, consent)\n", (unsigned)TEST_PACKET_BYTES);
    return 0;
}
