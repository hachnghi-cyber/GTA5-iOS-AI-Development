#include "rp_v133_authority_social.h"

static uint64_t read_be64(const uint8_t *wire) {
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8u) | wire[i];
    return value;
}

static void write_be64(uint8_t *wire, uint64_t value) {
    for (unsigned i = 0; i < 8; ++i) wire[i] = (uint8_t)(value >> (56u - 8u*i));
}

static void write_header(uint8_t *out, uint8_t kind, uint8_t length) {
    out[0] = kind;
    out[1] = out[2] = out[3] = 0;
    out[4] = length;
}

void rp_authority_social_stop(rp_authority_social *social) {
    if (social) *social = (rp_authority_social){0};
}

bool rp_authority_social_open(rp_authority_social *social, const rp_authority_client *client,
                              uint8_t *out, size_t size) {
    if (!social || social->self || !client || !client->ready || !client->expected_id ||
        !client->session || !client->epoch || !out || size != RP_AUTHORITY_HEADER_BYTES) return false;
    *social = (rp_authority_social){.self = client->expected_id, .session = client->session, .epoch = client->epoch};
    write_header(out, RP_AUTHORITY_SOCIAL_OPEN, 0);
    return true;
}

bool rp_authority_social_request(rp_authority_social *social, rp_v133_interaction_kind kind,
                                 uint64_t target, uint8_t *out, size_t size) {
    if (!social || !social->ready || social->pending_nonce || social->last_nonce == UINT64_MAX ||
        !target || target == social->self || !out || size != RP_AUTHORITY_SOCIAL_REQUEST_BYTES) return false;
    const rp_v133_action action = {.session_id = social->session, .receiver = target,
        .nonce = social->last_nonce + 1u, .epoch = social->epoch, .kind = kind};
    if (!rp_v133_wire_encode(&action, out + RP_AUTHORITY_HEADER_BYTES, RP_V133_WIRE_BYTES)) return false;
    write_header(out, RP_AUTHORITY_SOCIAL_REQUEST, RP_V133_WIRE_BYTES);
    social->last_nonce = social->pending_nonce = action.nonce;
    social->last_result = 0;
    return true;
}

static bool receive_event(rp_authority_social *social, const uint8_t *payload, size_t size,
                          uint8_t *receipt, size_t receipt_size) {
    if (size != 8u + RP_V133_WIRE_BYTES || !receipt || receipt_size != RP_AUTHORITY_SOCIAL_RECEIPT_BYTES)
        return false;
    const uint64_t sender = read_be64(payload);
    rp_v133_action action;
    if (!sender || sender == social->self ||
        !rp_v133_wire_decode(payload + 8, RP_V133_WIRE_BYTES, &action) ||
        action.session_id != social->session || action.epoch != social->epoch || action.receiver != social->self)
        return false;
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i) {
        if (social->seen[i].sender && social->seen[i].sender != sender) continue;
        if (action.nonce <= social->seen[i].nonce) return false;
        social->seen[i].sender = sender;
        social->seen[i].nonce = action.nonce;
        social->last_sender = sender;
        social->last_kind = action.kind;
        write_header(receipt, RP_AUTHORITY_SOCIAL_RECEIPT, 16);
        write_be64(receipt + 5, sender);
        write_be64(receipt + 13, action.nonce);
        return true;
    }
    return false;
}

bool rp_authority_social_receive(rp_authority_social *social, uint8_t kind,
                                 const uint8_t *payload, size_t size,
                                 uint8_t *receipt, size_t receipt_size) {
    if (!social || !social->self || !payload) return false;
    if (!social->ready) {
        if (kind != RP_AUTHORITY_SOCIAL_STATE || size != 8) return false;
        social->last_nonce = read_be64(payload);
        social->ready = true;
        return true;
    }
    if (kind == RP_AUTHORITY_SOCIAL_EVENT) return receive_event(social, payload, size, receipt, receipt_size);
    if (kind != RP_AUTHORITY_SOCIAL_RESULT || size != 9 || !social->pending_nonce ||
        read_be64(payload) != social->pending_nonce || payload[8] < 1 || payload[8] > 3) return false;
    social->pending_nonce = 0;
    social->last_result = payload[8];
    return true;
}
