/* In-process modeled authority observations only; no GTA or device binding. */
#ifdef NDEBUG
#error "Server FFI tests require assertions"
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../server/rp_authority_ffi.h"
#include "rp_v133_police_tx.h"

enum {COP = 11, PLAYER = 22};
enum {ID, ROLE, CONSENT, DUTY, CUSTODY, CUSTODIAN, VEHICLE, SEAT, JAIL_UNTIL, NONCE};

static void *create(void) {
    void *server = rp_server_create(123, 7);
    assert(server);
    assert(rp_server_admit(server, COP, RP_POLICE_OFFICER));
    assert(rp_server_admit(server, PLAYER, RP_POLICE_CITIZEN));
    assert(rp_server_tick(server, 1000));
    return server;
}

static uint64_t value(void *server, uint64_t id, unsigned field) {
    uint64_t out[RP_SERVER_SNAPSHOT_COUNT];
    assert(field < RP_SERVER_SNAPSHOT_COUNT);
    assert(rp_server_snapshot(server, id, out, RP_SERVER_SNAPSHOT_COUNT));
    return out[field];
}

static int command(void *server, uint64_t actor, uint64_t target, uint64_t nonce,
                   rp_police_operation operation, const uint64_t *facts,
                   rp_police_tx_outcome outcome) {
    const rp_police_command request = {123, 7, target, nonce, operation};
    uint8_t wire[RP_POLICE_TX_BYTES], ack[RP_POLICE_TX_BYTES];
    assert(rp_police_tx_encode(&request, wire, sizeof wire));
    memset(ack, 0xa5, sizeof ack);
    const int accepted = rp_server_dispatch(server, actor, 1000, wire, sizeof wire,
                                            facts, facts ? RP_SERVER_FACT_COUNT : 0,
                                            ack, sizeof ack);
    if (outcome) {
        rp_police_ack result;
        assert(accepted);
        assert(rp_police_tx_decode_ack(ack, sizeof ack, &request, &result));
        assert(result.outcome == outcome);
    } else {
        assert(!accepted);
        for (unsigned i = 0; i < sizeof ack; ++i) assert(ack[i] == 0xa5);
    }
    return accepted;
}

static void opt_in(void *server) {
    command(server, COP, COP, 1, RP_POLICE_OPT_IN, NULL, RP_POLICE_TX_APPLIED);
    command(server, PLAYER, PLAYER, 1, RP_POLICE_OPT_IN, NULL, RP_POLICE_TX_APPLIED);
}

static void ready(void *server) {
    opt_in(server);
    const uint64_t facts[RP_SERVER_FACT_COUNT] = {1000, 0, 0, 0, 3, COP, COP};
    command(server, COP, COP, 2, RP_POLICE_DUTY_START, facts, RP_POLICE_TX_APPLIED);
}

static void test_abi_and_bounds(void) {
    assert(rp_server_abi() == 1);
    assert(!rp_server_create(0, 7));
    assert(!rp_server_create(123, 0));
    rp_server_destroy(NULL);
    assert(!rp_server_admit(NULL, COP, RP_POLICE_OFFICER));
    assert(!rp_server_leave(NULL, COP));
    assert(!rp_server_tick(NULL, 1000));
    void *server = create();
    assert(!rp_server_admit(server, 0, RP_POLICE_CITIZEN));
    assert(!rp_server_admit(server, 33, UINT32_MAX));
    assert(!rp_server_admit(server, COP, RP_POLICE_OFFICER));
    assert(!rp_server_leave(server, 33));
    assert(!rp_server_tick(server, 999));
    assert(value(server, COP, ROLE) == RP_POLICE_OFFICER);
    assert(!value(server, COP, CONSENT) && !value(server, COP, DUTY));

    uint64_t out[RP_SERVER_SNAPSHOT_COUNT];
    for (unsigned i = 0; i < RP_SERVER_SNAPSHOT_COUNT; ++i) out[i] = 99;
    assert(!rp_server_snapshot(server, COP, out, RP_SERVER_SNAPSHOT_COUNT - 1));
    for (unsigned i = 0; i < RP_SERVER_SNAPSHOT_COUNT; ++i) assert(out[i] == 99);
    assert(!rp_server_snapshot(server, COP, NULL, RP_SERVER_SNAPSHOT_COUNT));
    assert(!rp_server_snapshot(NULL, COP, out, RP_SERVER_SNAPSHOT_COUNT));
    for (unsigned i = 0; i < RP_SERVER_SNAPSHOT_COUNT; ++i) assert(!out[i]);

    const rp_police_command request = {123, 7, COP, 1, RP_POLICE_OPT_IN};
    uint8_t wire[RP_POLICE_TX_BYTES], ack[RP_POLICE_TX_BYTES];
    assert(rp_police_tx_encode(&request, wire, sizeof wire));
    uint64_t facts[RP_SERVER_FACT_COUNT] = {1000, 0, 0, 0, 3, COP, COP};
    memset(ack, 0xa5, sizeof ack);
    assert(!rp_server_dispatch(NULL, COP, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, 0, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, 33, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, NULL, sizeof wire, NULL, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire - 1, NULL, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire + 1, NULL, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, NULL, 0, NULL, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack - 1));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, NULL, 7, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, facts, 0, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, facts, 6, ack, sizeof ack));
    assert(!rp_server_dispatch(server, COP, 999, wire, sizeof wire, facts, 7, ack, sizeof ack));
    for (unsigned field = 2; field <= 4; ++field) {
        const uint64_t saved = facts[field];
        facts[field] = field == 2 ? UINT64_C(0x100000000) : field == 3 ? 256 : 32;
        assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, facts, 7, ack, sizeof ack));
        facts[field] = saved;
    }
    wire[0] = 'X';
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack));
    wire[0] = 'P';
    wire[8] ^= 1; /* Wrong session. */
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack));
    wire[8] ^= 1;
    wire[24] ^= 1; /* Wrong epoch. */
    assert(!rp_server_dispatch(server, COP, 1000, wire, sizeof wire, NULL, 0, ack, sizeof ack));
    for (unsigned i = 0; i < sizeof ack; ++i) assert(ack[i] == 0xa5);
    assert(!value(server, COP, NONCE) && !value(server, COP, CONSENT));
    command(server, COP, COP, 1, RP_POLICE_OPT_IN, NULL, RP_POLICE_TX_APPLIED);
    rp_server_destroy(server);
}

