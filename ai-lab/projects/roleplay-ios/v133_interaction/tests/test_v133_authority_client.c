/* Protocol fixtures only. No TLS verification, GTA binding or native rights. */
#ifdef NDEBUG
#error "Authority client tests require assertions"
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "rp_v133_authority_client.h"

enum {SELF = 11, OTHER = 22, SCOPE_BYTES = 24, ROW_BYTES = 80};

static void be64(uint8_t *out, uint64_t value) {
    for (unsigned i = 0; i < 8; ++i) out[7u - i] = (uint8_t)(value >> (8u * i));
}

static void header(uint8_t out[5], uint8_t kind, uint32_t size) {
    out[0] = kind;
    for (unsigned i = 0; i < 4; ++i) out[4u - i] = (uint8_t)(size >> (8u * i));
}

static void welcome(uint8_t out[40], uint64_t id, uint64_t session, uint64_t epoch,
                    uint64_t nonce) {
    memcpy(out, "PRPSRV01", 8);
    be64(out + 8, id);
    be64(out + 16, session);
    be64(out + 24, epoch);
    be64(out + 32, nonce);
}

static void ready(rp_authority_client *client, uint64_t nonce) {
    uint8_t payload[40];
    assert(rp_authority_client_init(client, SELF));
    assert(!client->ready && !client->revision && !client->member_count);
    welcome(payload, SELF, 123, 7, nonce);
    assert(rp_authority_client_receive(client, RP_AUTHORITY_WELCOME, payload, sizeof payload));
    assert(client->ready && client->expected_id == SELF && client->session == 123 &&
           client->epoch == 7 && client->last_nonce == nonce);
}

static void stopped(const rp_authority_client *client) {
    assert(!client->ready && !client->pending && !client->expected_id && !client->session &&
           !client->epoch && !client->last_nonce && !client->revision && !client->member_count);
    assert(!client->pending_command.session && !client->pending_command.epoch &&
           !client->pending_command.target && !client->pending_command.nonce &&
           !client->pending_command.operation && !client->last_ack.outcome &&
           !client->last_ack.command.session && !client->last_ack.command.epoch &&
           !client->last_ack.command.target && !client->last_ack.command.nonce &&
           !client->last_ack.command.operation);
    for (unsigned i = 0; i < RP_V133_POLICE_CAPACITY; ++i)
        for (unsigned j = 0; j < RP_AUTHORITY_MEMBER_FIELDS; ++j)
            assert(!client->members[i][j]);
}

static size_t snapshot(uint8_t *out, uint64_t revision, unsigned count) {
    const size_t size = SCOPE_BYTES + count * ROW_BYTES;
    memset(out, 0, size);
    be64(out, 123);
    be64(out + 8, 7);
    be64(out + 16, revision);
    for (unsigned i = 0; i < count; ++i) {
        uint8_t *row = out + SCOPE_BYTES + i * ROW_BYTES;
        be64(row, i == 0 ? SELF : OTHER + i - 1u);
        be64(row + 8, i == 0 ? RP_POLICE_OFFICER : RP_POLICE_CITIZEN);
        be64(row + 16, 1);
    }
    return size;
}

static void ack(const uint8_t request[45], uint8_t out[40], uint8_t outcome) {
    memcpy(out, request + RP_AUTHORITY_HEADER_BYTES, RP_POLICE_TX_BYTES);
    out[3] = 'A';
    out[6] = outcome;
}

static void test_header_bounds(void) {
    const struct {uint8_t kind; uint32_t length;} good[] = {
        {RP_AUTHORITY_WELCOME, 40}, {RP_AUTHORITY_ACK, 40},
        {RP_AUTHORITY_SNAPSHOT, 24}, {RP_AUTHORITY_SNAPSHOT, 104},
        {RP_AUTHORITY_SNAPSHOT, 2584}, {RP_AUTHORITY_PONG, 0}
    }, bad[] = {
        {0, 0}, {7, 0}, {255, 40}, {RP_AUTHORITY_REQUEST, 40}, {RP_AUTHORITY_PING, 0},
        {RP_AUTHORITY_WELCOME, 39}, {RP_AUTHORITY_WELCOME, 41},
        {RP_AUTHORITY_ACK, 0}, {RP_AUTHORITY_ACK, 41}, {RP_AUTHORITY_PONG, 1},
        {RP_AUTHORITY_SNAPSHOT, 23}, {RP_AUTHORITY_SNAPSHOT, 25},
        {RP_AUTHORITY_SNAPSHOT, 2664}, {RP_AUTHORITY_SNAPSHOT, 4096},
        {RP_AUTHORITY_SNAPSHOT, 4097}, {RP_AUTHORITY_SNAPSHOT, UINT32_MAX}
    };
    uint8_t wire[5], kind;
    uint32_t length;
    for (unsigned i = 0; i < sizeof good / sizeof good[0]; ++i) {
        header(wire, good[i].kind, good[i].length);
        assert(rp_authority_record_header(wire, sizeof wire, &kind, &length));
        assert(kind == good[i].kind && length == good[i].length);
    }
    for (unsigned i = 0; i < sizeof bad / sizeof bad[0]; ++i) {
        header(wire, bad[i].kind, bad[i].length);
        kind = 99; length = 99;
        assert(!rp_authority_record_header(wire, sizeof wire, &kind, &length));
        assert(!kind && !length);
    }
    header(wire, RP_AUTHORITY_WELCOME, 40);
    assert(!rp_authority_record_header(NULL, 5, &kind, &length));
    assert(!rp_authority_record_header(wire, 4, &kind, &length));
    assert(!rp_authority_record_header(wire, 6, &kind, &length));
    assert(!rp_authority_record_header(wire, 5, NULL, &length));
    assert(!rp_authority_record_header(wire, 5, &kind, NULL));
}

