#include "rp_v133_police_bridge.h"

static bool valid_scope(rp_game_scope scope) {
    return scope.session && scope.generation;
}

static bool same_scope(rp_game_scope a, rp_game_scope b) {
    return a.session == b.session && a.generation == b.generation;
}

static bool same_peer(rp_game_peer a, rp_game_peer b) {
    return a.id == b.id && a.incarnation == b.incarnation;
}

static int find_binding(const rp_police_bridge *bridge, uint64_t rp_id) {
    if (!rp_id) return -1;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i)
        if (bridge->bindings[i].rp_id == rp_id) return (int)i;
    return -1;
}

static bool verified_delivery(const rp_police_bridge *bridge, const rp_v133_delivery *delivery) {
    return bridge && valid_scope(bridge->game) && delivery && delivery->transport_sender &&
        delivery->authenticated == 1 && delivery->transport_session == bridge->world.session &&
        delivery->transport_epoch == bridge->world.epoch;
}

bool rp_police_bridge_init(rp_police_bridge *bridge, uint64_t session, uint64_t epoch,
                           rp_game_scope game) {
    if (!bridge) return false;
    *bridge = (rp_police_bridge){0};
    if (!valid_scope(game) || !rp_police_init(&bridge->world, session, epoch)) return false;
    bridge->game = game;
    return true;
}

bool rp_police_bridge_rotate(rp_police_bridge *bridge, uint64_t session, uint64_t epoch,
                             rp_game_scope game) {
    if (!bridge || !valid_scope(bridge->game) || !valid_scope(game) || !session || !epoch ||
        (bridge->game.session == game.session && game.generation <= bridge->game.generation) ||
        (bridge->world.session == session && epoch <= bridge->world.epoch)) return false;
    return rp_police_bridge_init(bridge, session, epoch, game);
}

bool rp_police_bridge_bind(rp_police_bridge *bridge, const rp_v133_delivery *verified,
                           rp_game_scope game, rp_game_peer peer, rp_police_role role) {
    if (!verified_delivery(bridge, verified) || !same_scope(bridge->game, game) ||
        !peer.id || peer.incarnation <= bridge->highest_incarnation) return false;
    const uint64_t rp_id = verified->transport_sender;
    int index = find_binding(bridge, rp_id);
    int available = -1;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i) {
        const rp_police_binding *binding = &bridge->bindings[i];
        if (binding->active && (binding->rp_id == rp_id || binding->game.id == peer.id))
            return false;
        if (!binding->rp_id && available < 0) available = (int)i;
    }
    if (index < 0) index = available;
    if (index < 0 || !rp_police_admit(&bridge->world, rp_id, role)) return false;
    bridge->bindings[index] = (rp_police_binding){.rp_id = rp_id, .game = peer, .active = true};
    bridge->highest_incarnation = peer.incarnation;
    return true;
}

bool rp_police_bridge_leave(rp_police_bridge *bridge, uint64_t rp_id,
                            rp_game_scope game, rp_game_peer peer) {
    if (!bridge || !same_scope(bridge->game, game)) return false;
    const int index = find_binding(bridge, rp_id);
    if (index < 0) return false;
    rp_police_binding *binding = &bridge->bindings[index];
    if (!binding->active || !same_peer(binding->game, peer) ||
        !rp_police_leave(&bridge->world, rp_id)) return false;
    binding->active = false;
    return true;
}

bool rp_police_bridge_dispatch(rp_police_bridge *bridge, const rp_v133_delivery *delivery,
                               const rp_game_observation *game, uint64_t now_ms,
                               const uint8_t *wire, size_t wire_size,
                               uint8_t *ack, size_t ack_size) {
    rp_police_command command;
    if (!verified_delivery(bridge, delivery) || !ack || ack_size != RP_POLICE_TX_BYTES ||
        !rp_police_tx_decode_command(wire, wire_size, &command) ||
        command.session != bridge->world.session || command.epoch != bridge->world.epoch)
        return false;
    const int actor = find_binding(bridge, delivery->transport_sender);
    const int target = find_binding(bridge, command.target);
    if (actor < 0 || target < 0 || !bridge->bindings[actor].active ||
        !bridge->bindings[target].active || !rp_police_tick(&bridge->world, now_ms)) return false;

    rp_police_observation observation;
    const rp_police_observation *facts = 0;
    if (game && same_scope(bridge->game, game->scope) &&
        same_peer(bridge->bindings[actor].game, game->actor) &&
        same_peer(bridge->bindings[target].game, game->target)) {
        observation = (rp_police_observation){
            .actor = delivery->transport_sender, .target = command.target,
            .session = bridge->world.session, .epoch = bridge->world.epoch,
            .observed_at_ms = game->observed_at_ms, .vehicle_id = game->vehicle_id,
            .distance_cm = game->distance_cm, .seat = game->seat,
            .same_game_instance = game->same_game_instance,
            .native_duty_eligible = game->native_duty_eligible,
            .police_vehicle = game->police_vehicle, .seat_available = game->seat_available,
            .both_at_jail_intake = game->both_at_jail_intake
        };
        facts = &observation;
    }
    return rp_police_tx_dispatch(&bridge->world, delivery, facts, wire, wire_size, ack, ack_size);
}
