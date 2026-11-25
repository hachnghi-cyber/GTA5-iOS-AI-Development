#include "rp_v133_mailbox.h"
#include <assert.h>
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <string.h>

#define PRODUCERS 4
#define MESSAGES_PER_PRODUCER 500

typedef struct {
    rp_v133_mailbox box;
    rp_v133_gate gate;
    rp_v133_snapshot view;
    pthread_t main_thread;
    atomic_uint producers_done;
    atomic_uint enqueue_successes;
    unsigned observed;
} fixture;

typedef struct {
    fixture *f;
    unsigned index;
} producer_ctx;

static bool attest(void *ctx,const char *uuid,const char *sha) {
    (void)ctx;
    return strcmp(uuid,RP_V133_TARGET_UUID)==0 &&
           strcmp(sha,RP_V133_TARGET_SHA256)==0;
}
static bool on_game_thread(void *ctx) {
    fixture *f=(fixture *)ctx;
    return pthread_equal(pthread_self(),f->main_thread)!=0;
}
static bool snapshot(void *ctx,rp_v133_snapshot *out) {
    *out=((fixture *)ctx)->view;
    return true;
}
static bool nearby(void *ctx,uint64_t peer,uint64_t epoch,uint32_t radius) {
    fixture *f=(fixture *)ctx;
    return peer>=201 && peer<201+PRODUCERS &&
           epoch==f->view.peer_epoch && radius==RP_V133_MAX_INTERACT_CM;
}
static bool channel(void *ctx) { (void)ctx;return true; }
static bool no_outbound(void *ctx,const rp_v133_action *action) {
    (void)ctx;(void)action;return false;
}
static void observe(void *ctx,uint64_t sender,rp_v133_interaction_kind kind) {
    fixture *f=(fixture *)ctx;
    assert(pthread_equal(pthread_self(),f->main_thread));
    assert(sender>=201 && sender<201+PRODUCERS && kind==RP_V133_GREET);
    ++f->observed;
}
static void *produce(void *raw) {
    producer_ctx *p=(producer_ctx *)raw;
    for (unsigned i=0;i<MESSAGES_PER_PRODUCER;++i) {
        rp_v133_action action={111,101,(uint64_t)i+1,4,RP_V133_GREET};
        uint8_t wire[RP_V133_WIRE_BYTES];
        assert(rp_v133_wire_encode(&action,wire,sizeof wire));
        rp_v133_delivery meta={201+p->index,111,4,1};
        if (rp_v133_mailbox_enqueue(&p->f->box,&meta,wire,sizeof wire))
            atomic_fetch_add_explicit(&p->f->enqueue_successes,1u,memory_order_relaxed);
    }
    atomic_fetch_add_explicit(&p->f->producers_done,1u,memory_order_release);
    return NULL;
}

int main(void) {
    fixture f={0};
    f.main_thread=pthread_self();
    f.view=(rp_v133_snapshot){.session_id=111,.local_player_id=101,
        .peer_epoch=4,.online=1,.opted_in=1};
    rp_v133_mailbox_init(&f.box);
    rp_v133_gate_callbacks cb={attest,on_game_thread,snapshot,
        nearby,channel,no_outbound,observe,&f};
    rp_v133_gate_init(&f.gate,&cb);
    assert(rp_v133_gate_rebind(&f.gate));
    pthread_t threads[PRODUCERS];
    producer_ctx ctx[PRODUCERS];
    for(unsigned i=0;i<PRODUCERS;++i) {
        ctx[i]=(producer_ctx){&f,i};
        assert(pthread_create(&threads[i],NULL,produce,&ctx[i])==0);
    }
    uint64_t accepted=0,denied=0;
    /* Process on the true creator thread, never in any network worker. */
    while (atomic_load_explicit(&f.producers_done,memory_order_acquire)<PRODUCERS) {
        rp_v133_pump_report report;
        assert(rp_v133_mailbox_pump(&f.box,&f.gate,&report));
        assert(report.processed<=RP_V133_QUEUE_FRAME_BUDGET);
        accepted+=report.accepted;
        denied+=report.denied;
        sched_yield();
    }
    for(unsigned i=0;i<PRODUCERS;++i)
        assert(pthread_join(threads[i],NULL)==0);
    while(f.box.count) {
        rp_v133_pump_report report;
        assert(rp_v133_mailbox_pump(&f.box,&f.gate,&report));
        assert(report.processed && report.processed<=RP_V133_QUEUE_FRAME_BUDGET);
        accepted+=report.accepted;
        denied+=report.denied;
    }
    unsigned pushed=atomic_load(&f.enqueue_successes);
    assert(pushed>0 && pushed<=PRODUCERS*MESSAGES_PER_PRODUCER);
    assert(f.observed==accepted);
    assert(accepted>0);
    assert(accepted+denied==pushed);
    assert(f.box.count==0);
    printf("v13.3 mailbox pthread stress: PASS (%u pushed, %llu accepted, %llu denied, bounded per-frame)\n",
        pushed,(unsigned long long)accepted,(unsigned long long)denied);
    return 0;
}
