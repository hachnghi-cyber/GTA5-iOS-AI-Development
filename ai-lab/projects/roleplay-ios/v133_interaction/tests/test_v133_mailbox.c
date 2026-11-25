#include "rp_v133_mailbox.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    rp_v133_snapshot snapshot;
    bool on_thread, channel, build_ok, near_ok;
    bool stop_on_observe;
    unsigned observations;
    rp_v133_gate *gate;
} fixture;

static bool attest(void *ctx, const char *uuid, const char *sha) {
    fixture *f=(fixture *)ctx;
    return f->build_ok && strcmp(uuid,RP_V133_TARGET_UUID)==0 &&
        strcmp(sha,RP_V133_TARGET_SHA256)==0;
}
static bool game_thread(void *ctx) {return ((fixture *)ctx)->on_thread;}
static bool snapshot(void *ctx, rp_v133_snapshot *out) {
    *out=((fixture *)ctx)->snapshot;
    return true;
}
static bool trusted_peer(void *ctx, uint64_t peer, uint64_t epoch,
                          uint32_t radius) {
    fixture *f=(fixture *)ctx;
    return f->near_ok && peer==202 && epoch==f->snapshot.peer_epoch &&
           radius==RP_V133_MAX_INTERACT_CM;
}
static bool channel(void *ctx) {return ((fixture *)ctx)->channel;}
static bool send(void *ctx,const rp_v133_action *action) {
    (void)ctx; (void)action; return false;
}
static void observe(void *ctx,uint64_t sender,rp_v133_interaction_kind kind) {
    fixture *f=(fixture *)ctx;
    assert(sender==202 && (kind==RP_V133_GREET || kind==RP_V133_DOCUMENTS));
    ++f->observations;
    if (f->stop_on_observe) rp_v133_gate_stop(f->gate);
}
static rp_v133_delivery delivery(uint64_t session,uint64_t epoch,uint8_t auth) {
    rp_v133_delivery d={202,session,epoch,auth};
    return d;
}
static void make_wire(uint8_t out[RP_V133_WIRE_BYTES],uint64_t session,
                      uint64_t epoch,uint64_t nonce) {
    rp_v133_action action={session,101,nonce,epoch,RP_V133_GREET};
    assert(rp_v133_wire_encode(&action,out,RP_V133_WIRE_BYTES));
}
int main(void) {
    rp_v133_mailbox q;
    rp_v133_gate gate;
    fixture f={0};
    f.snapshot=(rp_v133_snapshot){.session_id=111,.local_player_id=101,
        .peer_epoch=4,.online=1,.opted_in=1};
    f.on_thread=f.channel=f.build_ok=f.near_ok=true;
    f.gate=&gate;
    rp_v133_gate_callbacks cb={attest,game_thread,snapshot,
        trusted_peer,channel,send,observe,&f};
    rp_v133_mailbox_init(&q);
    rp_v133_gate_init(&gate,&cb);
    assert(rp_v133_gate_rebind(&gate));
    uint8_t wire[RP_V133_WIRE_BYTES]={0};
    make_wire(wire,111,4,1);
    rp_v133_delivery meta=delivery(111,4,1);

    /* Never take an unauthenticated or structurally incomplete producer item. */
    assert(!rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES-1));
    meta.authenticated=0;
    assert(!rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    meta.authenticated=1;
    assert(!rp_v133_mailbox_enqueue(&q,NULL,wire,RP_V133_WIRE_BYTES));
    assert(atomic_load(&q.dropped_invalid)==3);

    assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    f.on_thread=false;
    rp_v133_pump_report report={99,99,99};
    assert(!rp_v133_mailbox_pump(&q,&gate,&report));
    assert(!report.processed && q.count==1);
    f.on_thread=true;
    assert(rp_v133_mailbox_pump(&q,&gate,&report));
    assert(report.processed==1 && report.accepted==1 && report.denied==0);
    assert(f.observations==1 && q.count==0);
    assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    assert(rp_v133_mailbox_pump(&q,&gate,&report));
    assert(report.denied==1 && f.observations==1); /* replay */

    /* Nonblocking producer: queue lock contention drops instead of spinning. */
    assert(!atomic_flag_test_and_set_explicit(&q.lock,memory_order_acquire));
    assert(!rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    atomic_flag_clear_explicit(&q.lock,memory_order_release);
    assert(atomic_load(&q.dropped_busy)==1);

    /* 64 item capacity; only 8 parsed on each game frame. */
    for (unsigned i=0;i<RP_V133_QUEUE_CAPACITY;++i) {
        make_wire(wire,111,4,(uint64_t)i+2);
        assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    }
    assert(q.count==RP_V133_QUEUE_CAPACITY);
    assert(!rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    assert(atomic_load(&q.dropped_full)==1);
    assert(rp_v133_mailbox_pump(&q,&gate,&report));
    assert(report.processed==8 && report.accepted==8);
    assert(q.count==56);
    while (q.count) {
        assert(rp_v133_mailbox_pump(&q,&gate,&report));
        assert(report.processed<=RP_V133_QUEUE_FRAME_BUDGET);
        assert(report.denied==0);
    }
    assert(f.observations==65);

    /* Host migration: old epoch packets must be discarded by the gate. */
    make_wire(wire,111,4,66);
    assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    f.snapshot.session_id=999;
    f.snapshot.peer_epoch=5;
    assert(rp_v133_gate_rebind(&gate));
    assert(rp_v133_mailbox_pump(&q,&gate,&report));
    assert(report.processed==1 && report.denied==1);
    assert(f.observations==65);
    assert(rp_v133_mailbox_try_clear(&q));
    meta=delivery(999,5,1);
    make_wire(wire,999,5,1);
    assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    assert(rp_v133_mailbox_pump(&q,&gate,&report));
    assert(report.accepted==1);

    /* Revocation during callback must abort draining remaining items. */
    make_wire(wire,999,5,2);
    assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    make_wire(wire,999,5,3);
    assert(rp_v133_mailbox_enqueue(&q,&meta,wire,RP_V133_WIRE_BYTES));
    f.stop_on_observe=true;
    assert(rp_v133_mailbox_pump(&q,&gate,&report));
    assert(report.processed==1 && !gate.bound && q.count==1);
    assert(!rp_v133_mailbox_pump(&q,&gate,&report));
    assert(rp_v133_mailbox_try_clear(&q) && q.count==0);

    puts("v13.3 bounded diagnostic mailbox: PASS (thread, capacity, migration, replay, consent/revocation)");
    return 0;
}
