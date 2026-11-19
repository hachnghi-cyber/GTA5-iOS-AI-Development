#include "rp_v133_authority_client.h"
#include <string.h>

#define WELCOME_BYTES 40u
#define SCOPE_BYTES 24u
#define ROW_BYTES (8u * RP_AUTHORITY_MEMBER_FIELDS)

static uint64_t read_be64(const uint8_t *wire) {
    uint64_t result = 0;
    for (unsigned i = 0; i < 8u; ++i) result = (result << 8u) | wire[i];
    return result;
}

static bool inbound_size(uint8_t kind, size_t size) {
    if (size > RP_AUTHORITY_MAX_RECORD_BYTES) return false;
    switch (kind) {
        case RP_AUTHORITY_WELCOME:
            return size == WELCOME_BYTES;
        case RP_AUTHORITY_ACK:
            return size == RP_POLICE_TX_BYTES;
        case RP_AUTHORITY_SNAPSHOT:
            return size >= SCOPE_BYTES &&
                size <= SCOPE_BYTES + RP_V133_POLICE_CAPACITY * ROW_BYTES &&
                (size - SCOPE_BYTES) % ROW_BYTES == 0;
        case RP_AUTHORITY_PONG:
            return size == 0;
        default:
            return false;
    }
}

void rp_authority_client_stop(rp_authority_client *client) {
    if (client) *client = (rp_authority_client){0};
}

bool rp_authority_client_init(rp_authority_client *client, uint64_t expected_id) {
    if (!client) return false;
    rp_authority_client_stop(client);
    if (!expected_id) return false;
    client->expected_id = expected_id;
    return true;
}

bool rp_authority_record_header(const uint8_t *wire, size_t size,
                                 uint8_t *kind, uint32_t *payload_size) {
    if (kind) *kind = 0;
    if (payload_size) *payload_size = 0;
    if (!wire || size != RP_AUTHORITY_HEADER_BYTES || !kind || !payload_size)
        return false;
    const uint32_t length = ((uint32_t)wire[1] << 24u) | ((uint32_t)wire[2] << 16u) |
                            ((uint32_t)wire[3] << 8u) | wire[4];
    if (!inbound_size(wire[0], length)) return false;
    *kind = wire[0];
    *payload_size = length;
    return true;
}

static bool welcome(rp_authority_client *client, const uint8_t *payload) {
    if (memcmp(payload, "PRPSRV01", 8) || read_be64(payload + 8) != client->expected_id)
        return false;
    const uint64_t session = read_be64(payload + 16);
    const uint64_t epoch = read_be64(payload + 24);
    if (!session || !epoch) return false;
    client->session = session;
    client->epoch = epoch;
    client->last_nonce = read_be64(payload + 32);
    client->ready = true;
    return true;
}

static bool snapshot(rp_authority_client *client, const uint8_t *payload, size_t size) {
    const uint64_t revision = read_be64(payload + 16);
    if (read_be64(payload) != client->session || read_be64(payload + 8) != client->epoch ||
        !revision || revision < client->revision) return false;
    const uint32_t count = (uint32_t)((size - SCOPE_BYTES) / ROW_BYTES);
    uint64_t rows[RP_V133_POLICE_CAPACITY][RP_AUTHORITY_MEMBER_FIELDS] = {{0}};
    bool found_self = false;
    for (uint32_t i = 0; i < count; ++i) {
        for (unsigned j = 0; j < RP_AUTHORITY_MEMBER_FIELDS; ++j)
            rows[i][j] = read_be64(payload + SCOPE_BYTES + i * ROW_BYTES + j * 8u);
        const uint64_t *row = rows[i];
        if (!row[0] || (row[1] != RP_POLICE_CITIZEN && row[1] != RP_POLICE_OFFICER) ||
            row[2] > 1 || row[3] > 1 || row[4] > RP_POLICE_JAILED ||
            row[7] > 2) return false;
        for (uint32_t other = 0; other < i; ++other)
            if (rows[other][0] == row[0]) return false;
        if (row[0] == client->expected_id) found_self = true;
    }
    if (!found_self) return false;
    if (revision == client->revision) {
        return count == client->member_count &&
            !memcmp(rows, client->members, sizeof rows);
    }
    memcpy(client->members, rows, sizeof rows);
    client->member_count = count;
    client->revision = revision;
    return true;
}

