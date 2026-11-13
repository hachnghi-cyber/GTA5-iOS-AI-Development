/* Source-only host regression: 32-player bounds, per-peer consent and
   replay sequence rollover. No network transport or GTA native APIs. */
#include "prp_p2p.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static unsigned assertions;
#define CHECK(condition) do { assert(condition); assertions++; } while (0)

static PRP_Peer snapshot(uint64_t id) {
    PRP_Peer p={0};
    p.player_id=id;
    p.connected=1;
    p.job_verified=1;
    p.native_job=(id==1) ? 0 : 4;
    p.on_shift=(uint8_t)(id==1);
    p.position_verified=1;
    p.last_position_ms=1000;
    p.x=(id==1) ? 0.0f : 1.0f;
    return p;
}
static PRP_TransportContext delivery(uint64_t sender) {
    PRP_TransportContext c={0};
    c.session_id=77;c.local_player_id=1;c.host_player_id=1;
    c.trusted_sender_id=sender;c.monotonic_ms=1000;
    c.session_verified=1;c.channel_authenticated=1;
    return c;
}
static PRP_Msg message(uint8_t op,uint64_t sender,uint64_t target,
                       uint32_t seq,uint8_t consent) {
    PRP_Msg m={0};
    m.op=op;m.session_id=77;m.sender_id=sender;m.target_id=target;
    m.seq=seq;m.issued_ms=1000;m.consent=consent;
    return m;
}
int main(void) {
    PRP_Host host;
    prp_host_init(&host,77,1);

    for (uint64_t id=1;id<=PRP_MAX_PEERS;id++) {
        PRP_Peer p=snapshot(id);
        p.opt_in=1; /* snapshots do not grant consent */
        CHECK(prp_host_update_peer(&host,&p)==1);
    }
    CHECK(host.peer_count==PRP_MAX_PEERS);
    PRP_Peer overflow=snapshot(PRP_MAX_PEERS+1);
    CHECK(prp_host_update_peer(&host,&overflow)==0);
    CHECK(host.peer_count==PRP_MAX_PEERS);
    for (size_t i=0;i<PRP_MAX_PEERS;i++)
        CHECK(host.peers[i].opt_in==0);

    PRP_TransportContext cop=delivery(1),civilian=delivery(2);
    PRP_Msg consent=message(PRP_OP_CONSENT,1,1,UINT32_MAX-1,1);
    CHECK(prp_host_receive(&host,&cop,&consent,NULL)==PRP_ACCEPTED);
    consent=message(PRP_OP_CONSENT,2,2,1,1);
    CHECK(prp_host_receive(&host,&civilian,&consent,NULL)==PRP_ACCEPTED);
    CHECK(host.peers[0].opt_in&&host.peers[1].opt_in);

    PRP_Msg cuff=message(PRP_OP_CUFF,1,2,UINT32_MAX,1);
    CHECK(prp_host_receive(&host,&cop,&cuff,NULL)==PRP_ACCEPTED);
    CHECK(host.states[1].status==PR_CUFFED);
    /* uint32 sequence rollover to 1 is valid, but an old UINT32_MAX is not. */
    PRP_Msg rollover=message(PRP_OP_CONSENT,1,1,1,1);
    CHECK(prp_host_receive(&host,&cop,&rollover,NULL)==PRP_ACCEPTED);
    CHECK(prp_host_receive(&host,&cop,&cuff,NULL)==PRP_ERR_REPLAY);
    CHECK(host.states[1].status==PR_CUFFED);

    /* Disconnect clears restraint and consent without preserving stale IDs. */
    PRP_Peer disconnect=snapshot(2);
    disconnect.connected=0;
    CHECK(prp_host_update_peer(&host,&disconnect)==1);
    CHECK(host.peer_count==PRP_MAX_PEERS-1);
    CHECK(host.states[1].status==PR_FREE);
    CHECK(host.peers[1].player_id==0);
    CHECK(host.peers[1].opt_in==0);

    CHECK(prp_host_update_peer(&host,&overflow)==1);
    CHECK(host.peer_count==PRP_MAX_PEERS);
    CHECK(host.peers[1].player_id==PRP_MAX_PEERS+1);
    CHECK(host.peers[1].opt_in==0);
    CHECK(host.last_client_seq[1]==0);
    printf("Police RP host peer lifecycle: %u assertions passed (32-player capacity, sequence rollover, disconnect)\n",
           assertions);
    return 0;
}
