#ifndef GTA_IOS_PRP_P2P_H
#define GTA_IOS_PRP_P2P_H
#include <stddef.h>
#include <stdint.h>
#include "../NativeBridge/police_rp_adapter.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Police RP application message inside an ALREADY authenticated GTA transport.
   This 56-byte format is NOT an encrypted UDP packet and must never be sent
   over unauthenticated sockets. Engine owns identity/session provenance. */
#define PRP_WIRE_SIZE 56u
#define PRP_MAX_PEERS 32u
#define PRP_VERSION 1u
#define PRP_POSITION_TTL_MS 2000u
#define PRP_HEARTBEAT_MS 500u
#define PRP_MAX_JAIL_MS 3600000u
#define PRP_CUFF_RADIUS_M 3.25f
#define PRP_ESCORT_RADIUS_M 6.0f

typedef enum {
    PRP_OP_CONSENT=1, PRP_OP_CUFF=2, PRP_OP_UNCUFF=3,
    PRP_OP_ESCORT=4, PRP_OP_JAIL=5, PRP_OP_RELEASE=6,
    PRP_OP_STATE=7
} PRP_Op;
typedef struct {
    uint8_t op;
    uint64_t session_id, sender_id, target_id;
    uint32_t seq, generation;
    uint64_t issued_ms;
    uint32_t jail_ms;
    uint8_t status, consent;
} PRP_Msg;
int prp_encode(uint8_t out[PRP_WIRE_SIZE], const PRP_Msg *m);
int prp_decode(PRP_Msg *m, const uint8_t *in, size_t size);

/* All fields populated from verified GTA session/peer state by integration
   adapter; never accept this struct from a remote packet or a text config. */
typedef struct {
    uint64_t session_id;
    uint64_t local_player_id;
    uint64_t host_player_id;
    uint64_t trusted_sender_id;     /* transport authenticated this sender */
    uint64_t monotonic_ms;
    uint8_t session_verified;
    uint8_t channel_authenticated;  /* encrypted/authenticated RAGE channel */
} PRP_TransportContext;
typedef struct {
    uint64_t player_id;
    uint8_t connected, opt_in;
    uint8_t job_verified, position_verified;
    int32_t native_job;
    uint8_t on_shift;
    float x, y, z;
    uint8_t station_verified; /* only engine's jail drop-off zone validator */
    uint64_t last_position_ms;
} PRP_Peer;
typedef struct {
    PR_Status status;
    uint64_t officer_id;
    uint64_t release_at_ms;
    uint32_t generation;
} PRP_TargetState;
typedef struct {
    uint64_t session_id, host_id;
    PRP_Peer peers[PRP_MAX_PEERS];
    PRP_TargetState states[PRP_MAX_PEERS];
    uint32_t last_client_seq[PRP_MAX_PEERS];
    uint32_t send_seq;
    uint8_t peer_count;
} PRP_Host;
typedef enum {
    PRP_ACCEPTED=0, PRP_SENT_PENDING=1, PRP_ERR_PACKET=-1, PRP_ERR_AUTH=-2,
    PRP_ERR_SESSION=-3, PRP_ERR_PEER=-4, PRP_ERR_REPLAY=-5,
    PRP_ERR_CONSENT=-6, PRP_ERR_POLICE=-7, PRP_ERR_DISTANCE=-8,
    PRP_ERR_STATE=-9, PRP_ERR_ZONE=-10
} PRP_Outcome;
typedef struct {
    PRP_Outcome outcome;
    uint64_t target_id;
    PRP_TargetState target_state;
} PRP_HostResult;

void prp_host_init(PRP_Host *h, uint64_t session_id, uint64_t host_id);
/* Snapshot MUST be attested by GTA networking; opt_in managed by consent packets.
   Calling it for a disconnected peer clears any existing cuff/escort/jail. */
int prp_host_update_peer(PRP_Host *h, const PRP_Peer *trusted_snapshot);
int prp_host_remove_peer(PRP_Host *h, uint64_t id);
PRP_Outcome prp_host_receive(PRP_Host *h, const PRP_TransportContext *ctx,
                             const PRP_Msg *m, PRP_HostResult *result);
void prp_host_expire(PRP_Host *h, uint64_t monotonic_ms);
/* State heartbeat: every PRP_HEARTBEAT_MS to each opted-in peer. */
int prp_host_state_for(PRP_Host *h, uint64_t target_id,
                       uint64_t now_ms, PRP_Msg *out);

typedef struct {
    uint64_t session_id, local_id, expected_host_id;
    uint32_t last_seq;
    PR_Adapter adapter; /* v0.5 local-ped-only fail-open enforcement */
} PRP_Client;
void prp_client_init(PRP_Client *c, uint64_t session, uint64_t local_id,
                     uint64_t expected_host);
/* Caller must supply authenticated transport identity (never a JSON value). */
int prp_client_receive_state(PRP_Client *c,
                             const PRP_TransportContext *ctx,
                             const PRP_Msg *m, const PR_EngineView *view);
#ifdef __cplusplus
}
#endif
#endif
