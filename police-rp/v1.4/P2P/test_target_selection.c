/* RP host-only proximity target selection regression.
   No GTA5 imports, sockets or device access: engine-attested state is simulated. */
#include "prp_p2p.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>

static unsigned checks;
#define CHECK(c) do { assert(c); ++checks; } while (0)

static PRP_Peer snapshot(uint64_t id,float x) {
    PRP_Peer p={0};
    p.player_id=id;
    p.connected=1;
    p.job_verified=1;
    p.native_job=(id==1)?0:4;
    p.on_shift=(uint8_t)(id==1);
    p.position_verified=1;
    p.last_position_ms=5000;
    p.x=x;
    return p;
}
static PRP_TransportContext delivery(uint64_t sender) {
    PRP_TransportContext ctx={0};
    ctx.session_id=99;
    ctx.local_player_id=1;
    ctx.host_player_id=1;
    ctx.trusted_sender_id=sender;
    ctx.monotonic_ms=5000;
    ctx.session_verified=1;
    ctx.channel_authenticated=1;
    return ctx;
}
static PRP_Msg message(uint64_t sender,uint64_t target,uint32_t seq,uint8_t op) {
    PRP_Msg m={0};
    m.session_id=99;
    m.sender_id=sender;
    m.target_id=target;
    m.seq=seq;
    m.issued_ms=5000;
    m.op=op;
    m.consent=1;
    return m;
}
static void consent(PRP_Host *host,uint64_t sender) {
    PRP_TransportContext ctx=delivery(sender);
    PRP_Msg m=message(sender,sender,1,PRP_OP_CONSENT);
    CHECK(prp_host_receive(host,&ctx,&m,NULL)==PRP_ACCEPTED);
}
int main(void) {
    PRP_Host host;
    prp_host_init(&host,99,1);
    /* Deliberately register player 3 before player 2: ties must use ID. */
    PRP_Peer officer=snapshot(1,0),three=snapshot(3,-2),two=snapshot(2,2);
    PRP_Peer four=snapshot(4,1),five=snapshot(5,4),six=snapshot(6,1.5f);
    six.last_position_ms=1; /* stale even though closer */
    CHECK(prp_host_update_peer(&host,&officer));
    CHECK(prp_host_update_peer(&host,&three));
    CHECK(prp_host_update_peer(&host,&two));
    CHECK(prp_host_update_peer(&host,&four));
    CHECK(prp_host_update_peer(&host,&five));
    CHECK(prp_host_update_peer(&host,&six));
    uint64_t nearest=123;
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==0); /* no officer consent yet */
    consent(&host,1);
    consent(&host,3);
    consent(&host,2);
    consent(&host,5);
    consent(&host,6);
    CHECK(prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==2); /* tie resolved by smaller player ID, not slot */
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,NULL));

    /* Selection is only a suggestion. The host must still revalidate range. */
    PRP_TransportContext cop=delivery(1);
    PRP_Msg cuff=message(1,nearest,2,PRP_OP_CUFF);
    two.x=10;
    CHECK(prp_host_update_peer(&host,&two));
    CHECK(prp_host_receive(&host,&cop,&cuff,NULL)==PRP_ERR_DISTANCE);
    CHECK(prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==3);
    two.x=2;
    CHECK(prp_host_update_peer(&host,&two));
    cuff.seq=3;
    CHECK(prp_host_receive(&host,&cop,&cuff,NULL)==PRP_ACCEPTED);
    CHECK(prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==3); /* already cuffed player 2 excluded */

    /* Invalid and future positions must not be used for proximity. */
    three.x=NAN;
    CHECK(prp_host_update_peer(&host,&three));
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==0);
    three.x=-2;
    three.last_position_ms=5001;
    CHECK(prp_host_update_peer(&host,&three));
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    three.last_position_ms=5000;
    CHECK(prp_host_update_peer(&host,&three));
    CHECK(prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==3);

    /* Disconnected, unconsented or stale targets never become selectable. */
    CHECK(prp_host_remove_peer(&host,3));
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,8001,&nearest));
    CHECK(nearest==0);
    CHECK(!prp_host_find_nearest_cuff_target(&host,999,5000,&nearest));
    CHECK(nearest==0);
    officer.on_shift=0;
    CHECK(prp_host_update_peer(&host,&officer));
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    officer.on_shift=1;officer.native_job=4;
    CHECK(prp_host_update_peer(&host,&officer));
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));

    /* At the exact cuff radius boundary an opted-in free human is eligible. */
    officer.native_job=0;
    CHECK(prp_host_update_peer(&host,&officer));
    five.x=PRP_CUFF_RADIUS_M;
    CHECK(prp_host_update_peer(&host,&five));
    CHECK(prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==5);

    prp_host_init(&host,0,0);
    CHECK(!prp_host_find_nearest_cuff_target(&host,1,5000,&nearest));
    CHECK(nearest==0);
    printf("RP nearest opted-in player selector: %u host assertions passed; no GTA device tested\n",checks);
    return 0;
}