static void test_welcome_and_disconnect(void) {
    rp_authority_client client;
    assert(!rp_authority_client_init(NULL, SELF));
    assert(!rp_authority_client_init(&client, 0));
    stopped(&client);
    rp_authority_client_stop(NULL);
    uint8_t payload[40];
    for (unsigned invalid = 0; invalid < 5; ++invalid) {
        assert(rp_authority_client_init(&client, SELF));
        welcome(payload, SELF, 123, 7, 4);
        if (invalid == 0) payload[0] = 'X';
        if (invalid == 1) be64(payload + 8, OTHER);
        if (invalid == 2) be64(payload + 16, 0);
        if (invalid == 3) be64(payload + 24, 0);
        assert(!rp_authority_client_receive(&client, RP_AUTHORITY_WELCOME,
                                            payload, invalid == 4 ? 39 : 40));
        stopped(&client);
    }
    assert(rp_authority_client_init(&client, SELF));
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_PONG, NULL, 0));
    stopped(&client);
    ready(&client, 4);
    welcome(payload, SELF, 123, 7, 4);
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_WELCOME, payload, 40));
    stopped(&client);
    ready(&client, 4);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_PONG, NULL, 0));
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_ACK, NULL, 40));
    stopped(&client);
    ready(&client, 4);
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_REQUEST, payload, 40));
    stopped(&client);
    assert(!rp_authority_client_receive(NULL, RP_AUTHORITY_WELCOME, payload, 40));
}

static void test_request_and_historical_ack(void) {
    rp_authority_client client;
    ready(&client, 7);
    uint8_t state[SCOPE_BYTES + 2 * ROW_BYTES], request[45], output[45], reply[40], ping[5];
    const size_t state_size = snapshot(state, 1, 2);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, state, state_size));
    memset(output, 0xa5, sizeof output);
    uint8_t before[sizeof client];
    memcpy(before, &client, sizeof client);
    assert(!rp_authority_client_request(NULL, RP_POLICE_CUFF, OTHER, output, 45));
    assert(!rp_authority_client_request(&client, RP_POLICE_CUFF, OTHER, NULL, 45));
    assert(!rp_authority_client_request(&client, RP_POLICE_CUFF, OTHER, output, 44));
    assert(!rp_authority_client_request(&client, RP_POLICE_CUFF, OTHER, output, 46));
    assert(!rp_authority_client_request(&client, (rp_police_operation)0, OTHER, output, 45));
    assert(!rp_authority_client_request(&client, (rp_police_operation)13, OTHER, output, 45));
    assert(!rp_authority_client_request(&client, RP_POLICE_CUFF, 0, output, 45));
    assert(!memcmp(before, &client, sizeof client));
    for (unsigned i = 0; i < sizeof output; ++i) assert(output[i] == 0xa5);

    assert(rp_authority_client_request(&client, RP_POLICE_CUFF, OTHER, request, sizeof request));
    const uint8_t expected_header[5] = {2, 0, 0, 0, 40};
    assert(!memcmp(request, expected_header, sizeof expected_header));
    rp_police_command decoded;
    assert(rp_police_tx_decode_command(request + 5, 40, &decoded));
    assert(decoded.session == 123 && decoded.epoch == 7 && decoded.target == OTHER &&
           decoded.operation == RP_POLICE_CUFF && decoded.nonce == 8);
    assert(client.pending && client.last_nonce == 8 && !client.last_ack.outcome);
    assert(!rp_authority_client_request(&client, RP_POLICE_OPT_OUT, SELF, output, sizeof output));
    assert(client.pending && client.last_nonce == 8);
    assert(rp_authority_client_ping(&client, ping, sizeof ping));
    const uint8_t expected_ping[5] = {5, 0, 0, 0, 0};
    assert(!memcmp(ping, expected_ping, sizeof ping));
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_PONG, NULL, 0));
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, state, state_size));
    assert(client.pending);
    ack(request, reply, RP_POLICE_TX_APPLIED);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    assert(!client.pending && client.last_ack.outcome == RP_POLICE_TX_APPLIED &&
           client.last_ack.command.nonce == 8 && !client.pending_command.nonce);
    /* An applied historical cuff ACK does not cuff a snapshot's free target. */
    assert(client.revision == 1 && client.members[1][4] == RP_POLICE_FREE);
    be64(state + 16, 2);
    be64(state + SCOPE_BYTES + ROW_BYTES + 4 * 8, RP_POLICE_CUFFED);
    be64(state + SCOPE_BYTES + ROW_BYTES + 5 * 8, SELF);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, state, state_size));
    assert(client.members[1][4] == RP_POLICE_CUFFED);
    assert(rp_authority_client_request(&client, RP_POLICE_UNCUFF, OTHER, request, sizeof request));
    assert(client.last_nonce == 9 && !client.last_ack.outcome);
    ack(request, reply, RP_POLICE_TX_DENIED);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    assert(client.members[1][4] == RP_POLICE_CUFFED && client.revision == 2);
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    stopped(&client);
    assert(!rp_authority_client_ping(&client, ping, sizeof ping));
    assert(!rp_authority_client_request(&client, RP_POLICE_OPT_IN, SELF, request, sizeof request));
}

