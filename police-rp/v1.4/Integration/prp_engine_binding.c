#include "prp_engine_binding.h"
#include <string.h>

static int valid(const PRP_GameSnapshot *s) {
    if (!(s && s->abi==PRP_BRIDGE_ABI &&
      s->local.abi_version==PR_ADAPTER_ABI &&
      s->local.online && s->local.session_verified &&
      s->local.verified_session_id && s->local.local_player_id &&
      s->host_player_id && s->peer_count<=PRP_MAX_PEERS &&
      s->channel_authenticated &&
      (s->local_is_host == (s->host_player_id == s->local.local_player_id))))
        return 0;
    /* A trusted snapshot must contain the connected local player and
     * current host. Incomplete peer lists are not sufficient to bind
     * local-ped state or accept authoritative host status packets. */
    int has_local=0,has_host=0;
    for (unsigned i=0; i<s->peer_count; ++i) {
        const PRP_Peer *peer=&s->trusted_peers[i];
        if (!peer->connected) continue;
        if (!peer->player_id) return 0;
        if (peer->player_id==s->local.local_player_id)has_local=1;
        if (peer->player_id==s->host_player_id)has_host=1;
        /* No two connected peers may share one authenticated ID. */
        for (unsigned j=0; j<i; ++j)
            if (s->trusted_peers[j].connected &&
                s->trusted_peers[j].player_id==peer->player_id)
                return 0;
    }
    return has_local && has_host;
}
static PRP_TransportContext context(const PRP_GameBridge *b,uint64_t sender) {
    PRP_TransportContext ctx={0};
    if(!b || !b->active || !b->have_snapshot)return ctx;
    ctx.session_id=b->last.local.verified_session_id;
    ctx.local_player_id=b->last.local.local_player_id;
    ctx.host_player_id=b->last.host_player_id;
    ctx.trusted_sender_id=sender;
    ctx.monotonic_ms=b->last.local.monotonic_ms;
    ctx.session_verified=b->last.local.session_verified;
    ctx.channel_authenticated=b->last.channel_authenticated;
    return ctx;
}
static PRP_SendCallbacks send_cb(PRP_GameBridge *b) {
    PRP_SendCallbacks s={0};
    if(b && b->active && b->have_snapshot) {
        s.send=b->callbacks.send_authenticated;
        s.ud=b->callbacks.userdata;
    }
    return s;
}
void prp_bridge_init(PRP_GameBridge *b,const PRP_EngineCallbacks *cb) {
    if(!b)return;
    memset(b,0,sizeof(*b));
    prp_inbox_init(&b->inbox);
    if(cb)b->callbacks=*cb;
}
void prp_bridge_stop(PRP_GameBridge *b) {
    if(!b)return;
    prp_runtime_stop(&b->runtime,&b->callbacks.local_ped);
    prp_inbox_clear(&b->inbox);
    b->have_snapshot=0;
    b->active=0;
    b->want_opt_in=0;
    b->pending_opt_out=0;
    memset(&b->last,0,sizeof(b->last));
}
void prp_bridge_set_consent(PRP_GameBridge *b,int enable) {
    if(!b)return;
    b->want_opt_in=(enable!=0);
    if(!enable) {
        if(b->active&&b->runtime.local_opt_in) {
            PRP_TransportContext ctx=context(b,b->runtime.local_id);
            PRP_SendCallbacks s=send_cb(b);
            /* Local release must NOT depend on the host receiving a packet.
             * Keep retrying revocation if the authenticated send failed. */
            b->pending_opt_out=(uint8_t)
                !prp_runtime_consent(&b->runtime,0,&ctx,&s);
        }
        b->runtime.local_opt_in=0;
        pr_adapter_stop(&b->runtime.client.adapter,&b->callbacks.local_ped);
    }
}
int prp_bridge_frame(PRP_GameBridge *b) {
    if(!b || !b->callbacks.read_snapshot)return 0;
    PRP_GameSnapshot snap={0};
    if(!b->callbacks.read_snapshot(b->callbacks.userdata,&snap) || !valid(&snap)) {
        prp_bridge_stop(b);
        return 0;
    }
    if(b->active && (b->runtime.session_id!=snap.local.verified_session_id ||
        b->runtime.local_id!=snap.local.local_player_id ||
        b->runtime.host_id!=snap.host_player_id ||
        b->runtime.is_host!=snap.local_is_host))prp_bridge_stop(b);
    if(!b->active) {
        prp_runtime_init(&b->runtime,snap.local.verified_session_id,
                snap.local.local_player_id,snap.host_player_id,snap.local_is_host);
        b->active=1;
    }
    b->last=snap;b->have_snapshot=1;
    if(b->runtime.is_host) {
        /* Prune departed players BEFORE joining/updating current peers.
         * At 32/32 capacity a leave + join in one verified frame otherwise
         * rejects the newcomer until the following frame. Removal also
         * clears consent, replay counters and restraints of departed IDs. */
        for(unsigned i=0;i<PRP_MAX_PEERS;i++) {
            uint64_t id=b->runtime.host.peers[i].player_id;
            if(!id)continue;
            int present=0;
            for(unsigned k=0;k<snap.peer_count;k++)
                if(snap.trusted_peers[k].connected &&
                   snap.trusted_peers[k].player_id==id)
                    {present=1;break;}
            if(!present)(void)prp_host_remove_peer(&b->runtime.host,id);
        }
        for(unsigned i=0;i<snap.peer_count;i++) {
            const PRP_Peer *p=&snap.trusted_peers[i];
            if(!p->connected)continue;
            /* Snapshot identity was validated above; the host must never
             * silently accept partial membership when building RP state.
             * Engine-supplied opt_in is ignored by prp_host_update_peer. */
            if(!prp_host_update_peer(&b->runtime.host,p)) {
                prp_bridge_stop(b);
                return 0;
            }
        }
    }
    PRP_TransportContext ctx=context(b,snap.local.local_player_id);
    PRP_SendCallbacks s=send_cb(b);
    if(b->pending_opt_out) {
        /* Revoke on a valid, engine-attested frame. Never opt back in before
         * the authenticated carrier has accepted the revoke send. This
         * is NOT proof that the host applied it; protocol ACK is pending. */
        if(prp_runtime_consent(&b->runtime,0,&ctx,&s))
            b->pending_opt_out=0;
        b->runtime.local_opt_in=0;
    }
    if(!b->pending_opt_out && b->runtime.local_opt_in!=b->want_opt_in) {
        (void)prp_runtime_consent(&b->runtime,b->want_opt_in,&ctx,&s);
    }
    /* Consume only on the verified game thread; do not let transport threads
     * touch PRP_Runtime or GTA natives. Limit per-frame work under packet flood. */
    for(unsigned n=0;n<PRP_INBOX_FRAME_BUDGET;n++) {
        PRP_Inbound msg;
        if(!prp_inbox_pop(&b->inbox,&msg))break;
        if(msg.trusted_session_id!=snap.local.verified_session_id)continue;
        (void)prp_bridge_receive(b,msg.trusted_sender_id,
                        msg.authenticated_delivery,msg.packet,PRP_WIRE_SIZE);
    }
    PR_EngineView view=snap.local;
    view.local_opt_in=(uint8_t)(b->want_opt_in && b->runtime.local_opt_in);
    prp_runtime_tick(&b->runtime,view.monotonic_ms,&view,
                     &b->callbacks.local_ped,&s);
    return 1;
}
PRP_Outcome prp_bridge_receive(PRP_GameBridge *b,uint64_t sender,
                               uint8_t authenticated_delivery,
                               const uint8_t *data,size_t n) {
    if(!b || !b->active || !b->have_snapshot || !sender)
        return PRP_ERR_SESSION;
    /* Transport adapter must supply authenticated_delivery from its own
       authenticated dispatch, not from sender-controlled payload bytes. */
    if(!authenticated_delivery)return PRP_ERR_AUTH;
    PRP_TransportContext ctx=context(b,sender);
    if(!ctx.channel_authenticated)return PRP_ERR_AUTH;
    PR_EngineView v=b->last.local;
    v.local_opt_in=(uint8_t)(b->want_opt_in&&b->runtime.local_opt_in);
    return prp_runtime_receive(&b->runtime,data,n,&ctx,&v);
}
PRP_Outcome prp_bridge_arrest(PRP_GameBridge *b,uint8_t op,
                              uint64_t target,uint32_t jail_ms) {
    if(!b || !b->active || !b->have_snapshot)return PRP_ERR_SESSION;
    if(!b->want_opt_in || !b->runtime.local_opt_in)return PRP_ERR_CONSENT;
    if(!pr_adapter_can_arrest(&b->runtime.client.adapter,&b->last.local)) {
        /* local_opt_in must also agree with current local user consent */
        return PRP_ERR_POLICE;
    }
    PRP_TransportContext ctx=context(b,b->runtime.local_id);
    PRP_SendCallbacks s=send_cb(b);
    return prp_runtime_action(&b->runtime,op,target,jail_ms,&ctx,&s);
}

int prp_bridge_enqueue(PRP_GameBridge *b,uint64_t trusted_session,
                       uint64_t trusted_sender,uint8_t authenticated,
                       const uint8_t *wire,size_t n) {
    if(!b)return 0;
    return prp_inbox_push(&b->inbox,trusted_session,trusted_sender,
                          authenticated,wire,n);
}
