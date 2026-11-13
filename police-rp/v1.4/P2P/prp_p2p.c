#include "prp_p2p.h"
#include <math.h>
#include <string.h>

static void w32(uint8_t *p,uint32_t v) {for(int i=3;i>=0;--i){p[i]=(uint8_t)v;v>>=8;}}
static void w64(uint8_t *p,uint64_t v) {for(int i=7;i>=0;--i){p[i]=(uint8_t)v;v>>=8;}}
static uint32_t r32(const uint8_t *p) {uint32_t v=0;for(int i=0;i<4;i++)v=(v<<8)|p[i];return v;}
static uint64_t r64(const uint8_t *p) {uint64_t v=0;for(int i=0;i<8;i++)v=(v<<8)|p[i];return v;}
static int valid_op(uint8_t op) {return op>=PRP_OP_CONSENT && op<=PRP_OP_STATE;}
static int valid_status(uint8_t s){return s<=PR_JAILED;}
int prp_encode(uint8_t out[PRP_WIRE_SIZE],const PRP_Msg *m){
    if(!out||!m||!valid_op(m->op)||!valid_status(m->status)||m->consent>1||
       !m->session_id||!m->sender_id||!m->seq||m->jail_ms>PRP_MAX_JAIL_MS)return 0;
    memset(out,0,PRP_WIRE_SIZE);
    memcpy(out,"PRP6",4);out[4]=PRP_VERSION;out[5]=m->op;
    w64(out+8,m->session_id);w64(out+16,m->sender_id);w64(out+24,m->target_id);
    w32(out+32,m->seq);w32(out+36,m->generation);w64(out+40,m->issued_ms);
    w32(out+48,m->jail_ms);out[52]=m->status;out[53]=m->consent;
    return 1;
}
int prp_decode(PRP_Msg *m,const uint8_t *in,size_t n){
    if(!m||!in||n!=PRP_WIRE_SIZE||memcmp(in,"PRP6",4)||in[4]!=PRP_VERSION||
       !valid_op(in[5])||in[6]||in[7]||in[54]||in[55]||in[52]>PR_JAILED||
       in[53]>1)return 0;
    PRP_Msg tmp={0};tmp.op=in[5];tmp.session_id=r64(in+8);
    tmp.sender_id=r64(in+16);tmp.target_id=r64(in+24);
    tmp.seq=r32(in+32);tmp.generation=r32(in+36);
    tmp.issued_ms=r64(in+40);tmp.jail_ms=r32(in+48);
    tmp.status=in[52];tmp.consent=in[53];
    if(!tmp.session_id||!tmp.sender_id||!tmp.seq||tmp.jail_ms>PRP_MAX_JAIL_MS)return 0;
    *m=tmp;return 1;
}
static int newer(uint32_t a,uint32_t b){return a!=b && (int32_t)(a-b)>0;}
static int idx(const PRP_Host *h,uint64_t id){
    if(!h||!id)return -1;
    for(int i=0;i<(int)PRP_MAX_PEERS;i++)if(h->peers[i].player_id==id)return i;
    return -1;
}
static int location_fresh(const PRP_Peer *p,uint64_t now){
    return p->position_verified&&now>=p->last_position_ms&&
        now-p->last_position_ms<=PRP_POSITION_TTL_MS&&
        isfinite(p->x)&&isfinite(p->y)&&isfinite(p->z);
}
static int close_enough(const PRP_Peer *a,const PRP_Peer *b,float r){
    double x=(double)a->x-b->x,y=(double)a->y-b->y,z=(double)a->z-b->z;
    return x*x+y*y+z*z<=(double)r*r;
}
/* Read-only target proposal for a host-controlled player interaction menu.
   The host MUST still authorize a subsequent PRP_OP_CUFF using fresh state. */
