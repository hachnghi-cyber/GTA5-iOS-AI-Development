#ifndef RP_V133_INTERACT_GATE_H
#define RP_V133_INTERACT_GATE_H
/* Clean-room, source-only GTA V iOS v13.3 interaction gateway.
 * No hooks, game natives, sockets or binary patching are performed here.
 * The integrator must supply trustworthy engine/transport callbacks.
 */
#include <stdbool.h>
#include <stdint.h>

#define RP_V133_GATE_ABI 1u
#define RP_V133_MAX_INTERACT_CM 400u
#define RP_V133_MAX_TRACKED_PEERS 32u
#define RP_V133_TARGET_UUID "EB122C35-96F4-307F-91C3-A2255DD9C685"
#define RP_V133_TARGET_SHA256 "f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc"

typedef enum {
    RP_V133_GREET = 1,
    RP_V133_DOCUMENTS = 2
} rp_v133_interaction_kind;

typedef enum {
    RP_V133_DENIED = 0,
    RP_V133_ATTEMPTED = 1, /* emitted to adapter, NOT delivery confirmation */
    RP_V133_RECEIVED = 2   /* authenticated adapter reported receipt, NOT UI effect */
} rp_v133_result;

typedef struct {
    uint64_t session_id;
    uint64_t local_player_id;
    uint64_t peer_epoch;
    uint64_t local_frame;
    uint8_t online;
    uint8_t opted_in;
} rp_v133_snapshot;

typedef struct {
    uint64_t session_id;
    uint64_t receiver;
    uint64_t nonce;
    uint64_t epoch;
    rp_v133_interaction_kind kind;
} rp_v133_action;

typedef struct {
    uint64_t transport_sender; /* must be from authenticated native transport metadata */
    uint64_t transport_session;
    uint64_t transport_epoch;
    uint8_t authenticated; /* NEVER read this flag from the packet payload */
} rp_v133_delivery;

typedef struct {
    /* These functions MUST be implemented against the exact v13.3 runtime.
     * Returning true from a fake/INI/packet-backed callback voids the security contract. */
    bool (*attest_build)(void *ctx, const char *uuid, const char *sha256);
    bool (*on_game_thread)(void *ctx);
    bool (*read_engine_snapshot)(void *ctx, rp_v133_snapshot *out);
    bool (*target_is_trusted_nearby)(void *ctx, uint64_t player_id,
                                     uint64_t peer_epoch, uint32_t radius_cm);
    bool (*authenticated_channel_ready)(void *ctx);
    /* Must route through authenticated native session transport; never through MPJ2
     * job events, a generic untrusted socket, or a UI-controlled sender identity. */
    bool (*emit_interaction)(void *ctx, const rp_v133_action *event);
    /* Receive notification only, no arrest/health/movement changes. */
    void (*observe_interaction)(void *ctx, uint64_t trusted_sender,
                                rp_v133_interaction_kind kind);
    void *ctx;
} rp_v133_gate_callbacks;

typedef struct {
    rp_v133_gate_callbacks cb;
    uint64_t last_session;
    uint64_t last_peer_epoch;
    uint64_t last_outgoing_nonce;
    struct { uint64_t sender; uint64_t nonce; } incoming[RP_V133_MAX_TRACKED_PEERS];
    uint32_t accepted;
    uint32_t denied;
    uint8_t bound;
    uint8_t busy;
} rp_v133_gate;

void rp_v133_gate_init(rp_v133_gate *gate, const rp_v133_gate_callbacks *cb);
void rp_v133_gate_stop(rp_v133_gate *gate);
/* Valid only on game thread. For a change of epoch/session all prior nonces
 * are revoked. Actual trust still depends on the integrator callbacks. */
bool rp_v133_gate_rebind(rp_v133_gate *gate);
/* Called by native UI bridge for greet/documents ONLY. Actor identity is never
 * accepted from untrusted JavaScript; it comes from read_engine_snapshot(). */
rp_v133_result rp_v133_gate_request(rp_v133_gate *gate, uint64_t target,
                                    rp_v133_interaction_kind kind, uint64_t nonce);
/* Called ONLY from game-thread authenticated native transport dispatch.
 * delivery metadata and action must originate from distinct trust boundaries. */
rp_v133_result rp_v133_gate_deliver(rp_v133_gate *gate,
                                    const rp_v133_delivery *delivery,
                                    const rp_v133_action *action);
#endif
