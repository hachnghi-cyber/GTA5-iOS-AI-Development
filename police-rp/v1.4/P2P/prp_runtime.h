#ifndef GTA_IOS_PRP_RUNTIME_H
#define GTA_IOS_PRP_RUNTIME_H
#include "prp_p2p.h"
#ifdef __cplusplus
extern "C" {
#endif
/* This adapter has NO sockets and NO server dependency. Game's authenticated
   session transport must carry the 56-byte application payload. Network
   callback must NOT be executed on game thread from a background socket. */
typedef int (*PRP_SendAuthenticated)(void *ud, uint64_t receiver_id,
                                    const uint8_t *data,size_t length);
typedef struct {
    PRP_SendAuthenticated send;
    void *ud;
} PRP_SendCallbacks;
typedef struct {
    uint64_t session_id, local_id, host_id;
    uint64_t last_heartbeat_ms;
    uint32_t next_seq;
    uint8_t is_host, local_opt_in;
    PRP_Host host;
    PRP_Client client;
} PRP_Runtime;
void prp_runtime_init(PRP_Runtime *r, uint64_t session_id, uint64_t local_id,
                      uint64_t host_id, uint8_t is_host);
/* Must originate from explicit user consent, NEVER a remote packet.
   enable=0 always clears the local opt-in flag, even when the context is
   missing or the network send fails; release callbacks execute on the next
   game-thread tick. Return 1 indicates host handling or delivery succeeded,
   NOT a guarantee the remote host applied the requested change. */
int prp_runtime_consent(PRP_Runtime *r,uint8_t enable,
                        const PRP_TransportContext *ctx,
                        const PRP_SendCallbacks *send);
/* For local police actions only. Host revalidates using engine-attested peers. */
PRP_Outcome prp_runtime_action(PRP_Runtime *r,uint8_t op,uint64_t target,
                                uint32_t jail_ms,
                                const PRP_TransportContext *ctx,
                                const PRP_SendCallbacks *send);
/* Called by GAME THREAD after verified transport unmarshalling. */
PRP_Outcome prp_runtime_receive(PRP_Runtime *r,const uint8_t *wire,size_t size,
                                 const PRP_TransportContext *ctx,
                                 const PR_EngineView *view);
/* Called every game frame, not ScriptHook tick. */
void prp_runtime_tick(PRP_Runtime *r,uint64_t now,
                      const PR_EngineView *local_view,
                      const PR_Callbacks *local_ped_cb,
                      const PRP_SendCallbacks *send);
/* On Online session leave/host change. Always release local controls. */
void prp_runtime_stop(PRP_Runtime *r,const PR_Callbacks *cb);
#ifdef __cplusplus
}
#endif
#endif
