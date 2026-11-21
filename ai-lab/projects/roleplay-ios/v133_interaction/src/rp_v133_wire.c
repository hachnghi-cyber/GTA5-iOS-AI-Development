#include "rp_v133_wire.h"

static int valid_action(const rp_v133_action *action) {
    return action && action->session_id && action->receiver &&
           action->epoch && action->nonce &&
           (action->kind == RP_V133_GREET || action->kind == RP_V133_DOCUMENTS);
}

static void write_le64(uint8_t *out, uint64_t n) {
    for (unsigned i=0; i<8; ++i) {
        out[i] = (uint8_t)(n & UINT64_C(255));
        n >>= 8;
    }
}

static uint64_t read_le64(const uint8_t *in) {
    uint64_t value=0;
    for (unsigned i=0; i<8; ++i)
        value |= (uint64_t)in[i] << (8u*i);
    return value;
}

int rp_v133_wire_encode(const rp_v133_action *action,
                        uint8_t *out, size_t out_len) {
    if (!out || out_len != RP_V133_WIRE_BYTES || !valid_action(action))
        return 0;
    uint8_t frame[RP_V133_WIRE_BYTES] = {0};
    frame[0] = 'P';
    frame[1] = 'R';
    frame[2] = 'P';
    frame[3] = '3';
    frame[4] = RP_V133_WIRE_VERSION;
    frame[5] = (uint8_t)action->kind;
    write_le64(frame+8, action->session_id);
    write_le64(frame+16, action->receiver);
    write_le64(frame+24, action->epoch);
    write_le64(frame+32, action->nonce);
    for (unsigned i=0; i<RP_V133_WIRE_BYTES; ++i)
        out[i] = frame[i];
    return 1;
}

int rp_v133_wire_decode(const uint8_t *bytes, size_t size,
                        rp_v133_action *out) {
    if (!out) return 0;
    *out = (rp_v133_action){0};
    if (!bytes || size != RP_V133_WIRE_BYTES ||
        (bytes[0] != 'P' || bytes[1] != 'R' || bytes[2] != 'P' || bytes[3] != '3') ||
        bytes[4] != RP_V133_WIRE_VERSION || bytes[6] || bytes[7])
        return 0;
    rp_v133_action a = {0};
    a.kind = (rp_v133_interaction_kind)bytes[5];
    a.session_id = read_le64(bytes+8);
    a.receiver = read_le64(bytes+16);
    a.epoch = read_le64(bytes+24);
    a.nonce = read_le64(bytes+32);
    if (!valid_action(&a)) return 0;
    *out = a;
    return 1;
}

rp_v133_result rp_v133_wire_deliver(rp_v133_gate *gate,
                                     const rp_v133_delivery *delivery,
                                     const uint8_t *bytes, size_t size) {
    rp_v133_action action = {0};
    if (!rp_v133_wire_decode(bytes, size, &action))
        return RP_V133_DENIED;
    /* Sender is not present in the packet. Never infer it from its contents. */
    return rp_v133_gate_deliver(gate, delivery, &action);
}
