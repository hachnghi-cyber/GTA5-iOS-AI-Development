#include <assert.h>
#include <stdio.h>
#include "rp_v133_police_bridge.h"

enum {COP = 11, CITIZEN = 22, STRANGER = 33};
static const rp_game_scope scope = {345, 6};
static const rp_game_peer cop_game = {781, 1};
static const rp_game_peer citizen_game = {922, 2};
static const rp_v133_delivery cop = {COP, 123, 7, 1};
static const rp_v133_delivery citizen = {CITIZEN, 123, 7, 1};

static rp_police_member member(const rp_police_bridge *bridge, uint64_t id) {
    rp_police_member out;
    assert(rp_police_get(&bridge->world, id, &out));
    return out;
}

static rp_police_tx_outcome operate(rp_police_bridge *bridge, rp_v133_delivery from,
                                    uint64_t target, uint64_t nonce, rp_police_operation op,
                                    const rp_game_observation *obs, uint64_t now) {
    const rp_police_command command = {from.transport_session, from.transport_epoch, target, nonce, op};
    uint8_t wire[RP_POLICE_TX_BYTES], reply[RP_POLICE_TX_BYTES];
    rp_police_ack ack;
    assert(rp_police_tx_encode(&command, wire, sizeof wire));
    if (!rp_police_bridge_dispatch(bridge, &from, obs, now, wire, sizeof wire, reply, sizeof reply))
        return 0; /* No ACK. */
    assert(rp_police_tx_decode_ack(reply, sizeof reply, &command, &ack));
    return ack.outcome;
}

static rp_game_observation observation(rp_game_peer target, uint64_t time) {
    return (rp_game_observation){ .scope = scope, .actor = cop_game, .target = target,
                                  .observed_at_ms = time, .distance_cm = 400,
                                  .same_game_instance = true, .native_duty_eligible = true };
}

static void bind_fixture(rp_police_bridge *bridge) {
    assert(rp_police_bridge_init(bridge, 123, 7, scope));
    assert(rp_police_bridge_bind(bridge, &cop, scope, cop_game, RP_POLICE_OFFICER));
    assert(rp_police_bridge_bind(bridge, &citizen, scope, citizen_game, RP_POLICE_CITIZEN));
}

static void start_fixture(rp_police_bridge *bridge) {
    bind_fixture(bridge);
    assert(operate(bridge, cop, COP, 1, RP_POLICE_OPT_IN, 0, 100) == RP_POLICE_TX_APPLIED);
    const rp_game_observation local = observation(cop_game, 100);
    assert(operate(bridge, cop, COP, 2, RP_POLICE_DUTY_START, &local, 100) == RP_POLICE_TX_APPLIED);
    assert(operate(bridge, citizen, CITIZEN, 1, RP_POLICE_OPT_IN, 0, 100) == RP_POLICE_TX_APPLIED);
}

static void test_scoped_one_to_one_binding(void) {
    rp_police_bridge bridge;
    bind_fixture(&bridge);
    const rp_v133_delivery third = {STRANGER, 123, 7, 1};
    const rp_v133_delivery unverified = {STRANGER, 123, 7, 0};
    const rp_game_peer alias = {cop_game.id, 3}, fresh = {555, 3};
    const rp_game_scope old = {scope.session, scope.generation - 1u};
    assert(!rp_police_bridge_bind(&bridge, &third, scope, alias, RP_POLICE_OFFICER));
    assert(!rp_police_bridge_bind(&bridge, &unverified, scope, fresh, RP_POLICE_OFFICER));
    assert(!rp_police_bridge_bind(&bridge, &third, old, fresh, RP_POLICE_CITIZEN));
    assert(!member(&bridge, COP).consent); /* Binding does not auto opt in. */
    assert(!operate(&bridge, third, STRANGER, 1, RP_POLICE_OPT_IN, 0, 10));
    assert(rp_police_bridge_bind(&bridge, &third, scope, fresh, RP_POLICE_CITIZEN));
    assert(!rp_police_bridge_bind(&bridge, &third, scope, (rp_game_peer){556, 4}, RP_POLICE_CITIZEN));
}

