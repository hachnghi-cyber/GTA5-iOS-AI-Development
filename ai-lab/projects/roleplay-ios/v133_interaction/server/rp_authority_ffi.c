#include "rp_authority_ffi.h"
#include "rp_v133_police_tx.h"
#include <stdlib.h>
#include <string.h>

uint32_t rp_server_abi(void) {
    return 3u;
}

void *rp_server_create(uint64_t session, uint64_t epoch) {
    rp_police_world *world = calloc(1, sizeof *world);
    if (!world) return NULL;
    if (!rp_police_init(world, session, epoch)) {
        free(world);
        return NULL;
    }
    return world;
}

void rp_server_destroy(void *handle) {
    free(handle);
}

int rp_server_admit(void *handle, uint64_t id, uint32_t role) {
    if (role != RP_POLICE_CITIZEN && role != RP_POLICE_OFFICER) return 0;
    return rp_police_admit(handle, id, (rp_police_role)role);
}

int rp_server_leave(void *handle, uint64_t id) {
    return rp_police_leave(handle, id);
}

int rp_server_reset_game_member(void *handle, uint64_t id) {
    return rp_police_reset_game_member(handle, id);
}

int rp_server_revoke_duty(void *handle, uint64_t id) {
    return rp_police_revoke_duty(handle, id);
}

int rp_server_tick(void *handle, uint64_t now_ms) {
    return rp_police_tick(handle, now_ms);
}

int rp_server_dispatch(void *handle, uint64_t sender, uint64_t now_ms,
                       const uint8_t *wire, size_t wire_size,
                       const uint64_t *facts, size_t facts_count,
                       uint8_t *ack, size_t ack_size) {
    rp_police_world *world = handle;
    if (!world || !sender || !wire || wire_size != RP_POLICE_TX_BYTES ||
        !ack || ack_size != RP_POLICE_TX_BYTES ||
        (facts ? facts_count != RP_SERVER_FACT_COUNT : facts_count != 0)) return 0;

    rp_police_observation observation;
    const rp_police_observation *observed = NULL;
    if (facts) {
        if (facts[2] > UINT32_MAX || facts[3] > UINT8_MAX || (facts[4] & ~UINT64_C(31)))
            return 0;
        observation = (rp_police_observation){
            .actor = facts[5], .target = facts[6],
            .session = world->session, .epoch = world->epoch,
            .observed_at_ms = facts[0], .vehicle_id = facts[1],
            .distance_cm = (uint32_t)facts[2], .seat = (uint8_t)facts[3],
            .same_game_instance = (facts[4] & 1u) != 0,
            .native_duty_eligible = (facts[4] & 2u) != 0,
            .police_vehicle = (facts[4] & 4u) != 0,
            .seat_available = (facts[4] & 8u) != 0,
            .both_at_jail_intake = (facts[4] & 16u) != 0
        };
        observed = &observation;
    }
    if (!rp_police_tick(world, now_ms)) return 0;
    const rp_v133_delivery delivery = {sender, world->session, world->epoch, 1};
    return rp_police_tx_dispatch(world, &delivery, observed, wire, wire_size, ack, ack_size);
}

int rp_server_snapshot(void *handle, uint64_t id, uint64_t *out, size_t out_count) {
    if (!out || out_count != RP_SERVER_SNAPSHOT_COUNT) return 0;
    memset(out, 0, RP_SERVER_SNAPSHOT_COUNT * sizeof *out);
    rp_police_member member;
    if (!rp_police_get(handle, id, &member)) return 0;
    const uint64_t values[RP_SERVER_SNAPSHOT_COUNT] = {
        member.id, (uint64_t)member.role, member.consent, member.on_duty,
        (uint64_t)member.custody, member.custodian, member.vehicle_id,
        member.seat, member.jail_until_ms, member.last_nonce
    };
    memcpy(out, values, sizeof values);
    return 1;
}
