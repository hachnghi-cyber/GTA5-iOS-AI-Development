#ifndef GTA_IOS_POLICE_RP_ADAPTER_H
#define GTA_IOS_POLICE_RP_ADAPTER_H
#include <stdint.h>
#include "police_rp_only.h"
#ifdef __cplusplus
extern "C" {
#endif
/* No engine headers or ScriptHook dependencies. All API calls MUST execute on
   the GTA game thread. The network worker must marshal reports to that thread.
   IDs MUST come from the real GTA Online session / local player, not user INI. */
#define PR_ADAPTER_ABI 2u

typedef struct {
    uint32_t abi_version;
    uint64_t monotonic_ms;         /* monotonic clock, not wall time */
    uint64_t verified_session_id;  /* 0 means no trusted session */
    uint64_t local_player_id;      /* 0 means no trusted local player */
    uint8_t online;
    uint8_t session_verified;
    uint8_t local_opt_in;
    int32_t native_job;           /* GTA v12 native work index, 0..2 police */
    uint8_t on_shift;
} PR_EngineView;

typedef struct {
    uint32_t abi_version;
    uint64_t session_id;
    uint64_t local_player_id;
    PR_Status status;
    uint8_t authenticated;        /* authenticated by transport adapter; NOT set from HTTP JSON */
} PR_AuthenticatedStatus;

typedef enum {
    PR_DROP_NONE=0,
    PR_DROP_NO_SESSION,
    PR_DROP_NO_OPT_IN,
    PR_DROP_STALE,
    PR_DROP_NO_AUTH_STATUS,
    PR_DROP_CONTEXT_CHANGED
} PR_DropReason;

typedef struct {
    PR_Core core;
    PR_AuthenticatedStatus last;
    uint64_t last_received_ms;
    uint64_t bound_session;
    uint64_t bound_player;
    uint8_t has_status;
    PR_DropReason reason;
} PR_Adapter;

void pr_adapter_init(PR_Adapter *a);
/* On GAME THREAD after transport verified sender, recipient, current session. */
int pr_adapter_accept(PR_Adapter *a, const PR_EngineView *local,
                      const PR_AuthenticatedStatus *remote);
/* On GAME THREAD EVERY frame; calls only local-ped callbacks. */
void pr_adapter_tick(PR_Adapter *a, const PR_EngineView *local,
                     const PR_Callbacks *local_ped_callbacks);
void pr_adapter_stop(PR_Adapter *a, const PR_Callbacks *local_ped_callbacks);
/* Useful to gate outgoing client police actions; server must recheck role/distance. */
int pr_adapter_can_arrest(const PR_Adapter *a, const PR_EngineView *local);
#ifdef __cplusplus
}
#endif
#endif
