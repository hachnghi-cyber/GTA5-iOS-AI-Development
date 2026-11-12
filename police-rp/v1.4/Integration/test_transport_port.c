#include "prp_transport_port.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {uint64_t src,dst;uint8_t body[PRP_CANDIDATE_CARRIER_SIZE];size_t n;} Frame;
typedef struct {Frame queue[32];unsigned count;} Bus;
typedef struct {
    PRP_GameSnapshot snapshot;
    Bus *bus;uint64_t id;
    int cuffed,restricted;unsigned calls;
} Peer;
static unsigned checks;
#define CHECK(c) do {assert(c);checks++;} while(0)
static int read_snap(void *v,PRP_GameSnapshot *out){*out=((Peer*)v)->snapshot;return 1;}
static void cuff(void *v,int b){Peer *p=v;p->cuffed=b;p->calls++;}
static void restrict_controls(void *v,int b){((Peer*)v)->restricted=b;}
static int emit(void *v,uint64_t to,const uint8_t *wire,size_t n){
    Peer *p=v;Bus *b=p->bus;
    if(!b || n!=PRP_CANDIDATE_CARRIER_SIZE || b->count>=32)return 0;
    Frame *f=&b->queue[b->count++];f->src=p->id;f->dst=to;
    f->n=n;memcpy(f->body,wire,n);return 1;
}
static PRP_GameSnapshot snapshot(uint64_t id,uint64_t session,uint64_t at){
    PRP_GameSnapshot s={0};s.abi=PRP_BRIDGE_ABI;
    s.local.abi_version=PR_ADAPTER_ABI;
    s.local.local_player_id=id;s.local.verified_session_id=session;
    s.local.monotonic_ms=at;s.local.online=1;s.local.session_verified=1;
    s.local.local_opt_in=1;
    s.local.native_job=id==1?0:-1;s.local.on_shift=id==1;
    s.host_player_id=1;s.local_is_host=id==1;
    s.channel_authenticated=1;s.peer_count=2;
    for(int i=0;i<2;i++){
       PRP_Peer *p=&s.trusted_peers[i];
       p->player_id=(uint64_t)i+1;p->connected=1;p->job_verified=1;
       p->native_job=i==0?0:-1;p->on_shift=i==0;
       p->position_verified=1;p->last_position_ms=at;
       p->x=(float)i;p->y=p->z=0;
    }
    return s;
}
static PRP_EngineCallbacks callbacks(Peer *p){
    PRP_EngineCallbacks c={0};c.userdata=p;c.read_snapshot=read_snap;
    c.local_ped.abi_version=PR_ABI_VERSION;c.local_ped.userdata=p;
    c.local_ped.set_local_cuffed=cuff;
    c.local_ped.set_local_controls_restricted=restrict_controls;return c;
}
static PRP_EventDecision deliver(PRP_TransportPort *target,const Frame *f,
                                  uint64_t session,int auth,int private_route){
    PRP_EventRoute route={.on_separate_police_route=(uint8_t)private_route,
       .authenticated_by_engine=(uint8_t)auth,.trusted_sender_id=f->src,
       .trusted_session_id=session};
    return prp_port_deliver(target,f->body,f->n,&route);
}
int main(void){
    Bus bus={0};
    Peer officer={.bus=&bus,.id=1,.snapshot=snapshot(1,777,1000)};
    Peer civilian={.bus=&bus,.id=2,.snapshot=snapshot(2,777,1000)};
    PRP_TransportPort host,guest;
    PRP_EngineCallbacks hc=callbacks(&officer),gc=callbacks(&civilian);
    prp_port_init(&host,&hc,emit,&officer);
    prp_port_init(&guest,&gc,emit,&civilian);
    CHECK(prp_port_frame(&host));CHECK(prp_port_frame(&guest));
    CHECK(prp_port_arrest(&host,PRP_OP_CUFF,2,0)==PRP_ERR_CONSENT);
    prp_port_consent(&host,1);prp_port_consent(&guest,1);
    CHECK(prp_port_frame(&host));CHECK(prp_port_frame(&guest));
    CHECK(bus.count==1 && bus.queue[0].src==2 && bus.queue[0].dst==1);
    uint8_t stock[PRP_CANDIDATE_CARRIER_SIZE]={0};memcpy(stock,"MPJ2",4);
    PRP_EventRoute stock_route={0};
    CHECK(prp_port_deliver(&host,stock,sizeof(stock),&stock_route)==PRP_PASS_TO_ORIGINAL_GAME);
    CHECK(deliver(&host,&bus.queue[0],777,1,0)==PRP_PASS_TO_ORIGINAL_GAME);
    CHECK(deliver(&host,&bus.queue[0],777,0,1)==PRP_PRIVATE_REJECTED);
    Frame forged=bus.queue[0];forged.src=123;
    CHECK(deliver(&host,&forged,777,1,1)==PRP_PRIVATE_REJECTED);
    CHECK(deliver(&host,&bus.queue[0],777,1,1)==PRP_PRIVATE_ACCEPTED);
    CHECK(!host.bridge.runtime.host.peers[1].opt_in);
    CHECK(prp_port_frame(&host));
    CHECK(host.bridge.runtime.host.peers[1].opt_in);
    CHECK(prp_port_arrest(&host,PRP_OP_CUFF,2,0)==PRP_ACCEPTED);
    officer.snapshot.local.monotonic_ms=1600;
    officer.snapshot.trusted_peers[0].last_position_ms=1600;
    officer.snapshot.trusted_peers[1].last_position_ms=1600;
    CHECK(prp_port_frame(&host));
    CHECK(bus.count==2 && bus.queue[1].src==1 && bus.queue[1].dst==2);
    CHECK(deliver(&guest,&bus.queue[1],777,1,1)==PRP_PRIVATE_ACCEPTED);
    CHECK(!civilian.cuffed); /* no mutation on network receive */
    civilian.snapshot.local.monotonic_ms=1600;
    civilian.snapshot.trusted_peers[0].last_position_ms=1600;
    civilian.snapshot.trusted_peers[1].last_position_ms=1600;
    CHECK(prp_port_frame(&guest));
    CHECK(civilian.cuffed && civilian.restricted);
    CHECK(deliver(&guest,&bus.queue[1],999,1,1)==PRP_PRIVATE_REJECTED);
    civilian.snapshot.channel_authenticated=0;
    CHECK(!prp_port_frame(&guest));
    CHECK(!civilian.cuffed && !civilian.restricted);
    CHECK(prp_port_arrest(&guest,PRP_OP_CUFF,1,0)==PRP_ERR_SESSION);
    prp_port_stop(&host);prp_port_stop(&guest);
    printf("Police RP v1.2: %u carrier-to-game bridge checks passed (mock transport only)\n",checks);
    return 0;
}
