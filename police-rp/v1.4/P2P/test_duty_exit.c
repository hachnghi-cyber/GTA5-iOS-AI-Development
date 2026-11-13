#include "prp_p2p.h"
#include <assert.h>
#include <stdio.h>

/* Regression: leaving native police shift releases temporary restraints,
 * but an already-final jail sentence stays valid until its expiry. */
static PRP_Peer peer(uint64_t id, int job, int duty, float x) {
    PRP_Peer p={0};
    p.player_id=id;p.connected=1;p.job_verified=1;
    p.native_job=job;p.on_shift=(uint8_t)duty;
    p.position_verified=1;p.last_position_ms=1000;
    p.x=x;p.station_verified=1;
    return p;
}
static PRP_TransportContext ctx(uint64_t sender) {
    PRP_TransportContext t={0};
    t.session_id=1234;t.local_player_id=10;t.host_player_id=10;
    t.trusted_sender_id=sender;t.monotonic_ms=1000;
    t.channel_authenticated=1;t.session_verified=1;
    return t;
}
static PRP_Msg msg(int op,uint64_t sender,uint64_t target,uint32_t seq) {
    PRP_Msg m={0};
    m.op=(uint8_t)op;m.sender_id=sender;m.target_id=target;
    m.session_id=1234;m.issued_ms=1000;m.seq=seq;m.consent=1;
    return m;
}
int main(void) {
    PRP_Host h;prp_host_init(&h,1234,10);
    PRP_Peer officer=peer(10,0,1,0),subject=peer(20,-1,0,2);
    assert(prp_host_update_peer(&h,&officer));
    assert(prp_host_update_peer(&h,&subject));
    PRP_TransportContext c=ctx(10);
    PRP_Msg op=msg(PRP_OP_CONSENT,10,10,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c.trusted_sender_id=20;op=msg(PRP_OP_CONSENT,20,20,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c.trusted_sender_id=10;
    op=msg(PRP_OP_CUFF,10,20,2);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[1].status==PR_CUFFED);
    uint32_t generation=h.states[1].generation;
    officer.on_shift=0;
    assert(prp_host_update_peer(&h,&officer));
    assert(h.states[1].status==PR_FREE && h.states[1].generation==generation+1);
    assert(h.peers[1].opt_in);
    /* No more arrests when off shift. */
    op=msg(PRP_OP_CUFF,10,20,3);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ERR_POLICE);
    officer.on_shift=1;
    assert(prp_host_update_peer(&h,&officer));
    op=msg(PRP_OP_CUFF,10,20,4);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_ESCORT,10,20,5);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    /* Losing verified duty from the engine must fail open. */
    officer.job_verified=0;
    assert(prp_host_update_peer(&h,&officer));
    assert(h.states[1].status==PR_FREE);
    officer.job_verified=1;
    assert(prp_host_update_peer(&h,&officer));
    op=msg(PRP_OP_CUFF,10,20,6);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_ESCORT,10,20,7);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_JAIL,10,20,8);op.jail_ms=60000;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[1].status==PR_JAILED);
    officer.on_shift=0;
    assert(prp_host_update_peer(&h,&officer));
    assert(h.states[1].status==PR_JAILED);
    assert(h.states[1].officer_id==0); /* stale job cannot retain release authority */
    prp_host_expire(&h,61000);
    assert(h.states[1].status==PR_FREE);
    /* A SECONDARY officer (ID 30) disconnects while session HOST (ID 10)
     * remains alive. Jail must NOT be canceled merely because the arresting
     * officer leaves. This differs from the target leaving the session. */
    PRP_Peer host_user=peer(10,-1,0,40), officer2=peer(30,0,1,0);
    prp_host_init(&h,1234,10);
    assert(prp_host_update_peer(&h,&host_user));
    assert(prp_host_update_peer(&h,&officer2));
    assert(prp_host_update_peer(&h,&subject));
    c=ctx(30);
    op=msg(PRP_OP_CONSENT,30,30,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c=ctx(20);op=msg(PRP_OP_CONSENT,20,20,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c=ctx(30);op=msg(PRP_OP_CUFF,30,20,2);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_ESCORT,30,20,3);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_JAIL,30,20,4);op.jail_ms=60000;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[2].status==PR_JAILED && h.states[2].officer_id==30);
    uint64_t jail_deadline=h.states[2].release_at_ms;
    assert(jail_deadline==61000);
    assert(prp_host_remove_peer(&h,30));
    assert(h.states[2].status==PR_JAILED);
    assert(h.states[2].officer_id==0);
    assert(h.states[2].release_at_ms==jail_deadline);
    assert(prp_host_state_for(&h,20,2000,&op));
    assert(op.status==PR_JAILED && op.jail_ms==59000);

    /* A later member reuses numeric ID 30. The old officer's release
     * authority must NOT transfer to the newly connected player. */
    assert(prp_host_update_peer(&h,&officer2));
    c=ctx(30);op=msg(PRP_OP_CONSENT,30,30,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_RELEASE,30,20,2);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ERR_STATE);
    assert(h.states[2].status==PR_JAILED);
    prp_host_expire(&h,61000);
    assert(h.states[2].status==PR_FREE);
    /* Advance the authoritative host clock and refresh verified positions
     * before starting another arrest. Never reuse a stale game timestamp. */
    officer2.last_position_ms=61000;
    subject.last_position_ms=61000;
    assert(prp_host_update_peer(&h,&officer2));
    assert(prp_host_update_peer(&h,&subject));
    c.monotonic_ms=61000;

    /* Transient cuff/escort must instead release immediately when an
     * officer disconnects. The same rule holds for explicit opt-out. */
    op=msg(PRP_OP_CUFF,30,20,3);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(prp_host_remove_peer(&h,30));
    assert(h.states[2].status==PR_FREE);
    assert(prp_host_update_peer(&h,&officer2));
    op=msg(PRP_OP_CONSENT,30,30,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_CUFF,30,20,2);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_ESCORT,30,20,3);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_CONSENT,30,30,4);op.consent=0;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[2].status==PR_FREE);

    /* Re-enrolled officer finishes another jail sentence then opts out.
     * Session owns the jail countdown; the officer loses release rights. */
    op=msg(PRP_OP_CONSENT,30,30,5);op.consent=1;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_CUFF,30,20,6);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_ESCORT,30,20,7);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_JAIL,30,20,8);op.jail_ms=60000;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    op=msg(PRP_OP_CONSENT,30,30,9);op.consent=0;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[2].status==PR_JAILED);
    assert(h.states[2].officer_id==0);
    assert(h.states[2].release_at_ms==121000);
    prp_host_expire(&h,121000);
    assert(h.states[2].status==PR_FREE);

    /* The prisoner leaving the session still clears their own jail state. */
    prp_host_init(&h,1234,10);
    assert(prp_host_update_peer(&h,&subject));
    h.states[0].status=PR_JAILED;
    h.states[0].officer_id=30;
    h.states[0].release_at_ms=61000;
    assert(prp_host_remove_peer(&h,20));
    assert(h.peer_count==0 && h.states[0].status==PR_FREE);

    /* The native GTA work flag stays valid even while the officer is
     * personally restrained. Host must NEVER authorize police actions by
     * a cuffed, escorted or jailed officer. Consent remains allowed so the
     * officer can explicitly opt out to release their own local controls. */
    PRP_Peer captain=peer(10,0,1,0), backup=peer(30,0,1,2);
    PRP_Peer civilian=peer(20,-1,0,1);
    prp_host_init(&h,1234,10);
    assert(prp_host_update_peer(&h,&captain));
    assert(prp_host_update_peer(&h,&backup));
    assert(prp_host_update_peer(&h,&civilian));
    c=ctx(10);op=msg(PRP_OP_CONSENT,10,10,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c=ctx(30);op=msg(PRP_OP_CONSENT,30,30,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c=ctx(20);op=msg(PRP_OP_CONSENT,20,20,1);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    c=ctx(30);op=msg(PRP_OP_CUFF,30,10,2);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[0].status==PR_CUFFED);
    uint64_t nearest=99;
    assert(!prp_host_find_nearest_cuff_target(&h,10,1000,&nearest));
    assert(nearest==0);
    c=ctx(10);op=msg(PRP_OP_CUFF,10,20,2);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ERR_STATE);
    assert(h.states[2].status==PR_FREE);
    c=ctx(30);op=msg(PRP_OP_ESCORT,30,10,3);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[0].status==PR_ESCORTED);
    c=ctx(10);op=msg(PRP_OP_CUFF,10,20,3);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ERR_STATE);
    c=ctx(30);op=msg(PRP_OP_JAIL,30,10,4);op.jail_ms=60000;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[0].status==PR_JAILED);
    c=ctx(10);op=msg(PRP_OP_CUFF,10,20,4);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ERR_STATE);
    assert(!prp_host_find_nearest_cuff_target(&h,10,1000,&nearest));
    /* A consent revoke is user-controlled and must continue to work while
     * jailed. Re-enrolling after explicit opt-out restores authority only
     * because the host state is now free AND the native duty is verified. */
    op=msg(PRP_OP_CONSENT,10,10,5);op.consent=0;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[0].status==PR_FREE);
    op=msg(PRP_OP_CONSENT,10,10,6);op.consent=1;
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(prp_host_find_nearest_cuff_target(&h,10,1000,&nearest));
    assert(nearest==20);
    op=msg(PRP_OP_CUFF,10,20,7);
    assert(prp_host_receive(&h,&c,&op,NULL)==PRP_ACCEPTED);
    assert(h.states[2].status==PR_CUFFED);

    puts("PoliceRP v0.9 officer off-duty / consent / jail regressions passed");
    return 0;
}