int prp_host_find_nearest_cuff_target(const PRP_Host *h,uint64_t officer_id,
                                      uint64_t now,uint64_t *target_id){
    if(!target_id)return 0;
    *target_id=0;
    if(!h||!h->session_id||!h->host_id)return 0;
    int officer_index=idx(h,officer_id);
    if(officer_index<0)return 0;
    const PRP_Peer *officer=&h->peers[officer_index];
    /* Eligibility is rechecked on the host even if the native police job
       remains active while the officer is personally restrained. */
    if(h->states[officer_index].status!=PR_FREE)return 0;
    if(!officer->connected||!officer->opt_in||!officer->job_verified||
       !officer->on_shift||officer->native_job<0||officer->native_job>2||
       !location_fresh(officer,now))return 0;

    const double radius_sq=(double)PRP_CUFF_RADIUS_M*PRP_CUFF_RADIUS_M;
    double nearest_sq=radius_sq;
    uint64_t nearest_id=0;
    for(unsigned i=0;i<PRP_MAX_PEERS;i++){
        const PRP_Peer *candidate=&h->peers[i];
        if(candidate->player_id==0||candidate->player_id==officer_id||
           !candidate->connected||!candidate->opt_in||
           h->states[i].status!=PR_FREE||
           !location_fresh(candidate,now))continue;
        double dx=(double)candidate->x-officer->x;
        double dy=(double)candidate->y-officer->y;
        double dz=(double)candidate->z-officer->z;
        double distance_sq=dx*dx+dy*dy+dz*dz;
        if(distance_sq<=radius_sq &&
           (!nearest_id||distance_sq<nearest_sq||
            (distance_sq==nearest_sq&&candidate->player_id<nearest_id))){
            nearest_sq=distance_sq;
            nearest_id=candidate->player_id;
        }
    }
    *target_id=nearest_id;
    return nearest_id!=0;
}

static void set_free(PRP_Host *h,int t){
    if(t<0)return;
    PRP_TargetState *s=&h->states[t];
    if(s->status!=PR_FREE||s->officer_id||s->release_at_ms){
        s->status=PR_FREE;s->officer_id=0;s->release_at_ms=0;s->generation++;
    }
}
/* Officer authority ends on duty loss, opt-out or disconnection.
   Cuff/escort are temporary and must fail open. A completed jail sentence
   belongs to the session, not to the departed officer: preserve its timer
   but orphan the officer reference so a RECYCLED numeric player ID cannot
   inherit the ability to release that prisoner. With officer_id=0, the
   original host state machine permits timer expiry, not manual RELEASE;
   an authenticated identity-generation contract is required for transfer. */
