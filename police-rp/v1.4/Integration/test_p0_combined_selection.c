/* P0 combined PR #4 target selector + PR #9 authenticated engine bridge.
 * Source-only synthetic GTA frame/transport harness. Does not test iPhone,
 * game hooks, RAGE networking or an actual GTA Online player.
 */
#include "prp_engine_binding.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    PRP_GameSnapshot snapshot;
    uint8_t last_wire[4][PRP_WIRE_SIZE];
    unsigned sent_to[4];
    int cuffed, controls;
} FakeEngine;

static unsigned checks;
#define CHECK(expr) do { assert(expr); ++checks; } while (0)

static int get_snapshot(void *userdata, PRP_GameSnapshot *out) {
    *out=((FakeEngine *)userdata)->snapshot;
    return 1;
}
static int send_wire(void *userdata, uint64_t receiver,
                     const uint8_t *data, size_t n) {
    FakeEngine *f=(FakeEngine *)userdata;
    if(receiver>=4 || n!=PRP_WIRE_SIZE) return 0;
    memcpy(f->last_wire[receiver],data,n);
    ++f->sent_to[receiver];
    return 1;
}
static void set_cuffed(void *userdata, int enable) {
    ((FakeEngine *)userdata)->cuffed=enable;
}
static void set_controls(void *userdata, int enable) {
    ((FakeEngine *)userdata)->controls=enable;
}
static PRP_EngineCallbacks callbacks(FakeEngine *e) {
    PRP_EngineCallbacks c={0};
    c.userdata=e;
    c.read_snapshot=get_snapshot;
    c.send_authenticated=send_wire;
    c.local_ped.abi_version=PR_ABI_VERSION;
    c.local_ped.userdata=e;
    c.local_ped.set_local_cuffed=set_cuffed;
    c.local_ped.set_local_controls_restricted=set_controls;
    return c;
}
static PRP_GameSnapshot snapshot(uint64_t local) {
    PRP_GameSnapshot s={0};
    s.abi=PRP_BRIDGE_ABI;
    s.local.abi_version=PR_ADAPTER_ABI;
    s.local.online=1;
    s.local.session_verified=1;
    s.local.verified_session_id=20261113;
    s.local.local_player_id=local;
    s.local.monotonic_ms=1000;
    s.local.local_opt_in=1;
    s.local.native_job=(local==1)?0:-1;
    s.local.on_shift=(uint8_t)(local==1);
    s.host_player_id=1;
    s.local_is_host=(uint8_t)(local==1);
    s.channel_authenticated=1;
    s.peer_count=3;
    /* Reverse order to verify tie selection is by player ID, NOT slot. */
    const uint64_t ids[3]={3,1,2};
    const float coords[3]={-2.0f,0.0f,2.0f};
    for(unsigned i=0;i<3;i++) {
        PRP_Peer *p=&s.trusted_peers[i];
        p->player_id=ids[i];
        p->connected=1;
        p->job_verified=1;
        p->native_job=(ids[i]==1)?0:-1;
        p->on_shift=(uint8_t)(ids[i]==1);
        p->position_verified=1;
        p->last_position_ms=1000;
        p->x=coords[i];
    }
    return s;
}

