#include <assert.h>
#include <stdio.h>
#include "rp_v133_police.h"

enum { COP = 11, PLAYER = 22, OTHER_COP = 33, OTHER_PLAYER = 44, CAR = 78 };

static rp_police_member member(const rp_police_world *world, uint64_t id) {
    rp_police_member result;
    assert(rp_police_get(world, id, &result));
    return result;
}

static bool act(rp_police_world *world, uint64_t actor, uint64_t target,
                rp_police_operation op, const rp_police_observation *obs) {
    const rp_v133_delivery sender = {actor, world->session, world->epoch, 1};
    const rp_police_command cmd = {
        world->session, world->epoch, target, member(world, actor).last_nonce + 1u, op
    };
    return rp_police_apply(world, &sender, &cmd, obs);
}

static rp_police_observation observed(uint64_t actor, uint64_t target) {
    return (rp_police_observation){
        .actor = actor, .target = target, .vehicle_id = CAR,
        .distance_cm = 400, .seat = 1, .same_game_instance = true,
        .native_duty_eligible = true, .police_vehicle = true, .seat_available = true
    };
}

static void fixture(rp_police_world *world) {
    assert(rp_police_init(world, 123, 7));
    assert(rp_police_admit(world, COP, RP_POLICE_OFFICER));
    assert(rp_police_admit(world, OTHER_COP, RP_POLICE_OFFICER));
    assert(rp_police_admit(world, PLAYER, RP_POLICE_CITIZEN));
    assert(rp_police_admit(world, OTHER_PLAYER, RP_POLICE_CITIZEN));
}

static void start_duty(rp_police_world *world, uint64_t officer) {
    const rp_police_observation on_duty = observed(officer, officer);
    assert(act(world, officer, officer, RP_POLICE_OPT_IN, 0));
    assert(act(world, officer, officer, RP_POLICE_DUTY_START, &on_duty));
}

static void ready(rp_police_world *world) {
    fixture(world);
    start_duty(world, COP);
    assert(act(world, PLAYER, PLAYER, RP_POLICE_OPT_IN, 0));
}

static void cuff_to_passenger(rp_police_world *world, uint64_t target,
                              const rp_police_observation *obs) {
    assert(act(world, COP, target, RP_POLICE_CUFF, obs));
    assert(act(world, COP, target, RP_POLICE_ESCORT_START, obs));
    assert(act(world, COP, target, RP_POLICE_ENTER_SEAT, obs));
}

static void test_policy_and_sender_metadata(void) {
    rp_police_world world;
    fixture(&world);
    rp_v133_delivery sender = {COP, 123, 7, 0};
    rp_police_command command = {123, 7, COP, 1, RP_POLICE_OPT_IN};
    assert(!rp_police_apply(&world, &sender, &command, 0));
    sender.authenticated = 1;
    sender.transport_epoch = 6;
    assert(!rp_police_apply(&world, &sender, &command, 0));
    sender.transport_epoch = 7;
    command.session = 999;
    assert(!rp_police_apply(&world, &sender, &command, 0));
    assert(member(&world, COP).last_nonce == 0);
    command.session = 123;
    sender.transport_sender = PLAYER;
    assert(!rp_police_apply(&world, &sender, &command, 0));
    assert(!member(&world, COP).consent);
    sender.transport_sender = COP;
    assert(rp_police_apply(&world, &sender, &command, 0));
    assert(!rp_police_apply(&world, &sender, &command, 0));
    rp_police_observation a_self = observed(COP, COP), b_self = observed(PLAYER, PLAYER);
    assert(act(&world, PLAYER, PLAYER, RP_POLICE_OPT_IN, 0));
    assert(!act(&world, PLAYER, PLAYER, RP_POLICE_DUTY_START, &b_self));
    a_self.native_duty_eligible = false;
    assert(!act(&world, COP, COP, RP_POLICE_DUTY_START, &a_self));
    a_self.native_duty_eligible = true;
    assert(act(&world, COP, COP, RP_POLICE_DUTY_START, &a_self));
    rp_police_observation obs = observed(COP, OTHER_PLAYER);
    assert(!act(&world, COP, OTHER_PLAYER, RP_POLICE_CUFF, &obs)); /* no consent */
    obs = observed(COP, PLAYER);
    obs.same_game_instance = false;
    assert(!act(&world, COP, PLAYER, RP_POLICE_CUFF, &obs));
    obs.same_game_instance = true;
    obs.target = OTHER_PLAYER;
    assert(!act(&world, COP, PLAYER, RP_POLICE_CUFF, &obs));
    obs.target = PLAYER;
    obs.distance_cm = 401;
    assert(!act(&world, COP, PLAYER, RP_POLICE_CUFF, &obs));
    const rp_police_command denied = {123, 7, PLAYER, member(&world, COP).last_nonce, RP_POLICE_CUFF};
    obs.distance_cm = 400;
    assert(!rp_police_apply(&world, &sender, &denied, &obs)); /* rejected nonce stays consumed */
    assert(act(&world, COP, PLAYER, RP_POLICE_CUFF, &obs));
    assert(act(&world, COP, PLAYER, RP_POLICE_UNCUFF, &obs));
    assert(member(&world, PLAYER).custody == RP_POLICE_FREE);
}

