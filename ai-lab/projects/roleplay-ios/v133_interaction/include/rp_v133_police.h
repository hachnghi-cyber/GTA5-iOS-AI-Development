#ifndef RP_V133_POLICE_H
#define RP_V133_POLICE_H

#include "rp_v133_interact_gate.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RP_V133_POLICE_CAPACITY RP_V133_MAX_TRACKED_PEERS
#define RP_V133_POLICE_JAIL_MS UINT64_C(60000)
#define RP_V133_POLICE_MAX_OBSERVATION_AGE_MS UINT64_C(250)

typedef enum {
    RP_POLICE_CITIZEN = 1,
    RP_POLICE_OFFICER
} rp_police_role;

typedef enum {
    RP_POLICE_FREE = 0,
    RP_POLICE_CUFFED,
    RP_POLICE_ESCORTED,
    RP_POLICE_SEATED,
    RP_POLICE_JAILED
} rp_police_custody;

typedef enum {
    RP_POLICE_OPT_IN = 1,
    RP_POLICE_OPT_OUT,
    RP_POLICE_DUTY_START,
    RP_POLICE_DUTY_END,
    RP_POLICE_CUFF,
    RP_POLICE_UNCUFF,
    RP_POLICE_ESCORT_START,
    RP_POLICE_ESCORT_END,
    RP_POLICE_ENTER_SEAT,
    RP_POLICE_EXIT_SEAT,
    RP_POLICE_JAIL,
    RP_POLICE_RELEASE_JAIL
} rp_police_operation;

typedef struct {
    uint64_t session;
    uint64_t epoch;
    uint64_t target;
    uint64_t nonce;
    rp_police_operation operation;
} rp_police_command;

/* Snapshot produced by the authority for this exact request. Never build it
 * from the decoded wire command or a client's self-reported coordinates.
 */
typedef struct {
    uint64_t actor;
    uint64_t target;
    uint64_t session;
    uint64_t epoch;
    uint64_t observed_at_ms; /* Same authority clock as rp_police_tick. */
    uint64_t vehicle_id;
    uint32_t distance_cm;
    uint8_t seat;
    bool same_game_instance;
    bool native_duty_eligible;
    bool police_vehicle;
    bool seat_available;
    bool both_at_jail_intake;
} rp_police_observation;

typedef struct {
    uint64_t id;
    uint64_t last_nonce;
    uint64_t last_target;
    uint64_t custodian;
    uint64_t vehicle_id;
    uint64_t jail_until_ms;
    rp_police_operation last_operation;
    rp_police_role role;
    rp_police_custody custody;
    uint8_t seat; /* Only meaningful in RP_POLICE_SEATED. */
    bool last_applied;
    bool present;
    bool consent;
    bool on_duty;
} rp_police_member;

/* One authority worker owns this state. No callbacks, network or game natives.
 * Members and their replay entries are retained until session generation ends.
 */
typedef struct {
    uint64_t session;
    uint64_t epoch;
    uint64_t now_ms;
    rp_police_member members[RP_V133_POLICE_CAPACITY];
} rp_police_world;

bool rp_police_init(rp_police_world *world, uint64_t session, uint64_t epoch);
/* Authority-only registrations. Rejoining retains role and last nonce. */
bool rp_police_admit(rp_police_world *world, uint64_t id, rp_police_role role);
bool rp_police_leave(rp_police_world *world, uint64_t id);
/* A verified game admission ended. Release all its effects and invalidate
 * affected ACKs, retaining the RP connection, role and nonce history. */
bool rp_police_reset_game_member(rp_police_world *world, uint64_t id);
/* Call when trusted engine job eligibility ends, e.g. quitting the stock job. */
bool rp_police_revoke_duty(rp_police_world *world, uint64_t id);
bool rp_police_tick(rp_police_world *world, uint64_t now_ms);
bool rp_police_get(const rp_police_world *world, uint64_t id, rp_police_member *member);
/* Returns true only for an applied transition. Valid authenticated envelopes
 * consume a nonce even on a policy denial. Retry needs a fresh nonce.
 */
bool rp_police_apply(rp_police_world *world, const rp_v133_delivery *delivery,
                     const rp_police_command *command,
                     const rp_police_observation *observation);

#ifdef __cplusplus
}
#endif
#endif
