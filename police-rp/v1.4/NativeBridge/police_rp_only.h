#ifndef GTA_IOS_POLICE_RP_ONLY_H
#define GTA_IOS_POLICE_RP_ONLY_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Isolated policy core; no ScriptHook, Menyoo, SHVDN or game-header dependency.
// The existing native GTA work loop must explicitly call pr_tick on game thread.
typedef enum {
    PR_FREE=0, PR_CUFFED=1, PR_ESCORTED=2, PR_JAILED=3
} PR_Status;
typedef struct {
    uint32_t abi_version;           // PR_ABI_VERSION = 1
    uint8_t online;                 // RAGE native network session confirmed
    uint8_t player_opted_in;        // explicit opt-in to Police RP
    int32_t native_job;             // native work job index from GTA5 v12
    uint8_t on_shift;               // native work shift flag
    uint8_t session_verified;       // trusted adapter verified real Online session
    uint8_t authoritative_state;    // state is from authenticated Police RP server
    uint32_t status_age_ms;         // ms since authenticated status accepted
    PR_Status local_status;         // status of THIS device's player ONLY
} PR_Frame;
typedef struct {
    uint32_t abi_version;
    void *userdata;
    // Called only on game thread. Must affect the LOCAL ped, never a remote player.
    void (*set_local_cuffed)(void *userdata, int enable);
    void (*set_local_controls_restricted)(void *userdata, int enable);
} PR_Callbacks;
typedef struct {
    uint8_t was_restricted;
    uint8_t was_cuffed;
} PR_Core;
#define PR_ABI_VERSION 1u
#define PR_STATUS_TTL_MS 4000u
void pr_reset(PR_Core *core, const PR_Callbacks *cb);
void pr_tick(PR_Core *core, const PR_Frame *frame, const PR_Callbacks *cb);
// Outgoing police actions are allowed only for an active, opted-in native police shift.
int pr_can_send_police_action(const PR_Frame *frame);
#ifdef __cplusplus
}
#endif
#endif
