#ifndef PRP_EVENT_ISOLATION_H
#define PRP_EVENT_ISOLATION_H
#include "prp_candidate_carrier.h"
/* A receiver adapter proposed for a FUTURE registered, authenticated RP-only
   event route. The original RAGE event dispatch MUST call this only after its
   own authentication. There is no adapter installed in GTA5 at this stage. */
typedef struct {
    uint8_t on_separate_police_route;
    uint8_t authenticated_by_engine;
    uint64_t trusted_session_id;
    uint64_t trusted_sender_id;
} PRP_EventRoute;
typedef enum {
    PRP_PASS_TO_ORIGINAL_GAME = 0,
    PRP_PRIVATE_ACCEPTED = 1,
    PRP_PRIVATE_REJECTED = 2
} PRP_EventDecision;
PRP_EventDecision prp_isolate_inbound(PRP_GameBridge *b,
                     const uint8_t *data,size_t n,const PRP_EventRoute *route);
#endif