int main(void) {
    FakeEngine eh={0},e2={0},e3={0};
    eh.snapshot=snapshot(1);
    e2.snapshot=snapshot(2);
    e3.snapshot=snapshot(3);
    PRP_GameBridge host,guest2,guest3;
    PRP_EngineCallbacks cbh=callbacks(&eh),cb2=callbacks(&e2),cb3=callbacks(&e3);
    prp_bridge_init(&host,&cbh);
    prp_bridge_init(&guest2,&cb2);
    prp_bridge_init(&guest3,&cb3);
    CHECK(prp_bridge_frame(&host));
    CHECK(prp_bridge_frame(&guest2));
    CHECK(prp_bridge_frame(&guest3));
    CHECK(host.runtime.host.peer_count==3);
    uint64_t nearest=99;
    CHECK(!prp_host_find_nearest_cuff_target(
        &host.runtime.host,1,1000,&nearest));
    CHECK(nearest==0);

    /* Consent is transmitted over a hypothetical authenticated carrier.
     * Enqueue authenticated sender metadata, never trust payload sender. */
    prp_bridge_set_consent(&host,1);
    prp_bridge_set_consent(&guest2,1);
    prp_bridge_set_consent(&guest3,1);
    CHECK(prp_bridge_frame(&host));
    CHECK(prp_bridge_frame(&guest2));
    CHECK(prp_bridge_frame(&guest3));
    CHECK(e2.sent_to[1]==1 && e3.sent_to[1]==1);
    CHECK(!host.runtime.host.peers[0].opt_in); /* no packet until game tick */
    CHECK(prp_bridge_enqueue(&host,20261113,2,1,
                              e2.last_wire[1],PRP_WIRE_SIZE));
    CHECK(prp_bridge_enqueue(&host,20261113,3,1,
                              e3.last_wire[1],PRP_WIRE_SIZE));
    CHECK(prp_bridge_frame(&host));
    CHECK(prp_host_find_nearest_cuff_target(
        &host.runtime.host,1,1000,&nearest));
    CHECK(nearest==2); /* equal distance, lower verified ID */
    CHECK(prp_bridge_arrest(&host,PRP_OP_CUFF,2,0)==PRP_ACCEPTED);
    CHECK(host.runtime.host.states[2].status==PR_CUFFED); /* slot 2 */

    /* Undo first cuff and test a TOCTOU race: a target moved out of range
     * AFTER selection but BEFORE the actual host-authorized action. */
    CHECK(prp_bridge_arrest(&host,PRP_OP_UNCUFF,2,0)==PRP_ACCEPTED);
    eh.snapshot.trusted_peers[2].x=10.0f;
    CHECK(prp_bridge_frame(&host));
    CHECK(prp_bridge_arrest(&host,PRP_OP_CUFF,2,0)==PRP_ERR_DISTANCE);
    CHECK(prp_host_find_nearest_cuff_target(
        &host.runtime.host,1,1000,&nearest));
    CHECK(nearest==3);
    CHECK(prp_bridge_arrest(&host,PRP_OP_CUFF,nearest,0)==PRP_ACCEPTED);

    /* Host heartbeat reaches the correct guest (ID 3), never ID 2. */
    eh.snapshot.local.monotonic_ms=1600;
    CHECK(prp_bridge_frame(&host));
    CHECK(eh.sent_to[3]>0);
    PRP_Msg state={0};
    CHECK(prp_decode(&state,eh.last_wire[3],PRP_WIRE_SIZE));
    CHECK(state.op==PRP_OP_STATE && state.target_id==3);
    CHECK(state.status==PR_CUFFED);
    CHECK(prp_bridge_receive(&guest3,1,1,
                             eh.last_wire[3],PRP_WIRE_SIZE)==PRP_ACCEPTED);
    e3.snapshot.local.monotonic_ms=1600;
    CHECK(prp_bridge_frame(&guest3));
    CHECK(e3.cuffed && e3.controls);
    CHECK(!e2.cuffed && !e2.controls);

    /* Voluntary opt-out releases the guest ped before host ACK, then
     * revocation clears server-side consent, selection and restraint. */
    prp_bridge_set_consent(&guest3,0);
    CHECK(!e3.cuffed && !e3.controls);
    CHECK(e3.sent_to[1]>=2);
    CHECK(prp_bridge_enqueue(&host,20261113,3,1,
                              e3.last_wire[1],PRP_WIRE_SIZE));
    eh.snapshot.local.monotonic_ms=1700;
    CHECK(prp_bridge_frame(&host));
    CHECK(!host.runtime.host.peers[0].opt_in);
    CHECK(host.runtime.host.states[0].status==PR_FREE);
    CHECK(!prp_host_find_nearest_cuff_target(
        &host.runtime.host,1,1700,&nearest));
    CHECK(nearest==0);

    prp_bridge_stop(&guest2);
    prp_bridge_stop(&guest3);
    prp_bridge_stop(&host);
    puts("P0 combined target-to-bridge consent and restriction simulation passed");
    printf("assertions=%u; device_tested=false\n",checks);
    return 0;
}