static void test_mismatched_ack_clears_pending_and_snapshot(void) {
    const unsigned offsets[] = {0, 4, 5, 6, 7, 8, 16, 24, 32};
    for (unsigned i = 0; i < sizeof offsets / sizeof offsets[0]; ++i) {
        rp_authority_client client;
        ready(&client, 0);
        uint8_t state[104], request[45], reply[40];
        snapshot(state, 1, 1);
        assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, state, sizeof state));
        assert(rp_authority_client_request(&client, RP_POLICE_OPT_IN, SELF, request, sizeof request));
        ack(request, reply, RP_POLICE_TX_APPLIED);
        reply[offsets[i]] ^= 1;
        assert(!rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
        stopped(&client);
    }
}

static void test_snapshot_validation_and_revisions(void) {
    const struct {unsigned offset; uint64_t value;} invalid[] = {
        {0, 999}, {8, 8}, {16, 0}, {16, 2},
        {24, 0}, {24, 99}, {32, 0}, {32, 3}, {40, 2}, {48, 2}, {56, 5}, {80, 3},
        {104, SELF}
    };
    uint8_t original[184], broken[184];
    snapshot(original, 3, 2);
    for (unsigned i = 0; i < sizeof invalid / sizeof invalid[0]; ++i) {
        rp_authority_client client;
        ready(&client, 4);
        assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, original, sizeof original));
        memcpy(broken, original, sizeof broken);
        be64(broken + invalid[i].offset, invalid[i].value);
        assert(!rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, broken, sizeof broken));
        stopped(&client);
    }
    rp_authority_client client;
    ready(&client, 4);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, original, sizeof original));
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, original, sizeof original));
    memcpy(broken, original, sizeof broken);
    be64(broken + 104 + 16, 0); /* Different content under the same revision. */
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, broken, sizeof broken));
    stopped(&client);

    ready(&client, 4);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, original, sizeof original));
    uint8_t smaller[104];
    snapshot(smaller, 4, 1);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, smaller, sizeof smaller));
    assert(client.member_count == 1 && client.revision == 4);
    for (unsigned i = 1; i < RP_V133_POLICE_CAPACITY; ++i)
        for (unsigned j = 0; j < RP_AUTHORITY_MEMBER_FIELDS; ++j)
            assert(!client.members[i][j]);
    const size_t bad_sizes[] = {0, 23, 24, 25, 103, 105, 2664, 4097, SIZE_MAX};
    for (unsigned i = 0; i < sizeof bad_sizes / sizeof bad_sizes[0]; ++i) {
        ready(&client, 4);
        /* 24 is structurally valid framing but lacks the required own row. */
        assert(!rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, smaller, bad_sizes[i]));
        stopped(&client);
    }
    ready(&client, 4);
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, NULL, 104));
    stopped(&client);
    uint8_t full[24 + 32 * 80];
    snapshot(full, UINT64_MAX, 32);
    ready(&client, 4);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, full, sizeof full));
    assert(client.member_count == 32 && client.revision == UINT64_MAX);
    rp_authority_client_stop(&client);
    stopped(&client);
}