static void test_live_frame_and_revocation(void) {
    rp_police_bridge bridge;
    start_fixture(&bridge);
    rp_game_observation frame = observation(citizen_game, 100);
    frame.target.id = CITIZEN; /* A TLS ID is not the engine ID. */
    assert(operate(&bridge, cop, CITIZEN, 3, RP_POLICE_CUFF, &frame, 100) == RP_POLICE_TX_DENIED);
    frame.target = citizen_game;
    frame.scope.generation--;
    assert(operate(&bridge, cop, CITIZEN, 4, RP_POLICE_CUFF, &frame, 100) == RP_POLICE_TX_DENIED);
    frame.scope = scope;
    assert(operate(&bridge, cop, CITIZEN, 5, RP_POLICE_CUFF, &frame, 351) == RP_POLICE_TX_DENIED);
    frame.observed_at_ms = 351;
    assert(operate(&bridge, cop, CITIZEN, 6, RP_POLICE_CUFF, &frame, 351) == RP_POLICE_TX_APPLIED);
    assert(member(&bridge, CITIZEN).custody == RP_POLICE_CUFFED);
    assert(!rp_police_bridge_leave(&bridge, CITIZEN, scope, (rp_game_peer){citizen_game.id, 1}));
    assert(rp_police_bridge_leave(&bridge, CITIZEN, scope, citizen_game));
    assert(!operate(&bridge, cop, CITIZEN, 6, RP_POLICE_CUFF, &frame, 351));
    assert(!rp_police_bridge_bind(&bridge, &citizen, scope, citizen_game, RP_POLICE_CITIZEN));
    const rp_game_peer replacement = {citizen_game.id, 3};
    assert(rp_police_bridge_bind(&bridge, &citizen, scope, replacement, RP_POLICE_CITIZEN));
    assert(member(&bridge, CITIZEN).custody == RP_POLICE_FREE);
    assert(!member(&bridge, CITIZEN).consent);
    assert(!operate(&bridge, citizen, CITIZEN, 1, RP_POLICE_OPT_IN, 0, 351)); /* old nonce */
    assert(!operate(&bridge, cop, CITIZEN, 6, RP_POLICE_CUFF, &frame, 351)); /* old ACK */
    assert(operate(&bridge, citizen, CITIZEN, 2, RP_POLICE_OPT_IN, 0, 351) == RP_POLICE_TX_APPLIED);
    assert(operate(&bridge, cop, CITIZEN, 7, RP_POLICE_CUFF, &frame, 351) == RP_POLICE_TX_DENIED);
    frame.target = replacement;
    frame.same_game_instance = false;
    assert(operate(&bridge, cop, CITIZEN, 8, RP_POLICE_CUFF, &frame, 351) == RP_POLICE_TX_DENIED);
    frame.same_game_instance = true;
    assert(operate(&bridge, cop, CITIZEN, 9, RP_POLICE_CUFF, &frame, 351) == RP_POLICE_TX_APPLIED);
}

static void test_rotation_pairing_and_game_must_advance(void) {
    rp_police_bridge bridge;
    start_fixture(&bridge);
    const rp_game_scope next = {scope.session, scope.generation + 1u};
    assert(!rp_police_bridge_rotate(&bridge, 123, 7, next));
    assert(!rp_police_bridge_rotate(&bridge, 123, 8, scope));
    assert(rp_police_bridge_rotate(&bridge, 123, 8, next));
    assert(!rp_police_bridge_rotate(&bridge, 123, 7, scope));
    assert(!rp_police_bridge_bind(&bridge, &cop, next, cop_game, RP_POLICE_OFFICER));
    assert(!operate(&bridge, cop, COP, 3, RP_POLICE_DUTY_END, 0, 500));
    const rp_v133_delivery new_cop = {COP, 123, 8, 1};
    assert(rp_police_bridge_bind(&bridge, &new_cop, next, cop_game, RP_POLICE_OFFICER));
    assert(!member(&bridge, COP).on_duty && member(&bridge, COP).last_nonce == 0);
    assert(operate(&bridge, new_cop, COP, 1, RP_POLICE_OPT_IN, 0, 500) == RP_POLICE_TX_APPLIED);
    const rp_game_observation old_frame = observation(cop_game, 500);
    assert(operate(&bridge, new_cop, COP, 2, RP_POLICE_DUTY_START, &old_frame, 500) == RP_POLICE_TX_DENIED);
}

int main(void) {
    test_scoped_one_to_one_binding();
    test_live_frame_and_revocation();
    test_rotation_pairing_and_game_must_advance();
    puts("Police bridge: PASS (injected identity and snapshot fixtures only)");
    return 0;
}
