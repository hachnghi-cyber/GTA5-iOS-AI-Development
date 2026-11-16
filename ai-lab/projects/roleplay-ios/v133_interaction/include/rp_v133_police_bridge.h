#ifndef RP_V133_POLICE_BRIDGE_H
#define RP_V133_POLICE_BRIDGE_H

#include "rp_v133_police_tx.h"

#ifdef __cplusplus
extern "C" {
#endif

/* A game identifier must not be a slot or a raw pointer. The trusted adapter
 * supplies a fresh, monotonically increasing admission incarnation within
 * this game generation. The same token must tag subsequent live snapshots.
 */
typedef struct {
    uint64_t id;
    uint64_t incarnation;
} rp_game_peer;

typedef struct {
    uint64_t session;
    uint64_t generation;
} rp_game_scope;

/* Construct on the verified authority callback. RP messages cannot construct
 * or provide these facts. The bridge copies no engine pointer.
 */
typedef struct {
    rp_game_scope scope;
    rp_game_peer actor;
    rp_game_peer target;
    uint64_t observed_at_ms;
    uint64_t vehicle_id;
    uint32_t distance_cm;
    uint8_t seat;
    bool same_game_instance;
    bool native_duty_eligible;
    bool police_vehicle;
    bool seat_available;
    bool both_at_jail_intake;
} rp_game_observation;

typedef struct {
    uint64_t rp_id;
    rp_game_peer game;
    bool active;
} rp_police_binding;

typedef struct {
    rp_police_world world;
    rp_game_scope game;
    uint64_t highest_incarnation;
    rp_police_binding bindings[RP_V133_POLICE_CAPACITY];
} rp_police_bridge;

/* Serialized authority owner only. Initialize once. Rotate on session
 * migration. This module implements no trust discovery or GTA calls. */
bool rp_police_bridge_init(rp_police_bridge *bridge, uint64_t session, uint64_t epoch,
                           rp_game_scope game);
bool rp_police_bridge_rotate(rp_police_bridge *bridge, uint64_t session, uint64_t epoch,
                             rp_game_scope game);
/* Called only after independently verifying the paired RP endpoint and the
 * consenting game participant are the same player. It neither infers that
 * association nor grants command-level opt-in. Never call from parsed wire.
 */
bool rp_police_bridge_bind(rp_police_bridge *bridge, const rp_v133_delivery *verified,
                           rp_game_scope game, rp_game_peer peer, rp_police_role role);
/* Qualified by the same game session/generation and exact incarnation.
 * Releases authority-side custody and preserves nonce history. */
bool rp_police_bridge_leave(rp_police_bridge *bridge, uint64_t rp_id,
                            rp_game_scope game, rp_game_peer peer);
bool rp_police_bridge_dispatch(rp_police_bridge *bridge, const rp_v133_delivery *delivery,
                               const rp_game_observation *game, uint64_t now_ms,
                               const uint8_t *wire, size_t wire_size,
                               uint8_t *ack, size_t ack_size);

#ifdef __cplusplus
}
#endif
#endif
