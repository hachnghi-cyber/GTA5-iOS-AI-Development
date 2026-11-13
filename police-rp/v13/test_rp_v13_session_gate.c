#include "rp_v13_session_gate.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned checks = 0u;
#define CHECK(condition) do { ++checks; assert(condition); } while (0)

static RP_V13_IdentityEvidence good_binary(void) {
    const uint8_t app[16] = {0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,
                             0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf};
    const uint8_t compat[16] = {0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,
                                0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc};
    RP_V13_IdentityEvidence e = {0};
    e.abi = RP_V13_IDENTITY_ABI;
    memcpy(e.gta5_uuid, app, sizeof(app));
    memcpy(e.gtacompat_uuid, compat, sizeof(compat));
    e.executable_uuid_verified_by_loader = 1u;
    e.compat_uuid_verified_by_loader = 1u;
    return e;
}
static RP_V13_SessionEvidence good_session(void) {
    RP_V13_SessionEvidence s = {0};
    s.abi = RP_V13_SESSION_ABI;
    s.session_id = 77u;
    s.local_player_id = 10u;
    s.host_player_id = 20u;
    s.monotonic_ms = 1000u;
    s.peer_generation = 1u;
    s.online = s.game_thread_verified = s.session_verified = 1u;
    s.carrier_authenticated = s.local_peer_connected = s.host_peer_connected = 1u;
    return s;
}

static void expect_blocked_on_bad_evidence(void) {
    RP_V13_SessionGate gate;
    RP_V13_IdentityEvidence binary = good_binary();
    RP_V13_SessionEvidence session = good_session();
    RP_V13_SessionEvidence invalid;

    rp_v13_session_gate_init(&gate);
    CHECK(rp_v13_session_gate_update(NULL, &binary, &session) == RP_V13_SESSION_BLOCKED);
    CHECK(rp_v13_session_gate_update(&gate, NULL, &session) == RP_V13_SESSION_BLOCKED);
    CHECK(rp_v13_session_gate_update(&gate, &binary, NULL) == RP_V13_SESSION_BLOCKED);
    invalid = session;
    invalid.abi = 2u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &invalid) == RP_V13_SESSION_BLOCKED);

#define BAD_FIELD(field, value) do { \
    invalid = session; invalid.field = value; \
    CHECK(rp_v13_session_gate_update(&gate, &binary, &invalid) == RP_V13_SESSION_BLOCKED); \
} while (0)
    BAD_FIELD(online, 0u);
    BAD_FIELD(online, 2u);
    BAD_FIELD(game_thread_verified, 0u);
    BAD_FIELD(session_verified, 0u);
    BAD_FIELD(carrier_authenticated, 0u);
    BAD_FIELD(local_peer_connected, 0u);
    BAD_FIELD(host_peer_connected, 0u);
    BAD_FIELD(session_id, 0u);
    BAD_FIELD(local_player_id, 0u);
    BAD_FIELD(host_player_id, 0u);
    BAD_FIELD(peer_generation, 0u);
#undef BAD_FIELD
    binary.gta5_uuid[0] ^= 1u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &session) == RP_V13_SESSION_BLOCKED);
    CHECK(!rp_v13_session_gate_is_ready(&gate));
}

static void expect_release_and_rearm(void) {
    RP_V13_SessionGate gate;
    RP_V13_IdentityEvidence binary = good_binary();
    RP_V13_SessionEvidence s = good_session();
    rp_v13_session_gate_init(&gate);
    rp_v13_session_gate_acknowledge_released(&gate); /* cannot grant readiness */
    CHECK(!rp_v13_session_gate_is_ready(&gate));
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
    CHECK(rp_v13_session_gate_is_ready(&gate));
    s.monotonic_ms += 20u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
    s.monotonic_ms -= 1u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    CHECK(!rp_v13_session_gate_is_ready(&gate));
    s.monotonic_ms += 100u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    rp_v13_session_gate_acknowledge_released(&gate);
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
    s.carrier_authenticated = 0u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    s.carrier_authenticated = 1u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    rp_v13_session_gate_acknowledge_released(&gate);
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
}

static void expect_every_identity_transition(void) {
    unsigned change;
    for (change = 0u; change != 4u; ++change) {
        RP_V13_SessionGate gate;
        RP_V13_IdentityEvidence binary = good_binary();
        RP_V13_SessionEvidence s = good_session();
        rp_v13_session_gate_init(&gate);
        CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
        if (change == 0u) ++s.session_id;
        if (change == 1u) ++s.local_player_id;
        if (change == 2u) ++s.host_player_id;
        if (change == 3u) ++s.peer_generation;
        CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
        CHECK(!rp_v13_session_gate_is_ready(&gate));
        CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
        rp_v13_session_gate_acknowledge_released(&gate);
        CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
    }
}

typedef struct {
    unsigned calls;
    int result;
} StopProbe;

static int fake_stop_local(void *ctx) {
    StopProbe *p = (StopProbe *)ctx;
    if (!p) return 0;
    ++p->calls;
    return p->result;
}

static void expect_release_requires_successful_stop(void) {
    RP_V13_SessionGate gate;
    RP_V13_IdentityEvidence binary = good_binary();
    RP_V13_SessionEvidence s = good_session();
    StopProbe probe = {0u, 0};
    rp_v13_session_gate_init(&gate);
    CHECK(rp_v13_session_gate_release_with_stop(NULL, fake_stop_local, &probe) == 0);
    CHECK(rp_v13_session_gate_release_with_stop(&gate, fake_stop_local, &probe) == 0);
    CHECK(probe.calls == 0u);
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
    ++s.host_player_id; /* a verified host transition must release RP state */
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    CHECK(rp_v13_session_gate_release_with_stop(&gate, NULL, &probe) == 0);
    CHECK(probe.calls == 0u);
    CHECK(rp_v13_session_gate_release_with_stop(&gate, fake_stop_local, &probe) == 0);
    CHECK(probe.calls == 1u);
    CHECK(!rp_v13_session_gate_is_ready(&gate));
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    probe.result = -1; /* even an unusual nonzero error is not success */
    CHECK(rp_v13_session_gate_release_with_stop(&gate, fake_stop_local, &probe) == 0);
    CHECK(probe.calls == 2u);
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    probe.result = 1;
    CHECK(rp_v13_session_gate_release_with_stop(&gate, fake_stop_local, &probe) == 1);
    CHECK(probe.calls == 3u);
    CHECK(!rp_v13_session_gate_is_ready(&gate));
    CHECK(rp_v13_session_gate_release_with_stop(&gate, fake_stop_local, &probe) == 0);
    CHECK(probe.calls == 3u); /* stop is not repeated after acknowledgement */
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_READY);
    CHECK(rp_v13_session_gate_is_ready(&gate));

    /* Authenticated carrier loss also requires successful local release. */
    s.carrier_authenticated = 0u;
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_RELEASE_REQUIRED);
    CHECK(rp_v13_session_gate_release_with_stop(&gate, fake_stop_local, &probe) == 1);
    CHECK(probe.calls == 4u);
    CHECK(rp_v13_session_gate_update(&gate, &binary, &s) == RP_V13_SESSION_BLOCKED);
    CHECK(!rp_v13_session_gate_is_ready(&gate));
}

int main(void) {
    expect_blocked_on_bad_evidence();
    expect_release_and_rearm();
    expect_every_identity_transition();
    expect_release_requires_successful_stop();
    printf("RP v13 session gate PASS: %u assertions, host-only; no device test\n", checks);
    return 0;
}
