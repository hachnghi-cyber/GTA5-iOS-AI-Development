#include "prp_event_isolation.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
    PRP_GameBridge b;
    prp_bridge_init(&b,NULL);
    PRP_Msg m={0};m.op=PRP_OP_CONSENT;m.session_id=17;
    m.sender_id=9;m.seq=1;m.consent=1;
    uint8_t wire[PRP_WIRE_SIZE],carrier[PRP_CANDIDATE_CARRIER_SIZE];
    assert(prp_encode(wire,&m));
    assert(prp_carrier_pack(carrier,wire));
    PRP_EventRoute route={.on_separate_police_route=0,
       .authenticated_by_engine=1,.trusted_session_id=17,.trusted_sender_id=9};
    /* No hijacking or interpreting stock RAGE / MPJ2 events. */
    assert(prp_isolate_inbound(&b,carrier,sizeof(carrier),&route)==PRP_PASS_TO_ORIGINAL_GAME);
    uint8_t stock[244]={0}; memcpy(stock,"MPJ2",4);
    assert(prp_isolate_inbound(&b,stock,sizeof(stock),&route)==PRP_PASS_TO_ORIGINAL_GAME);
    route.on_separate_police_route=1;
    assert(prp_isolate_inbound(&b,stock,sizeof(stock),&route)==PRP_PRIVATE_REJECTED);
    route.authenticated_by_engine=0;
    assert(prp_isolate_inbound(&b,carrier,sizeof(carrier),&route)==PRP_PRIVATE_REJECTED);
    route.authenticated_by_engine=1;
    route.trusted_sender_id=10;
    assert(prp_isolate_inbound(&b,carrier,sizeof(carrier),&route)==PRP_PRIVATE_REJECTED);
    route.trusted_sender_id=9;
    assert(prp_isolate_inbound(&b,carrier,sizeof(carrier),&route)==PRP_PRIVATE_ACCEPTED);
    PRP_Inbound q;
    assert(prp_inbox_pop(&b.inbox,&q));
    assert(q.trusted_sender_id==9&&q.trusted_session_id==17&&q.authenticated_delivery);
    assert(memcmp(q.packet,wire,sizeof(wire))==0);
    puts("Police RP isolated event routing: 7 security/isolation checks passed (simulation only)");
    return 0;
}
