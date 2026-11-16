#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "rp_v133_police_tx.h"

enum {COP = 11, PLAYER = 22};

static rp_police_member get(const rp_police_world *world, uint64_t id) {
    rp_police_member member;
    assert(rp_police_get(world, id, &member));
    return member;
}

static void ready(rp_police_world *world) {
    assert(rp_police_init(world, 123, 7));
    assert(rp_police_admit(world, COP, RP_POLICE_OFFICER));
    assert(rp_police_admit(world, PLAYER, RP_POLICE_CITIZEN));
    const rp_v133_delivery cop = {COP, 123, 7, 1}, player = {PLAYER, 123, 7, 1};
    const rp_police_observation job = {
        .actor = COP, .target = COP, .session = 123, .epoch = 7, .same_game_instance = true, .native_duty_eligible = true
    };
    const rp_police_command c1 = {123, 7, COP, 1, RP_POLICE_OPT_IN};
    const rp_police_command c2 = {123, 7, COP, 2, RP_POLICE_DUTY_START};
    const rp_police_command p1 = {123, 7, PLAYER, 1, RP_POLICE_OPT_IN};
    assert(rp_police_apply(world, &cop, &c1, 0));
    assert(rp_police_apply(world, &cop, &c2, &job));
    assert(rp_police_apply(world, &player, &p1, 0));
}

static void test_authenticated_retry_replays_decision_without_reapplying(void) {
    rp_police_world world;
    ready(&world);
    const rp_v133_delivery cop = {COP, 123, 7, 1}, player = {PLAYER, 123, 7, 1};
    rp_police_observation snapshot = {
        .actor = COP, .target = PLAYER, .session = 123, .epoch = 7, .same_game_instance = true,
        .distance_cm = 401, .native_duty_eligible = true
    };
    rp_police_command cmd = {123, 7, PLAYER, 3, RP_POLICE_CUFF};
    uint8_t wire[RP_POLICE_TX_BYTES], ack[RP_POLICE_TX_BYTES], cached[RP_POLICE_TX_BYTES];
    rp_police_ack decoded;
    assert(rp_police_tx_encode(&cmd, wire, sizeof wire));
    assert(rp_police_tx_dispatch(&world, &cop, &snapshot, wire, sizeof wire, ack, sizeof ack));
    assert(rp_police_tx_decode_ack(ack, sizeof ack, &cmd, &decoded));
    assert(decoded.outcome == RP_POLICE_TX_DENIED);
    snapshot.distance_cm = 400;
    assert(rp_police_tx_dispatch(&world, &cop, &snapshot, wire, sizeof wire, cached, sizeof cached));
    assert(!memcmp(ack, cached, sizeof ack) && get(&world, PLAYER).custody == RP_POLICE_FREE);
    ++cmd.nonce;
    assert(rp_police_tx_encode(&cmd, wire, sizeof wire));
    assert(rp_police_tx_dispatch(&world, &cop, &snapshot, wire, sizeof wire, ack, sizeof ack));
    assert(rp_police_tx_decode_ack(ack, sizeof ack, &cmd, &decoded));
    assert(decoded.outcome == RP_POLICE_TX_APPLIED);
    assert(get(&world, PLAYER).custody == RP_POLICE_CUFFED);
    const rp_police_command opt_out = {123, 7, PLAYER, 2, RP_POLICE_OPT_OUT};
    assert(rp_police_apply(&world, &player, &opt_out, 0));
    assert(rp_police_tx_dispatch(&world, &cop, &snapshot, wire, sizeof wire, cached, sizeof cached));
    assert(!memcmp(ack, cached, sizeof ack) && get(&world, PLAYER).custody == RP_POLICE_FREE);
    --cmd.nonce;
    assert(rp_police_tx_encode(&cmd, wire, sizeof wire));
    assert(!rp_police_tx_dispatch(&world, &cop, &snapshot, wire, sizeof wire, cached, sizeof cached));
    ++cmd.nonce;
    cmd.operation = RP_POLICE_ESCORT_START;
    assert(rp_police_tx_encode(&cmd, wire, sizeof wire));
    assert(!rp_police_tx_dispatch(&world, &cop, &snapshot, wire, sizeof wire, cached, sizeof cached));
    assert(!rp_police_tx_decode_ack(ack, sizeof ack, &cmd, &decoded));
    assert(decoded.outcome == 0);
}

static void test_malformed_envelopes_cannot_consume_transaction(void) {
    rp_police_world world;
    ready(&world);
    rp_v133_delivery cop = {COP, 123, 7, 0};
    const rp_police_command order = {123, 7, PLAYER, 3, RP_POLICE_CUFF};
    uint8_t wire[RP_POLICE_TX_BYTES], ack[RP_POLICE_TX_BYTES];
    assert(rp_police_tx_encode(&order, wire, sizeof wire));
    assert(!rp_police_tx_dispatch(&world, &cop, 0, wire, sizeof wire, ack, sizeof ack));
    cop.authenticated = 1;
    assert(!rp_police_tx_dispatch(&world, &cop, 0, wire, sizeof wire - 1u, ack, sizeof ack));
    assert(!rp_police_tx_dispatch(&world, &cop, 0, wire, sizeof wire, ack, sizeof ack - 1u));
    cop.transport_epoch = 8;
    assert(!rp_police_tx_dispatch(&world, &cop, 0, wire, sizeof wire, ack, sizeof ack));
    cop.transport_epoch = 7;
    wire[6] = 2;
    assert(!rp_police_tx_dispatch(&world, &cop, 0, wire, sizeof wire, ack, sizeof ack));
    assert(get(&world, COP).last_nonce == 2);
}

int main(void) {
    test_authenticated_retry_replays_decision_without_reapplying();
    test_malformed_envelopes_cannot_consume_transaction();
    puts("Police command and ACK: PASS (source-only)");
    return 0;
}
