#include "prp_event_isolation.h"
/* This is not an engine hook. A future caller must supply the actual verified
 * event type / route; never infer it from the magic in the packet itself. */
PRP_EventDecision prp_isolate_inbound(PRP_GameBridge *b,
    const uint8_t *data,size_t n,const PRP_EventRoute *route){
    if(!route||!route->on_separate_police_route)
        return PRP_PASS_TO_ORIGINAL_GAME;
    if(!route->authenticated_by_engine||!route->trusted_sender_id||
       !route->trusted_session_id||!b||!data)
        return PRP_PRIVATE_REJECTED;
    PRP_TrustedDelivery trusted={
        .trusted_session_id=route->trusted_session_id,
        .trusted_sender_id=route->trusted_sender_id,
        .authenticated=route->authenticated_by_engine
    };
    return prp_carrier_enqueue(b,data,n,&trusted)
       ? PRP_PRIVATE_ACCEPTED:PRP_PRIVATE_REJECTED;
}
