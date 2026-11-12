#include "prp_runtime.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned asserts_count;
#define ENSURE(c) do{assert(c);asserts_count++;}while(0)
typedef struct {uint8_t packet[PRP_WIRE_SIZE];uint64_t to;int sent;} Mailbox;
static int output(void *ud,uint64_t target,const uint8_t *b,size_t n){
    Mailbox *m=(Mailbox*)ud;
    if(!m||n!=PRP_WIRE_SIZE)return 0;
    memcpy(m->packet,b,n);m->to=target;m->sent++;return 1;
}
static int cuffed,restricted;
static void cuff(void *p,int v){(void)p;cuffed=v;}
static void restrict_ctrl(void *p,int v){(void)p;restricted=v;}
static PRP_TransportContext c(uint64_t local,uint64_t sender,uint64_t now){
    PRP_TransportContext t={.session_id=233,.local_player_id=local,
       .host_player_id=1,.trusted_sender_id=sender,.monotonic_ms=now,
       .session_verified=1,.channel_authenticated=1};return t;
}
static PRP_Peer peer(uint64_t id,int job,int shift){
    PRP_Peer p={.player_id=id,.connected=1,.native_job=job,
       .job_verified=1,.position_verified=1,.on_shift=(uint8_t)shift,
       .x=(float)id,.last_position_ms=1000};return p;
}
int main(void){
    PRP_Runtime host,guest;
    prp_runtime_init(&host,233,1,1,1);
    prp_runtime_init(&guest,233,2,1,0);
    PRP_Peer officer=peer(1,0,1),civilian=peer(2,-1,0);
    ENSURE(prp_host_update_peer(&host.host,&officer));
    ENSURE(prp_host_update_peer(&host.host,&civilian));
    Mailbox net={0};PRP_SendCallbacks tx={.send=output,.ud=&net};
    PRP_TransportContext hctx=c(1,1,1000),gctx=c(2,2,1000);
    ENSURE(prp_runtime_consent(&host,1,&hctx,&tx));
    ENSURE(prp_runtime_consent(&guest,1,&gctx,&tx));
    ENSURE(net.sent==1&&net.to==1);
    PRP_TransportContext rxhost=c(1,2,1000);
    ENSURE(prp_runtime_receive(&host,net.packet,PRP_WIRE_SIZE,&rxhost,NULL)==PRP_ACCEPTED);
    ENSURE(host.host.peers[1].opt_in);
    ENSURE(prp_runtime_action(&host,PRP_OP_CUFF,2,0,&hctx,&tx)==PRP_ACCEPTED);
    ENSURE(host.host.states[1].status==PR_CUFFED);
    PR_EngineView gv={.abi_version=PR_ADAPTER_ABI,.monotonic_ms=1001,
       .verified_session_id=233,.local_player_id=2,.online=1,
       .session_verified=1,.local_opt_in=1};
    PR_Callbacks local_cb={.abi_version=PR_ABI_VERSION,
       .set_local_cuffed=cuff,.set_local_controls_restricted=restrict_ctrl};
    PRP_TransportContext rxguest=c(2,1,1001);
    PR_EngineView hv={.abi_version=PR_ADAPTER_ABI,.monotonic_ms=1001,
       .verified_session_id=233,.local_player_id=1,.online=1,
       .session_verified=1,.local_opt_in=1,.native_job=0,.on_shift=1};
    prp_runtime_tick(&host,1001,&hv,NULL,&tx);
    ENSURE(net.sent==2&&net.to==2);
    ENSURE(prp_runtime_receive(&guest,net.packet,PRP_WIRE_SIZE,&rxguest,&gv)==PRP_ACCEPTED);
    prp_runtime_tick(&guest,1001,&gv,&local_cb,&tx);
    ENSURE(cuffed&&restricted);
    /* Host's next snapshot is refreshed, client releases if host vanishes >4s. */
    gv.monotonic_ms=5200;prp_runtime_tick(&guest,5200,&gv,&local_cb,&tx);
    ENSURE(!cuffed&&!restricted);
    hv.monotonic_ms=5300;prp_runtime_tick(&host,5300,&hv,NULL,&tx);
    rxguest.monotonic_ms=5300;gv.monotonic_ms=5300;
    ENSURE(prp_runtime_receive(&guest,net.packet,PRP_WIRE_SIZE,&rxguest,&gv)==PRP_ACCEPTED);
    prp_runtime_tick(&guest,5300,&gv,&local_cb,&tx);
    ENSURE(cuffed&&restricted);
    gctx=c(2,2,5301);
    ENSURE(prp_runtime_consent(&guest,0,&gctx,&tx));
    gv.local_opt_in=0;prp_runtime_tick(&guest,5301,&gv,&local_cb,&tx);
    ENSURE(!cuffed&&!restricted);
    rxhost=c(1,2,5302);
    ENSURE(prp_runtime_receive(&host,net.packet,PRP_WIRE_SIZE,&rxhost,NULL)==PRP_ACCEPTED);
    ENSURE(!host.host.peers[1].opt_in&&host.host.states[1].status==PR_FREE);
    /* Never rearm a lock after opt-out/host migration. */
    prp_runtime_stop(&guest,&local_cb);
    ENSURE(guest.session_id==0&&!cuffed&&!restricted);
    /* Changing Online session must also reset host and stop network sends. */
    hv.verified_session_id=234;
    int sent_before=net.sent;
    prp_runtime_tick(&host,5400,&hv,NULL,&tx);
    ENSURE(host.session_id==0&&net.sent==sent_before);
    puts("Police RP v0.6: end-to-end simulated 2-player game transport OK");
    printf("%u runtime assertions passed\n",asserts_count);
    return 0;
}
