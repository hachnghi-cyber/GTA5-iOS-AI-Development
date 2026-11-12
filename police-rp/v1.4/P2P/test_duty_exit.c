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
    prp_host_expire(&h,61000);
    assert(h.states[1].status==PR_FREE);
    puts("PoliceRP v0.9 officer off-duty / consent / jail regressions passed");
    return 0;
}
