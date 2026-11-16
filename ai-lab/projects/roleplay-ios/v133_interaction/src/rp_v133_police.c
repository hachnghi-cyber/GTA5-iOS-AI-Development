#include "rp_v133_police.h"

static bool world_ready(const rp_police_world *world) {
    return world && world->session && world->epoch;
}

static int member_index(const rp_police_world *world, uint64_t id) {
    if (!world_ready(world) || !id) return -1;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i)
        if (world->members[i].id == id) return (int)i;
    return -1;
}

static rp_police_member *present_member(rp_police_world *world, uint64_t id) {
    const int index = member_index(world, id);
    if (index < 0 || !world->members[index].present) return 0;
    return &world->members[index];
}

static void release_member(rp_police_member *member) {
    member->custody = RP_POLICE_FREE;
    member->custodian = 0;
    member->vehicle_id = 0;
    member->jail_until_ms = 0;
    member->seat = 0;
}

static void end_duty(rp_police_world *world, rp_police_member *actor) {
    actor->on_duty = false;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i) {
        rp_police_member *member = &world->members[i];
        if (member->custodian == actor->id) release_member(member);
    }
}

static void revoke_consent(rp_police_world *world, rp_police_member *member) {
    end_duty(world, member);
    release_member(member);
    member->consent = false;
}

bool rp_police_init(rp_police_world *world, uint64_t session, uint64_t epoch) {
    if (!world) return false;
    *world = (rp_police_world){0};
    if (!session || !epoch) return false;
    world->session = session;
    world->epoch = epoch;
    return true;
}

bool rp_police_admit(rp_police_world *world, uint64_t id, rp_police_role role) {
    if (!world_ready(world) || !id ||
        (role != RP_POLICE_CITIZEN && role != RP_POLICE_OFFICER)) return false;
    const int index = member_index(world, id);
    if (index >= 0) {
        rp_police_member *member = &world->members[index];
        if (member->present || member->role != role) return false;
        member->present = true;
        return true;
    }
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i) {
        if (world->members[i].id) continue;
        world->members[i] = (rp_police_member){.id = id, .role = role, .present = true};
        return true;
    }
    return false;
}

bool rp_police_leave(rp_police_world *world, uint64_t id) {
    rp_police_member *member = present_member(world, id);
    if (!member) return false;
    revoke_consent(world, member);
    member->present = false;
    return true;
}

bool rp_police_revoke_duty(rp_police_world *world, uint64_t id) {
    rp_police_member *member = present_member(world, id);
    if (!member || !member->on_duty) return false;
    end_duty(world, member);
    return true;
}

bool rp_police_tick(rp_police_world *world, uint64_t now_ms) {
    if (!world_ready(world) || now_ms < world->now_ms) return false;
    world->now_ms = now_ms;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i) {
        rp_police_member *member = &world->members[i];
        if (member->custody == RP_POLICE_JAILED && now_ms >= member->jail_until_ms)
            release_member(member);
    }
    return true;
}

bool rp_police_get(const rp_police_world *world, uint64_t id, rp_police_member *member) {
    if (!member) return false;
    *member = (rp_police_member){0};
    const int index = member_index(world, id);
    if (index < 0 || !world->members[index].present) return false;
    *member = world->members[index];
    return true;
}

static bool saw_pair(const rp_police_observation *obs, uint64_t actor, uint64_t target) {
    return obs && obs->actor == actor && obs->target == target && obs->same_game_instance;
}

static bool self_action(rp_police_world *world, rp_police_member *actor,
                        rp_police_operation op, const rp_police_observation *obs) {
    switch (op) {
        case RP_POLICE_OPT_IN:
            if (actor->consent) return false;
            actor->consent = true;
            return true;
        case RP_POLICE_OPT_OUT:
            if (!actor->consent) return false;
            revoke_consent(world, actor);
            return true;
        case RP_POLICE_DUTY_START:
            if (!actor->consent || actor->on_duty || actor->role != RP_POLICE_OFFICER ||
                actor->custody != RP_POLICE_FREE || !saw_pair(obs, actor->id, actor->id) ||
                !obs->native_duty_eligible) return false;
            actor->on_duty = true;
            return true;
        case RP_POLICE_DUTY_END:
            return rp_police_revoke_duty(world, actor->id);
        default:
            return false;
    }
}

