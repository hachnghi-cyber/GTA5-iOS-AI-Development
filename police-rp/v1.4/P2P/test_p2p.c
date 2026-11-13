#include "prp_p2p.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static unsigned tests;
#define CHECK(x) do{assert(x);tests++;}while(0)
static PRP_TransportContext ctx(uint64_t src,uint64_t now){
    PRP_TransportContext c={.session_id=101,.local_player_id=1,.host_player_id=1,
        .trusted_sender_id=src,.monotonic_ms=now,
        .session_verified=1,.channel_authenticated=1};return c;
}
static PRP_Peer peer(uint64_t id,float x,uint64_t now,int job,int shift){
    PRP_Peer p={.player_id=id,.connected=1,.job_verified=1,.position_verified=1,
        .native_job=job,.on_shift=(uint8_t)shift,.x=x,.y=0,.z=0,
        .last_position_ms=now};return p;
}
static PRP_Msg msg(uint8_t op,uint64_t from,uint64_t to,uint32_t seq){
    PRP_Msg m={.op=op,.session_id=101,.sender_id=from,
        .target_id=to,.seq=seq,.issued_ms=1000,.consent=1};return m;
}
static int restriction,cuff;
static void set_cuffed(void *ctx,int enable){(void)ctx;cuff=enable;}
static void set_restrict(void *ctx,int enable){(void)ctx;restriction=enable;}
int main(void){
    PRP_Host host;prp_host_init(&host,101,1);
    PRP_Peer cop=peer(1,0.0f,1000,0,1),cit=peer(2,2.0f,1000,4,0),guest=peer(3,2.5f,1000,0,0);
    cop.opt_in=cit.opt_in=guest.opt_in=1;/* engine snapshots may NOT grant consent */
    CHECK(prp_host_update_peer(&host,&cop));CHECK(prp_host_update_peer(&host,&cit));
    CHECK(prp_host_update_peer(&host,&guest));
    CHECK(!host.peers[0].opt_in&&!host.peers[1].opt_in);
    PRP_Msg opt=msg(PRP_OP_CONSENT,1,1,1);
    PRP_TransportContext c=ctx(1,1000);
    CHECK(prp_host_receive(&host,&c,&opt,NULL)==PRP_ACCEPTED);
    opt=msg(PRP_OP_CONSENT,2,2,1);c=ctx(2,1000);
    CHECK(prp_host_receive(&host,&c,&opt,NULL)==PRP_ACCEPTED);
    CHECK(host.peers[1].opt_in);
    PRP_Msg cuffmsg=msg(PRP_OP_CUFF,1,2,2);
    PRP_TransportContext fake=ctx(3,1000);
    CHECK(prp_host_receive(&host,&fake,&cuffmsg,NULL)==PRP_ERR_AUTH);
    c=ctx(1,1000);c.session_id=555;
    CHECK(prp_host_receive(&host,&c,&cuffmsg,NULL)==PRP_ERR_SESSION);
    c=ctx(1,1000);
    PRP_HostResult r;
    CHECK(prp_host_receive(&host,&c,&cuffmsg,&r)==PRP_ACCEPTED);
    CHECK(r.target_state.status==PR_CUFFED);
    CHECK(prp_host_receive(&host,&c,&cuffmsg,&r)==PRP_ERR_REPLAY);
    PRP_Msg e=msg(PRP_OP_ESCORT,1,2,3);
    CHECK(prp_host_receive(&host,&c,&e,&r)==PRP_ACCEPTED);
    CHECK(r.target_state.status==PR_ESCORTED);
    PRP_Msg jail=msg(PRP_OP_JAIL,1,2,4);jail.jail_ms=60000;
    CHECK(prp_host_receive(&host,&c,&jail,&r)==PRP_ERR_ZONE);
    cop.station_verified=cit.station_verified=1;
    CHECK(prp_host_update_peer(&host,&cop));CHECK(prp_host_update_peer(&host,&cit));
    /* Both at a station, but different stations / >6m apart: no remote jail. */
    cop.x=900.0f;
    CHECK(prp_host_update_peer(&host,&cop));
    jail.seq=5;
    CHECK(prp_host_receive(&host,&c,&jail,&r)==PRP_ERR_ZONE);
    cop.x=0.0f;
    CHECK(prp_host_update_peer(&host,&cop));
    jail.seq=6;
    CHECK(prp_host_receive(&host,&c,&jail,&r)==PRP_ACCEPTED);
    CHECK(r.target_state.status==PR_JAILED);
    PRP_Msg state;CHECK(prp_host_state_for(&host,2,1001,&state));
    CHECK(state.status==PR_JAILED&&state.jail_ms==59999);
    uint8_t bytes[PRP_WIRE_SIZE];CHECK(prp_encode(bytes,&state));
    PRP_Msg parsed;CHECK(prp_decode(&parsed,bytes,PRP_WIRE_SIZE));
    CHECK(parsed.op==PRP_OP_STATE&&parsed.seq==state.seq);
    CHECK(!prp_decode(&parsed,bytes,PRP_WIRE_SIZE-1));
    bytes[54]=1;CHECK(!prp_decode(&parsed,bytes,PRP_WIRE_SIZE));bytes[54]=0;
    bytes[5]=0xff;CHECK(!prp_decode(&parsed,bytes,PRP_WIRE_SIZE));bytes[5]=state.op;
    bytes[0]='X';CHECK(!prp_decode(&parsed,bytes,PRP_WIRE_SIZE));bytes[0]='P';

    PRP_Client client;prp_client_init(&client,101,2,1);
    PR_EngineView v={.abi_version=PR_ADAPTER_ABI,.monotonic_ms=1001,
       .verified_session_id=101,.local_player_id=2,.online=1,
       .session_verified=1,.local_opt_in=1,.native_job=4};
    PRP_TransportContext hctx=ctx(1,1001);
    hctx.local_player_id=2; /* delivery target is THIS client, not the host */
    PR_Callbacks cb={.abi_version=PR_ABI_VERSION,.set_local_cuffed=set_cuffed,
                    .set_local_controls_restricted=set_restrict};
    PRP_TransportContext wrong_receiver=hctx;
    wrong_receiver.local_player_id=3;
    CHECK(!prp_client_receive_state(&client,&wrong_receiver,&state,&v));
    CHECK(prp_client_receive_state(&client,&hctx,&state,&v));
    pr_adapter_tick(&client.adapter,&v,&cb);CHECK(cuff==1&&restriction==1);
    CHECK(!prp_client_receive_state(&client,&hctx,&state,&v)); /* replay */
    hctx.trusted_sender_id=3;
    CHECK(prp_host_state_for(&host,2,1002,&state));
    CHECK(!prp_client_receive_state(&client,&hctx,&state,&v)); /* spoofed host */
    hctx.trusted_sender_id=1;
    CHECK(prp_client_receive_state(&client,&hctx,&state,&v));
    v.monotonic_ms=6002;pr_adapter_tick(&client.adapter,&v,&cb);
    CHECK(!cuff&&!restriction);/* timeout fail-open */

    prp_host_expire(&host,61001);
    CHECK(host.states[1].status==PR_FREE);
    CHECK(prp_host_state_for(&host,2,61001,&state));
    CHECK(state.status==PR_FREE);
    v.monotonic_ms=61001;
    CHECK(prp_client_receive_state(&client,&hctx,&state,&v));
    pr_adapter_tick(&client.adapter,&v,&cb);
    CHECK(!cuff&&!restriction);

    /* Reconnect and opt out must not carry over cuffs or consent. */
    PRP_Msg optout=msg(PRP_OP_CONSENT,2,2,2);optout.consent=0;
    c=ctx(2,61002);
    CHECK(prp_host_receive(&host,&c,&optout,&r)==PRP_ACCEPTED);
    CHECK(!host.peers[1].opt_in);
    CHECK(!prp_host_state_for(&host,2,61003,&state));
    v.local_opt_in=0;pr_adapter_tick(&client.adapter,&v,&cb);
    CHECK(!cuff&&!restriction);
    opt=msg(PRP_OP_CONSENT,2,2,3);c=ctx(2,62000);
    CHECK(prp_host_receive(&host,&c,&opt,&r)==PRP_ACCEPTED);
    CHECK(prp_host_remove_peer(&host,2));
    CHECK(prp_host_update_peer(&host,&cit));CHECK(!host.peers[1].opt_in);

    /* Officer duty and location validation MUST use engine-authenticated state. */
    prp_host_init(&host,101,1);cop.on_shift=0;
    CHECK(prp_host_update_peer(&host,&cop));CHECK(prp_host_update_peer(&host,&cit));
    opt=msg(PRP_OP_CONSENT,1,1,1);c=ctx(1,1000);
    CHECK(prp_host_receive(&host,&c,&opt,&r)==PRP_ACCEPTED);
    opt=msg(PRP_OP_CONSENT,2,2,1);c=ctx(2,1000);
    CHECK(prp_host_receive(&host,&c,&opt,&r)==PRP_ACCEPTED);
    cuffmsg=msg(PRP_OP_CUFF,1,2,2);c=ctx(1,1000);
    CHECK(prp_host_receive(&host,&c,&cuffmsg,&r)==PRP_ERR_POLICE);
    cop.on_shift=1;cop.x=500;
    CHECK(prp_host_update_peer(&host,&cop));cuffmsg.seq=3;
    CHECK(prp_host_receive(&host,&c,&cuffmsg,&r)==PRP_ERR_DISTANCE);
    cop.x=0;cop.last_position_ms=10;c=ctx(1,5000);
    CHECK(prp_host_update_peer(&host,&cop));cuffmsg.seq=4;
    CHECK(prp_host_receive(&host,&c,&cuffmsg,&r)==PRP_ERR_DISTANCE);

    /* Cross-target consent must never opt in someone else. */
    PRP_Host isolated;prp_host_init(&isolated,101,1);
    CHECK(prp_host_update_peer(&isolated,&cit));
    PRP_Msg forged_consent=msg(PRP_OP_CONSENT,2,3,1);
    PRP_TransportContext isolated_ctx=ctx(2,1000);
    CHECK(prp_host_receive(&isolated,&isolated_ctx,&forged_consent,NULL)==PRP_ERR_PACKET);
    CHECK(!isolated.peers[0].opt_in);

    /* Deterministic malformed packet fuzz: decoder must not crash/overread. */
    uint32_t seed=0x12345678;
    for(int i=0;i<25000;i++){
        uint8_t b[PRP_WIRE_SIZE];
        for(int j=0;j<(int)sizeof(b);j++){
            seed=seed*1664525u+1013904223u;b[j]=(uint8_t)(seed>>24);
        }
        (void)prp_decode(&parsed,b,(size_t)(i%59));
    }
    printf("Police RP v0.6 P2P: %u assertions passed; 25,000 fuzz inputs; no network required\n",tests);
    return 0;
}