static void test_facts_and_snapshot(void) {
    void *server = create();
    opt_in(server);
    command(server, COP, COP, 2, RP_POLICE_DUTY_START, NULL, RP_POLICE_TX_DENIED);
    uint64_t facts[RP_SERVER_FACT_COUNT] = {1000, 77, 400, 2, 31, COP, COP};
    command(server, COP, COP, 3, RP_POLICE_DUTY_START, facts, RP_POLICE_TX_APPLIED);
    facts[6] = PLAYER;
    const unsigned fields[] = {5, 6, 0, 0, 4, 4, 2};
    const uint64_t invalid[] = {PLAYER, COP, 749, 1001, 30, 29, 401};
    uint64_t nonce = 3;
    for (unsigned i = 0; i < sizeof fields / sizeof fields[0]; ++i) {
        const unsigned field = fields[i];
        const uint64_t saved = facts[field];
        facts[field] = invalid[i];
        command(server, COP, PLAYER, ++nonce, RP_POLICE_CUFF, facts, RP_POLICE_TX_DENIED);
        facts[field] = saved;
        assert(value(server, PLAYER, CUSTODY) == RP_POLICE_FREE);
    }
    command(server, COP, PLAYER, ++nonce, RP_POLICE_CUFF, NULL, RP_POLICE_TX_DENIED);
    /* Improved facts cannot turn the cached denial into an application. */
    command(server, COP, PLAYER, nonce, RP_POLICE_CUFF, facts, RP_POLICE_TX_DENIED);
    command(server, COP, PLAYER, ++nonce, RP_POLICE_CUFF, facts, RP_POLICE_TX_APPLIED);
    assert(value(server, PLAYER, ID) == PLAYER);
    assert(value(server, PLAYER, ROLE) == RP_POLICE_CITIZEN);
    assert(value(server, PLAYER, CONSENT) == 1);
    assert(value(server, COP, DUTY) == 1);
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_CUFFED);
    assert(value(server, PLAYER, CUSTODIAN) == COP);
    command(server, COP, PLAYER, ++nonce, RP_POLICE_ESCORT_START, facts, RP_POLICE_TX_APPLIED);
    command(server, COP, PLAYER, ++nonce, RP_POLICE_ENTER_SEAT, facts, RP_POLICE_TX_APPLIED);
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_SEATED);
    assert(value(server, PLAYER, VEHICLE) == 77 && value(server, PLAYER, SEAT) == 2);
    command(server, COP, PLAYER, ++nonce, RP_POLICE_EXIT_SEAT, facts, RP_POLICE_TX_APPLIED);
    assert(!value(server, PLAYER, VEHICLE) && !value(server, PLAYER, SEAT));
    command(server, COP, PLAYER, ++nonce, RP_POLICE_JAIL, facts, RP_POLICE_TX_APPLIED);
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_JAILED);
    assert(value(server, PLAYER, JAIL_UNTIL) == 61000);
    assert(value(server, COP, NONCE) == nonce);
    assert(rp_server_tick(server, 60999));
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_JAILED);
    assert(rp_server_tick(server, 61000));
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_FREE);
    assert(!value(server, PLAYER, CUSTODIAN) && !value(server, PLAYER, JAIL_UNTIL));
    rp_server_destroy(server);
}

