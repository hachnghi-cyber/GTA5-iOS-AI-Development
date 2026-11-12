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
    printf("Police RP v0.7 engine binding simulation passed\n");
    return 0;
}