static bool seat_clear(const rp_police_world *world, const rp_police_observation *obs) {
    if (!obs->vehicle_id || !obs->police_vehicle || !obs->seat_available || obs->seat > 2u)
        return false;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i) {
        const rp_police_member *member = &world->members[i];
        if (member->custody == RP_POLICE_SEATED &&
            member->vehicle_id == obs->vehicle_id && member->seat == obs->seat) return false;
    }
    return true;
}

static bool custody_action(rp_police_world *world, rp_police_member *actor,
                           rp_police_member *target, rp_police_operation op,
                           const rp_police_observation *obs) {
    if (!actor->consent || !actor->on_duty || actor->role != RP_POLICE_OFFICER ||
        actor->custody != RP_POLICE_FREE || !target->consent ||
        !saw_pair(obs, actor->id, target->id) || !obs->native_duty_eligible ||
        obs->distance_cm > RP_V133_MAX_INTERACT_CM) return false;

    if (op == RP_POLICE_CUFF) {
        if (target->custody != RP_POLICE_FREE || target->on_duty) return false;
        target->custodian = actor->id;
        target->custody = RP_POLICE_CUFFED;
        return true;
    }
    if (target->custodian != actor->id) return false;
    const bool on_foot = target->custody == RP_POLICE_CUFFED ||
                         target->custody == RP_POLICE_ESCORTED;
    switch (op) {
        case RP_POLICE_UNCUFF:
            if (!on_foot) return false;
            release_member(target);
            return true;
        case RP_POLICE_ESCORT_START:
            if (target->custody != RP_POLICE_CUFFED) return false;
            target->custody = RP_POLICE_ESCORTED;
            return true;
        case RP_POLICE_ESCORT_END:
            if (target->custody != RP_POLICE_ESCORTED) return false;
            target->custody = RP_POLICE_CUFFED;
            return true;
        case RP_POLICE_ENTER_SEAT:
            if (target->custody != RP_POLICE_ESCORTED || !seat_clear(world, obs)) return false;
            target->custody = RP_POLICE_SEATED;
            target->vehicle_id = obs->vehicle_id;
            target->seat = obs->seat;
            return true;
        case RP_POLICE_EXIT_SEAT:
            if (target->custody != RP_POLICE_SEATED || !obs->police_vehicle ||
                obs->vehicle_id != target->vehicle_id) return false;
            target->custody = RP_POLICE_CUFFED;
            target->vehicle_id = 0;
            target->seat = 0;
            return true;
        case RP_POLICE_JAIL:
            if (!on_foot || !obs->both_at_jail_intake ||
                world->now_ms > UINT64_MAX - RP_V133_POLICE_JAIL_MS) return false;
            target->custody = RP_POLICE_JAILED;
            target->jail_until_ms = world->now_ms + RP_V133_POLICE_JAIL_MS;
            return true;
        case RP_POLICE_RELEASE_JAIL:
            if (target->custody != RP_POLICE_JAILED || !obs->both_at_jail_intake) return false;
            release_member(target);
            return true;
        default:
            return false;
    }
}

bool rp_police_apply(rp_police_world *world, const rp_v133_delivery *delivery,
                     const rp_police_command *command, const rp_police_observation *observation) {
    if (!world_ready(world) || !delivery || !command || delivery->authenticated != 1 ||
        delivery->transport_session != world->session || delivery->transport_epoch != world->epoch ||
        command->session != world->session || command->epoch != world->epoch ||
        !command->target || command->operation < RP_POLICE_OPT_IN ||
        command->operation > RP_POLICE_RELEASE_JAIL) return false;

    rp_police_member *actor = present_member(world, delivery->transport_sender);
    if (!actor || command->nonce <= actor->last_nonce) return false;
    actor->last_nonce = command->nonce;
    if (command->target == actor->id)
        return self_action(world, actor, command->operation, observation);
    rp_police_member *target = present_member(world, command->target);
    return target && custody_action(world, actor, target, command->operation, observation);
}
