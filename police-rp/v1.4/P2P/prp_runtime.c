#include "prp_runtime.h"
#include <string.h>

static int send_msg(const PRP_SendCallbacks *tx,uint64_t to,const PRP_Msg *m){
    if(!tx||!tx->send)return 0;
    uint8_t bytes[PRP_WIRE_SIZE];
    if(!prp_encode(bytes,m))return 0;
    return tx->send(tx->ud,to,bytes,PRP_WIRE_SIZE)==1;
}
void prp_runtime_init(PRP_Runtime *r,uint64_t session,uint64_t local,
                      uint64_t host,uint8_t is_host){
    if(!r)return;
    memset(r,0,sizeof(*r));r->session_id=session;
    r->local_id=local;r->host_id=host;r->is_host=(is_host!=0);
    if(r->is_host)prp_host_init(&r->host,session,host);
    prp_client_init(&r->client,session,local,host);
}
static int context_ok(const PRP_Runtime *r,const PRP_TransportContext *ctx){
    return r&&ctx&&ctx->channel_authenticated&&ctx->session_verified&&
           r->session_id&&r->session_id==ctx->session_id&&
           r->local_id==ctx->local_player_id&&r->host_id==ctx->host_player_id;
}
static int process_local(PRP_Runtime *r,const PRP_Msg *m,
                         const PRP_TransportContext *ctx){
    PRP_TransportContext v=*ctx;
    v.trusted_sender_id=r->local_id;
    return prp_host_receive(&r->host,&v,m,NULL)==PRP_ACCEPTED;
}
int prp_runtime_consent(PRP_Runtime *r,uint8_t enable,
                        const PRP_TransportContext *ctx,
                        const PRP_SendCallbacks *send){
    if(!context_ok(r,ctx)||enable>1)return 0;
    PRP_Msg m={.op=PRP_OP_CONSENT,.session_id=r->session_id,
         .sender_id=r->local_id,.target_id=r->local_id,
         .seq=++r->next_seq,.issued_ms=ctx->monotonic_ms,.consent=enable};
    if(r->is_host){
        if(!process_local(r,&m,ctx))return 0;
    }else if(!send_msg(send,r->host_id,&m))return 0;
    r->local_opt_in=enable;
    /* Local controls must be released immediately on opt-out even when no
       valid host packet comes back. Actual game callbacks release on tick. */
    return 1;
}
PRP_Outcome prp_runtime_action(PRP_Runtime *r,uint8_t op,uint64_t target,
                                uint32_t jail_ms,
                                const PRP_TransportContext *ctx,
                                const PRP_SendCallbacks *send){
    if(!context_ok(r,ctx))return PRP_ERR_SESSION;
    if(!r->local_opt_in)return PRP_ERR_CONSENT;
    if(op<PRP_OP_CUFF||op>PRP_OP_RELEASE||!target||target==r->local_id)
        return PRP_ERR_PACKET;
    PRP_Msg m={.op=op,.session_id=r->session_id,.sender_id=r->local_id,
        .target_id=target,.seq=++r->next_seq,.issued_ms=ctx->monotonic_ms,
        .jail_ms=jail_ms,.consent=1};
    if(r->is_host){
        PRP_TransportContext v=*ctx;v.trusted_sender_id=r->local_id;
        return prp_host_receive(&r->host,&v,&m,NULL);
    }
    return send_msg(send,r->host_id,&m)?PRP_SENT_PENDING:PRP_ERR_AUTH;
    /* A successful send is NOT an accepted arrest. Host may deny the request. */
}
PRP_Outcome prp_runtime_receive(PRP_Runtime *r,const uint8_t *wire,size_t n,
                                 const PRP_TransportContext *ctx,
                                 const PR_EngineView *view){
    if(!context_ok(r,ctx))return PRP_ERR_SESSION;
    PRP_Msg m;
    if(!prp_decode(&m,wire,n))return PRP_ERR_PACKET;
    if(r->is_host)return prp_host_receive(&r->host,ctx,&m,NULL);
    if(!r->local_opt_in||!view)return PRP_ERR_CONSENT;
    return prp_client_receive_state(&r->client,ctx,&m,view)?
        PRP_ACCEPTED:PRP_ERR_AUTH;
}
void prp_runtime_tick(PRP_Runtime *r,uint64_t now,
                      const PR_EngineView *local_view,
                      const PR_Callbacks *cb,
                      const PRP_SendCallbacks *send){
    if(!r)return;
    /* Never continue a stale session after Online disconnect / host migration.
       The engine must provide its authoritative identity EACH frame. */
    if(!local_view || local_view->abi_version!=PR_ADAPTER_ABI ||
       !local_view->online || !local_view->session_verified ||
       local_view->verified_session_id!=r->session_id ||
       local_view->local_player_id!=r->local_id){
        prp_runtime_stop(r,cb);
        return;
    }
    if(!r->is_host){
        PR_EngineView v=*local_view;
        /* User's consent is local preference; never trust arbitrary packet. */
        v.local_opt_in=(uint8_t)(v.local_opt_in&&r->local_opt_in);
        pr_adapter_tick(&r->client.adapter,&v,cb);
        return;
    }
    prp_host_expire(&r->host,now);
    /* Host is also a player. Never apply a remote player's state to host ped. */
    {
        PR_EngineView v=*local_view;
        v.local_opt_in=(uint8_t)(v.local_opt_in&&r->local_opt_in);
        if(v.session_verified&&v.verified_session_id==r->session_id&&
           v.local_player_id==r->local_id&&v.local_opt_in){
            PRP_Msg local_state;
            if(prp_host_state_for(&r->host,r->local_id,now,&local_state)){
                PR_AuthenticatedStatus status={.abi_version=PR_ADAPTER_ABI,
                     .session_id=r->session_id,.local_player_id=r->local_id,
                     .status=(PR_Status)local_state.status,.authenticated=1};
                (void)pr_adapter_accept(&r->client.adapter,&v,&status);
            }
        }
        pr_adapter_tick(&r->client.adapter,&v,cb);
    }
    if(now<r->last_heartbeat_ms||
       (r->last_heartbeat_ms&&now-r->last_heartbeat_ms<PRP_HEARTBEAT_MS))return;
    r->last_heartbeat_ms=now;
    for(unsigned i=0;i<PRP_MAX_PEERS;i++){
        uint64_t id=r->host.peers[i].player_id;
        if(!id||id==r->local_id)continue;
        PRP_Msg state;
        if(prp_host_state_for(&r->host,id,now,&state))
            (void)send_msg(send,id,&state);
    }
}
void prp_runtime_stop(PRP_Runtime *r,const PR_Callbacks *cb){
    if(!r)return;
    pr_adapter_stop(&r->client.adapter,cb);
    prp_runtime_init(r,0,0,0,0);
}