static void test_revocation_and_admission_replay(void) {
    void *server = create();
    ready(server);
    uint64_t facts[RP_SERVER_FACT_COUNT] = {1000, 0, 400, 0, 3, COP, PLAYER};
    command(server, COP, PLAYER, 3, RP_POLICE_CUFF, facts, RP_POLICE_TX_APPLIED);
    command(server, PLAYER, PLAYER, 2, RP_POLICE_OPT_OUT, NULL, RP_POLICE_TX_APPLIED);
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_FREE);
    /* Retry is the original decision, never the current custody state. */
    command(server, COP, PLAYER, 3, RP_POLICE_CUFF, NULL, RP_POLICE_TX_APPLIED);
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_FREE);
    command(server, COP, PLAYER, 3, RP_POLICE_UNCUFF, facts, 0);
    command(server, COP, PLAYER, 2, RP_POLICE_CUFF, facts, 0);
    command(server, COP, PLAYER, 4, RP_POLICE_CUFF, facts, RP_POLICE_TX_DENIED);
    command(server, PLAYER, PLAYER, 3, RP_POLICE_OPT_IN, NULL, RP_POLICE_TX_APPLIED);
    command(server, COP, PLAYER, 5, RP_POLICE_CUFF, facts, RP_POLICE_TX_APPLIED);
    assert(rp_server_leave(server, PLAYER));
    assert(!rp_server_leave(server, PLAYER));
    uint64_t out[RP_SERVER_SNAPSHOT_COUNT];
    assert(!rp_server_snapshot(server, PLAYER, out, RP_SERVER_SNAPSHOT_COUNT));
    for (unsigned i = 0; i < RP_SERVER_SNAPSHOT_COUNT; ++i) assert(!out[i]);
    assert(!rp_server_admit(server, PLAYER, RP_POLICE_OFFICER));
    assert(rp_server_admit(server, PLAYER, RP_POLICE_CITIZEN));
    assert(!value(server, PLAYER, CONSENT));
    assert(value(server, PLAYER, NONCE) == 3 && value(server, COP, NONCE) == 5);
    command(server, PLAYER, PLAYER, 3, RP_POLICE_OPT_IN, NULL, 0);
    command(server, COP, PLAYER, 5, RP_POLICE_CUFF, facts, 0);
    command(server, PLAYER, PLAYER, 4, RP_POLICE_OPT_IN, NULL, RP_POLICE_TX_APPLIED);
    command(server, COP, PLAYER, 6, RP_POLICE_CUFF, facts, RP_POLICE_TX_APPLIED);
    assert(rp_server_leave(server, COP));
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_FREE);
    assert(!value(server, PLAYER, CUSTODIAN));
    assert(rp_server_admit(server, COP, RP_POLICE_OFFICER));
    assert(!value(server, COP, CONSENT) && !value(server, COP, DUTY));
    assert(value(server, COP, NONCE) == 6);
    command(server, COP, PLAYER, 6, RP_POLICE_CUFF, facts, 0);
    command(server, COP, COP, 7, RP_POLICE_OPT_IN, NULL, RP_POLICE_TX_APPLIED);
    facts[6] = COP;
    command(server, COP, COP, 8, RP_POLICE_DUTY_START, facts, RP_POLICE_TX_APPLIED);
    facts[6] = PLAYER;
    command(server, COP, PLAYER, 9, RP_POLICE_CUFF, facts, RP_POLICE_TX_APPLIED);
    command(server, COP, COP, 10, RP_POLICE_DUTY_END, NULL, RP_POLICE_TX_APPLIED);
    assert(value(server, PLAYER, CUSTODY) == RP_POLICE_FREE);
    rp_server_destroy(server);
}

static void test_full_width_ids_and_nonce(void) {
    const uint64_t id = UINT64_MAX - 2;
    void *server = rp_server_create(UINT64_MAX, UINT64_MAX - 1);
    assert(server);
    assert(rp_server_admit(server, id, RP_POLICE_CITIZEN));
    const rp_police_command request = {
        UINT64_MAX, UINT64_MAX - 1, id, UINT64_MAX, RP_POLICE_OPT_IN
    };
    uint8_t wire[RP_POLICE_TX_BYTES], ack[RP_POLICE_TX_BYTES];
    assert(rp_police_tx_encode(&request, wire, sizeof wire));
    assert(rp_server_dispatch(server, id, UINT64_MAX, wire, sizeof wire,
                              NULL, 0, ack, sizeof ack));
    assert(value(server, id, ID) == id && value(server, id, NONCE) == UINT64_MAX);
    assert(value(server, id, CONSENT) == 1);
    assert(rp_server_leave(server, id));
    assert(rp_server_admit(server, id, RP_POLICE_CITIZEN));
    /* Rejoin must not reset an exhausted nonce ledger. Rotate generation. */
    assert(!rp_server_dispatch(server, id, UINT64_MAX, wire, sizeof wire,
                               NULL, 0, ack, sizeof ack));
    assert(!value(server, id, CONSENT));
    rp_server_destroy(server);
}

int main(void) {
    test_abi_and_bounds();
    test_facts_and_snapshot();
    test_revocation_and_admission_replay();
    test_full_width_ids_and_nonce();
    puts("Server authority FFI: PASS (modeled observations; no GTA or device binding)");
    return 0;
}
