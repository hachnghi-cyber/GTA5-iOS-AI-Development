#ifndef RP_V133_RAGE_PROVENANCE_H
#define RP_V133_RAGE_PROVENANCE_H
/*
 * Exact GTA v13.3: READ-ONLY connection/session correlation.
 * NO engine call, memory hook, packet parser, native action or RP authority.
 * Inputs MUST come from independently observed game callbacks; a wire packet
 * must never populate this struct. Consistency is NOT authentication.
 */
#include <stdbool.h>
#include <stdint.h>
#define RP_RAGE_OBSERVER_MAX_PEERS 32u
#define RP_RAGE_OBSERVER_MAX_AGE_MS UINT64_C(250)
typedef enum {
    RP_RAGE_ORIGIN_UNKNOWN=0,
    RP_RAGE_ORIGIN_LOCAL_SEND_BUFFER=1,
    RP_RAGE_ORIGIN_REMOTE_ON_NET_EVENT=2
} rp_rage_origin;
typedef struct {
    uint64_t session_id;           /* rlSession::GetId, not state enum */
    uint64_t generation;           /* locally minted by scope_begin */
    uint64_t peer_id;              /* snSession peer identifier */
    uint64_t observed_at_ms;       /* monotonic time, same owner clock */
    uint32_t event_connection_id; /* netEvent+0x3c on remote path */
    uint32_t netplayer_connection_id; /* netPlayer+0x18 on remote path */
    int32_t session_connection_id; /* snSession::GetPeerCxn, -1 invalid */
    int32_t session_endpoint_id;   /* GetPeerEndpointId, -1 invalid */
    uint8_t netplayer_slot;        /* diagnostic only, NEVER identity */
    bool netplayer_valid;          /* diagnostic only, NOT authentication */
    bool session_member;          /* verified membership lookup, not packet bit */
    bool local_player;
    rp_rage_origin origin;
} rp_rage_sample;
typedef struct {
    uint64_t peer_id;
    uint64_t last_seen_ms;
    uint32_t connection_id;
    int32_t endpoint_id;
    uint8_t slot;
    uint32_t observations; /* count, NOT a confidence score */
} rp_rage_candidate;
typedef struct {
    uint64_t session_id;
    uint64_t generation;
    uint64_t last_now_ms;
    rp_rage_candidate candidates[RP_RAGE_OBSERVER_MAX_PEERS];
    uint32_t candidate_count;
    bool active;
    bool quarantined;
} rp_rage_observer;
typedef enum {
    RP_RAGE_REJECTED=0,
    RP_RAGE_CANDIDATE_ONLY=1,
    RP_RAGE_QUARANTINED=2
} rp_rage_observation_status;
void rp_rage_observer_init(rp_rage_observer *observer);
/* Session-owner callback ONLY, NEVER from network payload. Bump generation
 * on EVERY join or migration, including reuse of identical session ID. */
bool rp_rage_scope_begin(rp_rage_observer *observer, uint64_t session_id);
/* Session-owner disconnect/migration signal. Never retain netPlayer pointers. */
void rp_rage_scope_invalidate(rp_rage_observer *observer);
/* Serialized read-only observer callback, not a privilege grant. */
rp_rage_observation_status rp_rage_observe(rp_rage_observer *observer,
                                        const rp_rage_sample *sample,
                                        uint64_t now_ms);
/* This API deliberately provides NO authenticated flag or police dispatcher. */
#endif
