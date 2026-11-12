#ifndef GTA_V_IOS_PRP_ENGINE_BINDING_H
#define GTA_V_IOS_PRP_ENGINE_BINDING_H
#include "../P2P/prp_runtime.h"
#include "prp_mailbox.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Called ONLY from GTA5's game thread. The engine integrator MUST supply
 * authoritative values from the exact v12 GTA5 runtime, never inferred
 * from a player label, config, raw UDP, or remote client packet. */
#define PRP_BRIDGE_ABI 1u
typedef struct {
    uint32_t abi;
    PR_EngineView local;
    uint64_t host_player_id;
    uint8_t local_is_host;
    uint8_t channel_authenticated;
    uint8_t peer_count;
    PRP_Peer trusted_peers[PRP_MAX_PEERS];
} PRP_GameSnapshot;
typedef int (*PRP_ReadEngineSnapshot)(void *ctx, PRP_GameSnapshot *out);
typedef struct {
    PRP_ReadEngineSnapshot read_snapshot;
    PRP_SendAuthenticated send_authenticated;
    PR_Callbacks local_ped;
    void *userdata;
} PRP_EngineCallbacks;
typedef struct {
    PRP_Runtime runtime;
    PRP_Inbox inbox;
    PRP_GameSnapshot last;
    PRP_EngineCallbacks callbacks;
    uint8_t active;
    uint8_t want_opt_in;
    uint8_t have_snapshot;
} PRP_GameBridge;

void prp_bridge_init(PRP_GameBridge *b, const PRP_EngineCallbacks *cb);
/* No engine pointer access in this function; only sets local preference.
 * Call on game thread, never set from incoming packet. */
void prp_bridge_set_consent(PRP_GameBridge *b, int enable);
/* Must be called once PER GAME FRAME by the verified GTA engine callback.
 * Returns 1 only when the session snapshot was verified and accepted. */
int prp_bridge_frame(PRP_GameBridge *b);
/* Delivery must come from the authenticated GTA transport on game thread.
 * trusted_sender must come from transport metadata, not wire payload. */
PRP_Outcome prp_bridge_receive(PRP_GameBridge *b, uint64_t trusted_sender,
                               uint8_t authenticated_delivery,
                               const uint8_t *data, size_t length);
PRP_Outcome prp_bridge_arrest(PRP_GameBridge *b, uint8_t op,
                              uint64_t target, uint32_t jail_ms);
/* Thread-safe producer API. Call from engine's AUTHENTICATED transport callback.
 * All game state changes and decoding happen later on the game thread. */
int prp_bridge_enqueue(PRP_GameBridge *b,uint64_t trusted_session,
                       uint64_t trusted_sender,uint8_t authenticated,
                       const uint8_t *wire,size_t n);
void prp_bridge_stop(PRP_GameBridge *b);
#ifdef __cplusplus
}
#endif
#endif