static void test_full_custody_and_seat_conflict(void) {
    rp_police_world world;
    ready(&world);
    start_duty(&world, OTHER_COP);
    assert(act(&world, OTHER_PLAYER, OTHER_PLAYER, RP_POLICE_OPT_IN, 0));
    rp_police_observation obs = observed(COP, PLAYER);
    rp_police_observation rival = observed(OTHER_COP, PLAYER);
    cuff_to_passenger(&world, PLAYER, &obs);
    assert(member(&world, PLAYER).vehicle_id == CAR && member(&world, PLAYER).seat == 1);
    assert(!act(&world, OTHER_COP, PLAYER, RP_POLICE_EXIT_SEAT, &rival));
    assert(!act(&world, COP, PLAYER, RP_POLICE_UNCUFF, &obs));
    obs.both_at_jail_intake = true;
    assert(!act(&world, COP, PLAYER, RP_POLICE_JAIL, &obs)); /* must exit */
    rp_police_observation other = observed(COP, OTHER_PLAYER);
    assert(act(&world, COP, OTHER_PLAYER, RP_POLICE_CUFF, &other));
    assert(act(&world, COP, OTHER_PLAYER, RP_POLICE_ESCORT_START, &other));
    assert(!act(&world, COP, OTHER_PLAYER, RP_POLICE_ENTER_SEAT, &other));
    obs.vehicle_id++;
    assert(!act(&world, COP, PLAYER, RP_POLICE_EXIT_SEAT, &obs));
    obs.vehicle_id = CAR;
    assert(act(&world, COP, PLAYER, RP_POLICE_EXIT_SEAT, &obs));
    assert(member(&world, PLAYER).vehicle_id == 0);
    assert(act(&world, COP, OTHER_PLAYER, RP_POLICE_ENTER_SEAT, &other));
    assert(act(&world, COP, PLAYER, RP_POLICE_ESCORT_START, &obs));
    assert(act(&world, COP, PLAYER, RP_POLICE_ESCORT_END, &obs));
    obs.both_at_jail_intake = false;
    assert(!act(&world, COP, PLAYER, RP_POLICE_JAIL, &obs));
    obs.both_at_jail_intake = true;
    assert(rp_police_tick(&world, 1000));
    assert(act(&world, COP, PLAYER, RP_POLICE_JAIL, &obs));
    assert(member(&world, PLAYER).jail_until_ms == 61000);
    assert(!rp_police_tick(&world, 999));
    assert(rp_police_tick(&world, 60999));
    assert(member(&world, PLAYER).custody == RP_POLICE_JAILED);
    assert(rp_police_tick(&world, 61000));
    assert(member(&world, PLAYER).custody == RP_POLICE_FREE);
    assert(act(&world, COP, PLAYER, RP_POLICE_CUFF, &obs));
    assert(act(&world, COP, PLAYER, RP_POLICE_JAIL, &obs));
    assert(act(&world, COP, PLAYER, RP_POLICE_RELEASE_JAIL, &obs));
}

static void test_disconnect_duty_and_generation_cleanup(void) {
    rp_police_world world;
    ready(&world);
    rp_police_observation obs = observed(COP, PLAYER);
    cuff_to_passenger(&world, PLAYER, &obs);
    assert(act(&world, PLAYER, PLAYER, RP_POLICE_OPT_OUT, 0));
    assert(member(&world, PLAYER).custody == RP_POLICE_FREE);
    assert(member(&world, PLAYER).vehicle_id == 0);
    assert(act(&world, PLAYER, PLAYER, RP_POLICE_OPT_IN, 0));
    cuff_to_passenger(&world, PLAYER, &obs);
    assert(rp_police_revoke_duty(&world, COP));
    assert(!member(&world, COP).on_duty && member(&world, PLAYER).custody == RP_POLICE_FREE);
    const rp_police_observation self = observed(COP, COP);
    assert(act(&world, COP, COP, RP_POLICE_DUTY_START, &self));
    cuff_to_passenger(&world, PLAYER, &obs);
    const uint64_t saved = member(&world, COP).last_nonce;
    assert(rp_police_leave(&world, COP));
    assert(member(&world, PLAYER).custody == RP_POLICE_FREE);
    assert(!rp_police_admit(&world, COP, RP_POLICE_CITIZEN));
    assert(rp_police_admit(&world, COP, RP_POLICE_OFFICER));
    assert(!member(&world, COP).consent && member(&world, COP).last_nonce == saved);
    const rp_v133_delivery old_sender = {COP, 123, 7, 1};
    const rp_police_command old_cmd = {123, 7, COP, saved, RP_POLICE_OPT_IN};
    assert(!rp_police_apply(&world, &old_sender, &old_cmd, 0));
    assert(rp_police_init(&world, 123, 8));
    assert(rp_police_admit(&world, COP, RP_POLICE_OFFICER));
    assert(!rp_police_apply(&world, &old_sender, &old_cmd, 0));
}

static void test_bounds(void) {
    rp_police_world world;
    ready(&world);
    rp_police_observation obs = observed(COP, PLAYER);
    assert(act(&world, COP, PLAYER, RP_POLICE_CUFF, &obs));
    obs.both_at_jail_intake = true;
    assert(rp_police_tick(&world, UINT64_MAX - RP_V133_POLICE_JAIL_MS + 1u));
    assert(!act(&world, COP, PLAYER, RP_POLICE_JAIL, &obs));
    assert(member(&world, PLAYER).custody == RP_POLICE_CUFFED);
    assert(rp_police_init(&world, 1, 1));
    for (uint64_t id = 1; id <= RP_V133_POLICE_CAPACITY; ++id)
        assert(rp_police_admit(&world, id, RP_POLICE_CITIZEN));
    assert(rp_police_leave(&world, 1));
    assert(!rp_police_admit(&world, RP_V133_POLICE_CAPACITY + 1u, RP_POLICE_CITIZEN));
    assert(rp_police_admit(&world, 1, RP_POLICE_CITIZEN));
}

int main(void) {
    test_policy_and_sender_metadata();
    test_full_custody_and_seat_conflict();
    test_disconnect_duty_and_generation_cleanup();
    test_bounds();
    puts("Police authority: PASS (source-only synthetic decisions)");
    return 0;
}
