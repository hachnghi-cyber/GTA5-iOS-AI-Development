#include "prp_engine_binding.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {
  PRP_GameSnapshot snapshot;
  uint8_t sent[PRP_WIRE_SIZE];uint64_t to;unsigned sends;
  int cuffed,ctrl;
} Mock;
static int read_snapshot(void *ud,PRP_GameSnapshot *out){*out=((Mock*)ud)->snapshot;return 1;}
static int send_authenticated(void *ud,uint64_t receiver,const uint8_t *p,size_t n){
  Mock *m=ud;if(n!=PRP_WIRE_SIZE)return 0;
  memcpy(m->sent,p,n);m->to=receiver;m->sends++;return 1;
}
static void set_cuffed(void *ud,int value){((Mock*)ud)->cuffed=value;}
static void set_ctrl(void *ud,int value){((Mock*)ud)->ctrl=value;}
static PRP_GameSnapshot snap(uint64_t local,uint64_t host,uint64_t session){
    PRP_GameSnapshot s={0};
    s.abi=PRP_BRIDGE_ABI;s.local.abi_version=PR_ADAPTER_ABI;
    s.local.verified_session_id=session;s.local.local_player_id=local;
    s.local.monotonic_ms=1000;s.local.online=1;s.local.session_verified=1;
    s.local.native_job=0;s.local.on_shift=1;s.local.local_opt_in=1;
    s.host_player_id=host;s.local_is_host=(uint8_t)(local==host);
    s.channel_authenticated=1;s.peer_count=2;
    for(int i=0;i<2;i++) {
        s.trusted_peers[i].player_id=i+1;s.trusted_peers[i].connected=1;
        s.trusted_peers[i].job_verified=1;
        s.trusted_peers[i].native_job=i==0?0:-1;
        s.trusted_peers[i].on_shift=(uint8_t)(i==0);
        s.trusted_peers[i].position_verified=1;
        s.trusted_peers[i].last_position_ms=1000;
        s.trusted_peers[i].x=(float)(i+1);
    }
    return s;
}
static PRP_EngineCallbacks callbacks(Mock *m){
   PRP_EngineCallbacks c={0};c.read_snapshot=read_snapshot;
   c.send_authenticated=send_authenticated;c.local_ped.abi_version=PR_ABI_VERSION;
   c.local_ped.userdata=m;c.local_ped.set_local_cuffed=set_cuffed;
   c.local_ped.set_local_controls_restricted=set_ctrl;c.userdata=m;return c;
}
int main(void){
    Mock hm={0},gm={0};hm.snapshot=snap(1,1,777);gm.snapshot=snap(2,1,777);
    PRP_GameBridge h,g;PRP_EngineCallbacks hc=callbacks(&hm),gc=callbacks(&gm);
    prp_bridge_init(&h,&hc);prp_bridge_init(&g,&gc);
    assert(prp_bridge_frame(&h));assert(prp_bridge_frame(&g));
    assert(prp_bridge_arrest(&h,PRP_OP_CUFF,2,0)==PRP_ERR_CONSENT);
    prp_bridge_set_consent(&h,1);prp_bridge_set_consent(&g,1);
    assert(prp_bridge_frame(&h));assert(prp_bridge_frame(&g));
    assert(gm.sends==1&&gm.to==1);
    assert(!prp_bridge_enqueue(&h,777,2,0,gm.sent,PRP_WIRE_SIZE));
    assert(prp_bridge_receive(&h,2,0,gm.sent,PRP_WIRE_SIZE)==PRP_ERR_AUTH);
    assert(prp_bridge_receive(&h,1,1,gm.sent,PRP_WIRE_SIZE)==PRP_ERR_AUTH);
    /* Network event must be queued, processed during the next GTA game frame. */
    assert(prp_bridge_enqueue(&h,777,2,1,gm.sent,PRP_WIRE_SIZE));
    assert(!h.runtime.host.peers[1].opt_in);
    assert(prp_bridge_frame(&h));
    assert(h.runtime.host.peers[1].opt_in);
    assert(prp_bridge_arrest(&h,PRP_OP_CUFF,2,0)==PRP_ACCEPTED);
    hm.snapshot.local.monotonic_ms=1501;
    assert(prp_bridge_frame(&h));
    assert(hm.sends==1 && hm.to==2);
    assert(prp_bridge_receive(&g,1,1,hm.sent,PRP_WIRE_SIZE)==PRP_ACCEPTED);
    gm.snapshot.local.monotonic_ms=1501;
    assert(prp_bridge_frame(&g) && gm.cuffed && gm.ctrl);
    /* A stale packet from the preceding session can never be processed. */
    assert(prp_bridge_enqueue(&g,776,1,1,hm.sent,PRP_WIRE_SIZE));
    assert(prp_bridge_frame(&g));
    assert(gm.cuffed);
    /* Attestation is dropped => immediately release local controls. */
    gm.snapshot.channel_authenticated=0;
    assert(!prp_bridge_frame(&g) && !gm.cuffed && !gm.ctrl);
    assert(!g.active);
    /* A new session ID must not reuse stale authority/remote state. */
    hm.snapshot.local.verified_session_id=778;
    assert(prp_bridge_frame(&h)&&h.runtime.session_id==778);
    assert(h.runtime.host.peer_count==2);
    assert(!h.runtime.local_opt_in);
    /* Guest consents again, then loses the session while cuffed. */
    gm.snapshot=snap(2,1,888);
    assert(prp_bridge_frame(&g));
    assert(!gm.cuffed && !gm.ctrl);
    prp_bridge_set_consent(&g,0);
    assert(prp_bridge_frame(&g));
    /* Reject ambiguous attested peer identity before mutating host state.
     * Recovery with a later valid snapshot must still be possible. */
    Mock bad={0};bad.snapshot=snap(1,1,999);
    PRP_GameBridge b;PRP_EngineCallbacks bc=callbacks(&bad);
    prp_bridge_init(&b,&bc);
    bad.snapshot.trusted_peers[1].player_id=1; /* duplicate connected ID */
    assert(!prp_bridge_frame(&b) && !b.active);
    assert(b.runtime.host.peer_count==0);
    bad.snapshot=snap(1,1,999);
    bad.snapshot.trusted_peers[1].player_id=0; /* connected, no identity */
    assert(!prp_bridge_frame(&b) && !b.active);
    bad.snapshot=snap(1,1,999);
    assert(prp_bridge_frame(&b) && b.runtime.host.peer_count==2);
    /* A live RP session must not retain consent or queued packets if
     * the next authenticated engine snapshot becomes ambiguous. */
    prp_bridge_set_consent(&b,1);
    assert(prp_bridge_frame(&b) && b.runtime.local_opt_in);
    uint8_t pending[PRP_WIRE_SIZE]={0};
    assert(prp_bridge_enqueue(&b,999,2,1,pending,sizeof(pending)));
    assert(b.inbox.count==1);
    bad.snapshot.trusted_peers[1].player_id=1;
    assert(!prp_bridge_frame(&b) && !b.active);
    assert(b.inbox.count==0 && !b.want_opt_in && !b.runtime.local_opt_in);
    assert(b.runtime.host.peer_count==0);
    /* The user must explicitly opt back in after identity recovery. */
    bad.snapshot=snap(1,1,999);
    assert(prp_bridge_frame(&b) && b.runtime.host.peer_count==2);
    assert(!b.runtime.local_opt_in && !b.want_opt_in);
    prp_bridge_stop(&b);
    /* RP-003: host and local must both exist among connected identities.
     * Invalidating a live guest session drops consent and queued packets. */
    Mock missing={0};missing.snapshot=snap(2,1,1001);
    PRP_GameBridge isolated;PRP_EngineCallbacks mc=callbacks(&missing);
    prp_bridge_init(&isolated,&mc);
    missing.snapshot.trusted_peers[0].connected=0; /* missing host */
    assert(!prp_bridge_frame(&isolated) && !isolated.active);
    missing.snapshot=snap(2,1,1001);
    missing.snapshot.trusted_peers[1].connected=0; /* missing local */
    assert(!prp_bridge_frame(&isolated) && !isolated.active);
    missing.snapshot=snap(2,1,1001);
    missing.snapshot.peer_count=1; /* local omitted by truncated list */
    assert(!prp_bridge_frame(&isolated) && !isolated.active);
    missing.snapshot=snap(2,1,1001);
    assert(prp_bridge_frame(&isolated) && isolated.active);
    prp_bridge_set_consent(&isolated,1);
    assert(prp_bridge_frame(&isolated) && isolated.runtime.local_opt_in);
    /* A missing host must fail open even if the local ped is restrained. */
    PRP_Msg host_state={0};
    host_state.op=PRP_OP_STATE;host_state.session_id=1001;
    host_state.sender_id=1;host_state.target_id=2;
    host_state.seq=1;host_state.consent=1;host_state.status=PR_CUFFED;
    uint8_t host_wire[PRP_WIRE_SIZE];
    assert(prp_encode(host_wire,&host_state));
    assert(prp_bridge_receive(&isolated,1,1,host_wire,sizeof(host_wire))==PRP_ACCEPTED);
    assert(prp_bridge_frame(&isolated) && missing.cuffed && missing.ctrl);
    assert(prp_bridge_enqueue(&isolated,1001,1,1,pending,sizeof(pending)));
    assert(isolated.inbox.count==1);
    missing.snapshot.trusted_peers[0].connected=0;
    assert(!prp_bridge_frame(&isolated) && !isolated.active);
    assert(isolated.inbox.count==0 && !isolated.want_opt_in &&
           !isolated.runtime.local_opt_in && !missing.cuffed && !missing.ctrl);
    missing.snapshot=snap(2,1,1001);
    assert(prp_bridge_frame(&isolated) && isolated.active);
    assert(!isolated.runtime.local_opt_in);
    prp_bridge_stop(&isolated);
    printf("Police RP v0.7 engine binding simulation passed\n");
    return 0;
}