static void revoke_officer_authority(PRP_Host *h,uint64_t player_id){
    if(!h||!player_id)return;
    for(int k=0;k<(int)PRP_MAX_PEERS;k++){
        PRP_TargetState *s=&h->states[k];
        if(s->officer_id!=player_id)continue;
        if(s->status==PR_CUFFED||s->status==PR_ESCORTED){
            set_free(h,k);
        }else if(s->status==PR_JAILED){
            s->officer_id=0;
            s->generation++;
        }
    }
}
void prp_host_init(PRP_Host *h,uint64_t session,uint64_t host){
    if(!h)return;
    memset(h,0,sizeof(*h));h->session_id=session;h->host_id=host;
}
int prp_host_update_peer(PRP_Host *h,const PRP_Peer *trusted){
    if(!h||!trusted||!trusted->player_id)return 0;
    int i=idx(h,trusted->player_id);
    if(i<0){for(int k=0;k<(int)PRP_MAX_PEERS;k++)if(!h->peers[k].player_id){i=k;h->peer_count++;break;}}
    if(i<0)return 0;
    const uint8_t previous_opt=h->peers[i].opt_in;
    h->peers[i]=*trusted;
    h->peers[i].opt_in=previous_opt; /* consent exclusively from authenticated packet */
    if(!trusted->connected) {
        prp_host_remove_peer(h,trusted->player_id);
        return 1;
    }
    /* v0.9: A police officer ending the native GTA work shift must no longer
       keep another player temporarily cuffed or escorted. Preserve completed
       jail sentences until expiry; they are owned by the RP session, not an
       active officer. Treat loss of authoritative job attestation as off duty.
       Never trust a peer-supplied job flag: trusted is engine-sourced only. */
    if (!trusted->job_verified || !trusted->on_shift ||
        trusted->native_job < 0 || trusted->native_job > 2) {
        revoke_officer_authority(h,trusted->player_id);
    }
    return 1;
}
int prp_host_remove_peer(PRP_Host *h,uint64_t id){
    int i=idx(h,id);if(i<0)return 0;
    revoke_officer_authority(h,id);
    memset(&h->peers[i],0,sizeof(h->peers[i]));
    memset(&h->states[i],0,sizeof(h->states[i]));
    h->last_client_seq[i]=0;
    if(h->peer_count)h->peer_count--;
    return 1;
}
static void fail(PRP_HostResult *r,PRP_Outcome e){if(r)r->outcome=e;}
static PRP_Outcome finish(PRP_HostResult *r,PRP_Outcome e){fail(r,e);return e;}
PRP_Outcome prp_host_receive(PRP_Host *h,const PRP_TransportContext *ctx,
                             const PRP_Msg *m,PRP_HostResult *result){
    if(result)memset(result,0,sizeof(*result));
    if(!h||!ctx||!m||!valid_op(m->op)||m->op==PRP_OP_STATE)
        return finish(result,PRP_ERR_PACKET);
    if(!ctx->channel_authenticated||!ctx->session_verified||
       !ctx->trusted_sender_id||ctx->trusted_sender_id!=m->sender_id)
        return finish(result,PRP_ERR_AUTH);
    if(!h->session_id||h->session_id!=ctx->session_id||
       h->session_id!=m->session_id||ctx->local_player_id!=h->host_id||
       ctx->host_player_id!=h->host_id)
        return finish(result,PRP_ERR_SESSION);
    int i=idx(h,m->sender_id);
    if(i<0||!h->peers[i].connected)return finish(result,PRP_ERR_PEER);
    if(!m->seq || (h->last_client_seq[i]&&!newer(m->seq,h->last_client_seq[i])))
        return finish(result,PRP_ERR_REPLAY);
    /* Validly received events consume sequence even if denied. */
    h->last_client_seq[i]=m->seq;
    if(m->op==PRP_OP_CONSENT){
        /* Consent may only concern the authenticated sender, not a target. */
        if(m->target_id!=m->sender_id)
            return finish(result,PRP_ERR_PACKET);
        h->peers[i].opt_in=(m->consent==1);
        if(!m->consent){
            set_free(h,i);
            revoke_officer_authority(h,m->sender_id);
        }
        if(result){result->target_id=m->sender_id;result->target_state=h->states[i];}
        return finish(result,PRP_ACCEPTED);
    }
    PRP_Peer *officer=&h->peers[i];
    if(!officer->opt_in)return finish(result,PRP_ERR_CONSENT);
    if(!officer->job_verified||!officer->on_shift||
       officer->native_job<0||officer->native_job>2)
        return finish(result,PRP_ERR_POLICE);
    /* A cuffed/escorted/jailed officer has no police-action authority.
       Consent is processed above so explicit opt-out still releases this
       player's own restrictions. Never trust only the native job flag. */
    if(h->states[i].status!=PR_FREE)
        return finish(result,PRP_ERR_STATE);
    int t=idx(h,m->target_id);
    if(t<0||t==i||!h->peers[t].connected)return finish(result,PRP_ERR_PEER);
    PRP_Peer *target=&h->peers[t];
    if(!target->opt_in)return finish(result,PRP_ERR_CONSENT);
    PRP_TargetState *s=&h->states[t];
    if(s->status!=PR_FREE&&s->officer_id!=m->sender_id)
        return finish(result,PRP_ERR_STATE);
    if(m->op==PRP_OP_CUFF||m->op==PRP_OP_ESCORT){
        float range=m->op==PRP_OP_CUFF?PRP_CUFF_RADIUS_M:PRP_ESCORT_RADIUS_M;
        if(!location_fresh(officer,ctx->monotonic_ms)||
           !location_fresh(target,ctx->monotonic_ms)||
           !close_enough(officer,target,range))
            return finish(result,PRP_ERR_DISTANCE);
    }
    switch(m->op){
    case PRP_OP_CUFF:
        if(s->status!=PR_FREE)return finish(result,PRP_ERR_STATE);
        s->status=PR_CUFFED;s->officer_id=m->sender_id;s->release_at_ms=0;break;
    case PRP_OP_UNCUFF:
        if(s->status!=PR_CUFFED&&s->status!=PR_ESCORTED)return finish(result,PRP_ERR_STATE);
        set_free(h,t);break;
    case PRP_OP_ESCORT:
        if(s->status!=PR_CUFFED)return finish(result,PRP_ERR_STATE);
        s->status=PR_ESCORTED;break;
    case PRP_OP_JAIL:
        if(s->status!=PR_ESCORTED||m->jail_ms<60000||m->jail_ms>PRP_MAX_JAIL_MS)
            return finish(result,PRP_ERR_STATE);
        if(!officer->station_verified||!target->station_verified||
           !location_fresh(officer,ctx->monotonic_ms)||
           !location_fresh(target,ctx->monotonic_ms)||
           !close_enough(officer,target,PRP_ESCORT_RADIUS_M))
            return finish(result,PRP_ERR_ZONE);
        if(UINT64_MAX-ctx->monotonic_ms<m->jail_ms)return finish(result,PRP_ERR_STATE);
        s->status=PR_JAILED;
        s->release_at_ms=ctx->monotonic_ms+m->jail_ms;break;
    case PRP_OP_RELEASE:
        if(s->status!=PR_JAILED)return finish(result,PRP_ERR_STATE);
        set_free(h,t);break;
    default:return finish(result,PRP_ERR_PACKET);
    }
    if(m->op!=PRP_OP_UNCUFF&&m->op!=PRP_OP_RELEASE)s->generation++;
    if(result){result->target_id=m->target_id;result->target_state=*s;}
    return finish(result,PRP_ACCEPTED);
}
void prp_host_expire(PRP_Host *h,uint64_t now){
    if(!h)return;
    for(int i=0;i<(int)PRP_MAX_PEERS;i++){
        PRP_TargetState *s=&h->states[i];
        if(s->status==PR_JAILED && now>=s->release_at_ms)set_free(h,i);
    }
}
int prp_host_state_for(PRP_Host *h,uint64_t target_id,
                       uint64_t now,PRP_Msg *out){
    int i=idx(h,target_id);
    if(i<0||!out||!h->peers[i].connected||!h->peers[i].opt_in)return 0;
    prp_host_expire(h,now);
    PRP_TargetState *s=&h->states[i];
    uint32_t remaining=0;
    if(s->status==PR_JAILED&&s->release_at_ms>now){
        uint64_t rem=s->release_at_ms-now;
        remaining=rem>PRP_MAX_JAIL_MS?PRP_MAX_JAIL_MS:(uint32_t)rem;
    }
    *out=(PRP_Msg){.op=PRP_OP_STATE,.session_id=h->session_id,
       .sender_id=h->host_id,.target_id=target_id,.seq=++h->send_seq,
       .generation=s->generation,.issued_ms=now,.jail_ms=remaining,
       .status=(uint8_t)s->status,.consent=1};
    if(!out->seq)out->seq=++h->send_seq;
    return 1;
}
void prp_client_init(PRP_Client *c,uint64_t session,uint64_t local,uint64_t host){
    if(!c)return;
    memset(c,0,sizeof(*c));
    c->session_id=session;c->local_id=local;c->expected_host_id=host;
    pr_adapter_init(&c->adapter);
}
int prp_client_receive_state(PRP_Client *c,const PRP_TransportContext *ctx,
                             const PRP_Msg *m,const PR_EngineView *v){
    if(!c||!ctx||!m||!v||m->op!=PRP_OP_STATE||!ctx->session_verified||
       !ctx->channel_authenticated||!v->session_verified||!v->local_opt_in||
       !ctx->trusted_sender_id||ctx->trusted_sender_id!=c->expected_host_id||
       ctx->host_player_id!=c->expected_host_id||m->sender_id!=c->expected_host_id||
       m->session_id!=c->session_id||ctx->session_id!=c->session_id||
       m->target_id!=c->local_id||ctx->local_player_id!=c->local_id||
       v->verified_session_id!=c->session_id||
       v->local_player_id!=c->local_id||!m->consent||!valid_status(m->status)||
       !m->seq||(c->last_seq&&!newer(m->seq,c->last_seq)))return 0;
    PR_AuthenticatedStatus s={.abi_version=PR_ADAPTER_ABI,
       .session_id=c->session_id,.local_player_id=c->local_id,
       .status=(PR_Status)m->status,.authenticated=1};
    if(!pr_adapter_accept(&c->adapter,v,&s))return 0;
    c->last_seq=m->seq;return 1;
}