bool rp_authority_client_receive(rp_authority_client *client, uint8_t kind,
                                  const uint8_t *payload, size_t size) {
    if (!client) return false;
    bool accepted = false;
    if (client->expected_id && inbound_size(kind, size) && (payload || !size)) {
        if (!client->ready) {
            accepted = kind == RP_AUTHORITY_WELCOME && welcome(client, payload);
        } else if (kind == RP_AUTHORITY_SNAPSHOT) {
            accepted = snapshot(client, payload, size);
        } else if (kind == RP_AUTHORITY_ACK && client->pending) {
            rp_police_ack ack;
            accepted = rp_police_tx_decode_ack(payload, size, &client->pending_command, &ack);
            if (accepted) {
                client->last_ack = ack;
                client->pending = false;
                client->pending_command = (rp_police_command){0};
            }
        } else if (kind == RP_AUTHORITY_PONG) {
            accepted = true;
        }
    }
    if (!accepted) rp_authority_client_stop(client);
    return accepted;
}

bool rp_authority_client_request(rp_authority_client *client,
                                  rp_police_operation operation, uint64_t target,
                                  uint8_t *out, size_t size) {
    if (!client || !client->ready || client->pending || !out ||
        size != RP_AUTHORITY_REQUEST_BYTES || client->last_nonce == UINT64_MAX)
        return false;
    const rp_police_command command = {
        client->session, client->epoch, target, client->last_nonce + 1u, operation
    };
    uint8_t record[RP_AUTHORITY_REQUEST_BYTES] = {RP_AUTHORITY_REQUEST, 0, 0, 0, RP_POLICE_TX_BYTES};
    if (!rp_police_tx_encode(&command, record + RP_AUTHORITY_HEADER_BYTES, RP_POLICE_TX_BYTES))
        return false;
    memcpy(out, record, sizeof record);
    client->pending_command = command;
    client->pending = true;
    client->last_nonce = command.nonce;
    client->last_ack = (rp_police_ack){0};
    return true;
}

bool rp_authority_client_ping(const rp_authority_client *client, uint8_t *out, size_t size) {
    if (!client || !client->ready || !out || size != RP_AUTHORITY_HEADER_BYTES) return false;
    const uint8_t record[RP_AUTHORITY_HEADER_BYTES] = {RP_AUTHORITY_PING, 0, 0, 0, 0};
    memcpy(out, record, sizeof record);
    return true;
}

rp_consent_probe_result rp_authority_consent_probe_step(rp_authority_client *client,
    rp_consent_probe_phase *phase, uint8_t *out, size_t size) {
    if (!client || !client->ready || !phase || !out || size != RP_AUTHORITY_REQUEST_BYTES)
        return RP_CONSENT_PROBE_FAILED;
    if (!client->revision || client->pending) return RP_CONSENT_PROBE_WAIT;

    const uint64_t *self = NULL;
    for (uint32_t i = 0; i < client->member_count; ++i) {
        if (client->members[i][0] == client->expected_id) {
            self = client->members[i];
            break;
        }
    }
    if (!self || self[3] || self[4] || self[9] > client->last_nonce)
        return RP_CONSENT_PROBE_FAILED;

    rp_police_operation next;
    rp_consent_probe_phase next_phase;
    if (*phase == RP_CONSENT_PROBE_INITIAL) {
        if (self[2] || self[9] != client->last_nonce || client->last_nonce >= UINT64_MAX - 1u)
            return RP_CONSENT_PROBE_FAILED;
        next = RP_POLICE_OPT_IN;
        next_phase = RP_CONSENT_PROBE_OPTING_IN;
    } else {
        const rp_police_ack *ack = &client->last_ack;
        const bool opting_in = *phase == RP_CONSENT_PROBE_OPTING_IN;
        if (!opting_in && *phase != RP_CONSENT_PROBE_OPTING_OUT)
            return RP_CONSENT_PROBE_FAILED;
        if (ack->outcome != RP_POLICE_TX_APPLIED || ack->command.target != client->expected_id ||
            ack->command.nonce != client->last_nonce ||
            ack->command.operation != (opting_in ? RP_POLICE_OPT_IN : RP_POLICE_OPT_OUT))
            return RP_CONSENT_PROBE_FAILED;
        if (self[9] < client->last_nonce) return RP_CONSENT_PROBE_WAIT;
        if (self[2] != (uint64_t)opting_in) return RP_CONSENT_PROBE_FAILED;
        if (!opting_in) return RP_CONSENT_PROBE_PASSED;
        next = RP_POLICE_OPT_OUT;
        next_phase = RP_CONSENT_PROBE_OPTING_OUT;
    }
    if (!rp_authority_client_request(client, next, client->expected_id, out, size))
        return RP_CONSENT_PROBE_FAILED;
    *phase = next_phase;
    return RP_CONSENT_PROBE_SEND;
}