static void test_uint64_and_nonce_exhaustion(void) {
    rp_authority_client client;
    uint8_t hello[40], state[104], request[45], reply[40], ping[5];
    assert(rp_authority_client_init(&client, UINT64_MAX));
    welcome(hello, UINT64_MAX, UINT64_MAX - 1, UINT64_MAX - 2, UINT64_MAX - 1);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_WELCOME, hello, sizeof hello));
    snapshot(state, UINT64_MAX, 1);
    be64(state, UINT64_MAX - 1);
    be64(state + 8, UINT64_MAX - 2);
    be64(state + 24, UINT64_MAX);
    be64(state + 24 + 9 * 8, UINT64_MAX - 1);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, state, sizeof state));
    assert(client.expected_id == UINT64_MAX && client.members[0][0] == UINT64_MAX &&
           client.members[0][9] == UINT64_MAX - 1 && client.revision == UINT64_MAX);
    assert(rp_authority_client_request(&client, RP_POLICE_OPT_IN, UINT64_MAX, request, sizeof request));
    rp_police_command command;
    assert(rp_police_tx_decode_command(request + 5, 40, &command));
    assert(command.nonce == UINT64_MAX && command.target == UINT64_MAX &&
           command.session == UINT64_MAX - 1 && command.epoch == UINT64_MAX - 2);
    ack(request, reply, RP_POLICE_TX_DENIED);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    uint8_t before[sizeof client];
    memcpy(before, &client, sizeof client);
    assert(!rp_authority_client_request(&client, RP_POLICE_OPT_IN, UINT64_MAX, request, sizeof request));
    assert(!memcmp(before, &client, sizeof client));
    assert(rp_authority_client_ping(&client, ping, sizeof ping));
    assert(!rp_authority_client_ping(NULL, ping, sizeof ping));
    assert(!rp_authority_client_ping(&client, NULL, sizeof ping));
    assert(!rp_authority_client_ping(&client, ping, 4));
    rp_authority_client_stop(&client);
    stopped(&client);
    assert(!rp_authority_client_receive(&client, RP_AUTHORITY_WELCOME, hello, sizeof hello));
    assert(rp_authority_client_init(&client, UINT64_MAX));
    be64(hello + 32, UINT64_MAX);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_WELCOME, hello, sizeof hello));
    assert(!rp_authority_client_request(&client, RP_POLICE_OPT_IN, UINT64_MAX, request, sizeof request));
    rp_authority_client_stop(&client);
    stopped(&client);
}

static void test_consent_probe_requires_ack_and_current_snapshot(void) {
    rp_authority_client client;
    rp_consent_probe_phase phase = RP_CONSENT_PROBE_INITIAL;
    uint8_t request[45], reply[40], members[104];
    ready(&client, 5);
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_WAIT);
    snapshot(members, 1, 1);
    be64(members + SCOPE_BYTES + 16, 0);
    be64(members + SCOPE_BYTES + 72, 5);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, members, sizeof members));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_SEND);
    ack(request, reply, RP_POLICE_TX_APPLIED);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_WAIT);
    be64(members + 16, 2);
    be64(members + SCOPE_BYTES + 16, 1);
    be64(members + SCOPE_BYTES + 72, 6);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, members, sizeof members));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_SEND);
    be64(members + 16, 3);
    be64(members + SCOPE_BYTES + 16, 0);
    be64(members + SCOPE_BYTES + 72, 7);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, members, sizeof members));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_WAIT);
    ack(request, reply, RP_POLICE_TX_APPLIED);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_PASSED);
}

static void test_consent_probe_rejects_denied_ack_and_preexisting_consent(void) {
    rp_authority_client client;
    rp_consent_probe_phase phase = RP_CONSENT_PROBE_INITIAL;
    uint8_t members[104], request[45], reply[40];
    ready(&client, 0);
    snapshot(members, 1, 1);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, members, sizeof members));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_FAILED);
    be64(members + 16, 2);
    be64(members + SCOPE_BYTES + 16, 0);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_SNAPSHOT, members, sizeof members));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_SEND);
    ack(request, reply, RP_POLICE_TX_DENIED);
    assert(rp_authority_client_receive(&client, RP_AUTHORITY_ACK, reply, sizeof reply));
    assert(rp_authority_consent_probe_step(&client, &phase, request, sizeof request) == RP_CONSENT_PROBE_FAILED);
}

int main(void) {
    test_header_bounds();
    test_welcome_and_disconnect();
    test_request_and_historical_ack();
    test_mismatched_ack_clears_pending_and_snapshot();
    test_snapshot_validation_and_revisions();
    test_uint64_and_nonce_exhaustion();
    test_consent_probe_requires_ack_and_current_snapshot();
    test_consent_probe_rejects_denied_ack_and_preexisting_consent();
    puts("Authority client codec: PASS (protocol fixtures; no TLS or GTA authorization)");
    return 0;
}
