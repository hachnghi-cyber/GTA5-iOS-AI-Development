#include "prp_candidate_carrier.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned passed;
#define CHECK(x) do{assert((x));++passed;}while(0)
int main(void){
    PRP_Msg msg={.op=PRP_OP_CUFF,.session_id=11001,
         .sender_id=51,.target_id=52,.seq=1,.issued_ms=1000,.consent=1};
    uint8_t wire[PRP_WIRE_SIZE],out[PRP_WIRE_SIZE];
    uint8_t carrier[PRP_CANDIDATE_CARRIER_SIZE];
    PRP_TrustedDelivery t={.trusted_session_id=11001,.trusted_sender_id=51,
                           .authenticated=1};
    CHECK(prp_encode(wire,&msg));
    CHECK(prp_carrier_pack(carrier,wire));
    CHECK(prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    CHECK(memcmp(out,wire,sizeof(wire))==0);
    CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier)-1,&t));
    t.authenticated=0;CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    t.authenticated=1;t.trusted_sender_id=99;
    CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    t.trusted_sender_id=51;t.trusted_session_id=11002;
    CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    t.trusted_session_id=11001;
    carrier[10]^=1;CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    carrier[10]^=1;
    carrier[240]=1;CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    carrier[240]=0;
    carrier[0]='M';CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    carrier[0]='P';
    carrier[7]=1;CHECK(!prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    carrier[7]=0;
    CHECK(prp_carrier_unpack(out,carrier,sizeof(carrier),&t));
    /* The inbound packet queues only; no game callbacks are invoked. */
    PRP_GameBridge bridge;
    prp_bridge_init(&bridge,NULL);
    CHECK(prp_carrier_enqueue(&bridge,carrier,sizeof(carrier),&t));
    PRP_Inbound incoming;
    CHECK(prp_inbox_pop(&bridge.inbox,&incoming));
    CHECK(incoming.trusted_sender_id==51&&incoming.trusted_session_id==11001);
    CHECK(!prp_inbox_pop(&bridge.inbox,&incoming));
    CHECK(!prp_carrier_enqueue(&bridge,carrier,6,&t));
    CHECK(prp_carrier_pack(carrier,wire));
    msg.sender_id=999;
    CHECK(prp_encode(wire,&msg));
    CHECK(prp_carrier_pack(carrier,wire));
    CHECK(!prp_carrier_enqueue(&bridge,carrier,sizeof(carrier),&t));
    puts("PRP v1.0 candidate carrier: all checks passed; no RAGE event sent");
    printf("Assertions: %u\n",passed);
    return 0;
}
