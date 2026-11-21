#include "rp_v133_police_tx.h"
#include <string.h>

static const uint8_t command_magic[4] = {'P', 'R', 'P', 'C'};
static const uint8_t ack_magic[4] = {'P', 'R', 'P', 'A'};

static void write_u64(uint8_t *out, uint64_t value) {
    for (unsigned n = 0; n < 8u; ++n) out[n] = (uint8_t)(value >> (8u * n));
}

static uint64_t read_u64(const uint8_t *wire) {
    uint64_t value = 0;
    for (unsigned n = 0; n < 8u; ++n) value |= (uint64_t)wire[n] << (8u * n);
    return value;
}

static bool valid(const rp_police_command *command) {
    return command && command->session && command->target && command->epoch && command->nonce &&
        command->operation >= RP_POLICE_OPT_IN && command->operation <= RP_POLICE_RELEASE_JAIL;
}

static bool same_command(const rp_police_command *a, const rp_police_command *b) {
    return b && a->session == b->session && a->epoch == b->epoch && a->target == b->target &&
        a->nonce == b->nonce && a->operation == b->operation;
}

static void encode(const uint8_t *magic, const rp_police_command *command,
                   uint8_t result, uint8_t *out) {
    memcpy(out, magic, 4);
    out[4] = 1;
    out[5] = (uint8_t)command->operation;
    out[6] = result;
    out[7] = 0;
    write_u64(out + 8, command->session);
    write_u64(out + 16, command->target);
    write_u64(out + 24, command->epoch);
    write_u64(out + 32, command->nonce);
}

static bool decode(const uint8_t *magic, const uint8_t *wire, size_t size,
                   rp_police_command *command) {
    if (!wire || size != RP_POLICE_TX_BYTES || memcmp(wire, magic, 4) ||
        wire[4] != 1 || wire[7]) return false;
    *command = (rp_police_command){
        .session = read_u64(wire + 8), .target = read_u64(wire + 16),
        .epoch = read_u64(wire + 24), .nonce = read_u64(wire + 32),
        .operation = (rp_police_operation)wire[5]
    };
    return valid(command);
}

bool rp_police_tx_encode(const rp_police_command *command, uint8_t *out, size_t size) {
    if (!out || size != RP_POLICE_TX_BYTES || !valid(command)) return false;
    encode(command_magic, command, 0, out);
    return true;
}

bool rp_police_tx_decode_command(const uint8_t *wire, size_t size, rp_police_command *out) {
    if (!out) return false;
    *out = (rp_police_command){0};
    rp_police_command parsed;
    if (!decode(command_magic, wire, size, &parsed) || wire[6]) return false;
    *out = parsed;
    return true;
}

bool rp_police_tx_dispatch(rp_police_world *world, const rp_v133_delivery *delivery,
                          const rp_police_observation *observation,
                          const uint8_t *wire, size_t wire_size,
                          uint8_t *ack, size_t ack_size) {
    rp_police_command command;
    rp_police_member actor;
    if (!world || !delivery || delivery->authenticated != 1 || !ack ||
        ack_size != RP_POLICE_TX_BYTES || !rp_police_tx_decode_command(wire, wire_size, &command) ||
        command.session != world->session || command.epoch != world->epoch ||
        delivery->transport_session != world->session || delivery->transport_epoch != world->epoch ||
        !rp_police_get(world, delivery->transport_sender, &actor) ||
        command.nonce < actor.last_nonce) return false;

    bool applied;
    if (command.nonce == actor.last_nonce) {
        if (command.target != actor.last_target || command.operation != actor.last_operation)
            return false;
        applied = actor.last_applied;
    } else {
        applied = rp_police_apply(world, delivery, &command, observation);
    }
    encode(ack_magic, &command, applied ? RP_POLICE_TX_APPLIED : RP_POLICE_TX_DENIED, ack);
    return true;
}

bool rp_police_tx_decode_ack(const uint8_t *wire, size_t size,
                            const rp_police_command *pending, rp_police_ack *out) {
    if (!out) return false;
    const rp_police_command expected = pending ? *pending : (rp_police_command){0};
    *out = (rp_police_ack){0};
    rp_police_command command;
    if (!decode(ack_magic, wire, size, &command) ||
        !same_command(&command, &expected) ||
        (wire[6] != RP_POLICE_TX_DENIED && wire[6] != RP_POLICE_TX_APPLIED)) return false;
    out->command = command;
    out->outcome = (rp_police_tx_outcome)wire[6];
    return true;
}
