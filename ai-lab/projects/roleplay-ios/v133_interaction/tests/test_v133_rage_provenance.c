#include "rp_v133_rage_provenance.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#define C RP_RAGE_CANDIDATE_ONLY
#define R RP_RAGE_REJECTED
#define Q RP_RAGE_QUARANTINED
static rp_rage_sample sample(uint64_t gen,uint64_t peer,uint32_t conn,
                             uint8_t slot,int32_t endpoint,uint64_t at) {
    rp_rage_sample s={0};
    s.session_id=345; s.generation=gen; s.peer_id=peer;
    s.event_connection_id=conn; s.netplayer_connection_id=conn;
    s.session_connection_id=(int32_t)conn; s.session_endpoint_id=endpoint;
    s.netplayer_slot=slot; s.observed_at_ms=at;
    s.netplayer_valid=true; s.session_member=true;
    s.origin=RP_RAGE_ORIGIN_REMOTE_ON_NET_EVENT;
    return s;
}
static void test_consistency_does_not_authorize(void) {
    rp_rage_observer o;rp_rage_observer_init(&o);
    assert(rp_rage_scope_begin(&o,345));
    rp_rage_sample s=sample(o.generation,781,77,2,101,1000);
    assert(rp_rage_observe(&o,&s,1010)==C);
    assert(rp_rage_observe(&o,&s,1011)==C);
    assert(o.candidate_count==1 && o.candidates[0].observations==2);
    /* No authenticated/authorization output exists in this struct or API. */
    s.origin=RP_RAGE_ORIGIN_LOCAL_SEND_BUFFER;
    assert(rp_rage_observe(&o,&s,1012)==R);
    s.origin=RP_RAGE_ORIGIN_REMOTE_ON_NET_EVENT;
    s.local_player=true;
    assert(rp_rage_observe(&o,&s,1012)==R);
    s.local_player=false; s.session_member=false;
    assert(rp_rage_observe(&o,&s,1012)==R);
    assert(o.candidate_count==1 && !o.quarantined);
}
static void test_bad_connection_and_stale(void) {
    rp_rage_observer o;rp_rage_observer_init(&o);
    assert(rp_rage_scope_begin(&o,345));
    rp_rage_sample s=sample(o.generation,781,77,2,101,1000);
    s.netplayer_connection_id=76;assert(rp_rage_observe(&o,&s,1010)==R);
    s.netplayer_connection_id=77;s.session_connection_id=-1;
    assert(rp_rage_observe(&o,&s,1010)==R);
    s.session_connection_id=77;s.session_endpoint_id=-1;
    assert(rp_rage_observe(&o,&s,1010)==R);
    s.session_endpoint_id=101;s.netplayer_slot=255;
    assert(rp_rage_observe(&o,&s,1010)==R);
    s.netplayer_slot=2;s.observed_at_ms=1000;
    assert(rp_rage_observe(&o,&s,1251)==R);/* >250ms */
    assert(rp_rage_observe(&o,&s,999)==R);/* from future */
    s.session_id=346;assert(rp_rage_observe(&o,&s,1010)==R);
    assert(!o.candidate_count && !o.quarantined);
}
static void test_remap_and_alias_quarantine(void) {
    rp_rage_observer o;rp_rage_observer_init(&o);
    assert(rp_rage_scope_begin(&o,345));
    rp_rage_sample s=sample(o.generation,781,77,2,101,1000);
    assert(rp_rage_observe(&o,&s,1010)==C);
    rp_rage_sample t=sample(o.generation,922,77,3,102,1011);
    assert(rp_rage_observe(&o,&t,1011)==Q);
    assert(o.quarantined && o.candidate_count==0);
    assert(rp_rage_observe(&o,&s,1012)==R);
    assert(rp_rage_scope_begin(&o,345));/* even same session ID */
    t=sample(o.generation,922,78,3,102,1200);
    assert(rp_rage_observe(&o,&t,1200)==C);
    t.event_connection_id=79;t.netplayer_connection_id=79;
    t.session_connection_id=79;t.observed_at_ms=1201;
    assert(rp_rage_observe(&o,&t,1201)==Q);
}
static void test_migration_rejects_previous_generation(void) {
    rp_rage_observer o;rp_rage_observer_init(&o);
    assert(rp_rage_scope_begin(&o,345));
    rp_rage_sample old=sample(o.generation,781,77,2,101,1000);
    assert(rp_rage_observe(&o,&old,1000)==C);
    uint64_t oldgen=o.generation;
    rp_rage_scope_invalidate(&o);
    assert(!o.active && !o.candidate_count && o.generation!=oldgen);
    assert(rp_rage_observe(&o,&old,1001)==R);
    assert(rp_rage_scope_begin(&o,345));/* reused ID */
    assert(rp_rage_observe(&o,&old,1001)==R);
    old.generation=o.generation;old.observed_at_ms=2000;
    assert(rp_rage_observe(&o,&old,2000)==C);
    assert(rp_rage_observe(&o,&old,1999)==Q);/* clock rollback */
    rp_rage_scope_invalidate(&o);
    assert(!o.active);
}
static void test_full_capacity_and_wrap(void) {
    rp_rage_observer o;rp_rage_observer_init(&o);
    assert(!rp_rage_scope_begin(&o,0));
    assert(rp_rage_scope_begin(&o,345));
    for(unsigned i=0;i<32;i++){
        rp_rage_sample s=sample(o.generation,1000+i,20+i,(uint8_t)i,
                                 (int32_t)(200+i),3000+i);
        assert(rp_rage_observe(&o,&s,3000+i)==C);
    }
    assert(o.candidate_count==32 && !o.quarantined);
    /* A colliding peer/slot fails closed even when capacity reached. */
    rp_rage_sample collision=sample(o.generation,9099,20,5,300,3000);
    assert(rp_rage_observe(&o,&collision,4000)==R);/* stale first */
    collision.observed_at_ms=4000;
    assert(rp_rage_observe(&o,&collision,4000)==Q);
    o.generation=UINT64_MAX;
    assert(!rp_rage_scope_begin(&o,345));
    rp_rage_scope_invalidate(&o);
    assert(o.generation==UINT64_MAX && !o.active);
}
static void test_failed_scope_begin_revokes_previous_session(void) {
    for(unsigned exhausted=0;exhausted<2;exhausted++) {
        rp_rage_observer o;rp_rage_observer_init(&o);
        if(exhausted)o.generation=UINT64_MAX-1;
        assert(rp_rage_scope_begin(&o,345));
        rp_rage_sample old=sample(o.generation,781,77,2,101,1000);
        assert(rp_rage_observe(&o,&old,1000)==C);

        /* A new session-owner callback is an invalidation boundary even if
         * its ID is not ready or the incarnation counter cannot advance. */
        assert(!rp_rage_scope_begin(&o,exhausted ? 345 : 0));
        assert(rp_rage_observe(&o,&old,1001)==R);
        assert(!o.active && !o.session_id && !o.candidate_count && !o.last_now_ms);
        for(unsigned i=0;i<RP_RAGE_OBSERVER_MAX_PEERS;i++)
            assert(!o.candidates[i].peer_id && !o.candidates[i].observations);

        if(exhausted) {
            assert(o.generation==UINT64_MAX);
            assert(!rp_rage_scope_begin(&o,345));
            rp_rage_scope_invalidate(&o);
            assert(o.generation==UINT64_MAX && !o.active);
        } else {
            assert(o.generation>old.generation);
            assert(rp_rage_scope_begin(&o,345)); /* same ID, new incarnation */
            assert(rp_rage_observe(&o,&old,1001)==R);
            rp_rage_sample fresh=sample(o.generation,781,77,2,101,1002);
            assert(rp_rage_observe(&o,&fresh,1002)==C);
        }
    }
    assert(!rp_rage_scope_begin(NULL,345));
}
int main(void) {
    test_consistency_does_not_authorize();
    test_bad_connection_and_stale();
    test_remap_and_alias_quarantine();
    test_migration_rejects_previous_generation();
    test_full_capacity_and_wrap();
    test_failed_scope_begin_revokes_previous_session();
    puts("PASS: RAGE provenance candidates only; failed scope renewal, stale, alias, migration and clock faults denied");
}
