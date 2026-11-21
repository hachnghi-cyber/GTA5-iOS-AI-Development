#include "rp_v133_wire.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static const uint8_t golden[RP_V133_WIRE_BYTES]={
    0x50,0x52,0x50,0x33,0x01,0x01,0x00,0x00,
    0x08,0x07,0x06,0x05,0x04,0x03,0x02,0x01,
    0x18,0x17,0x16,0x15,0x14,0x13,0x12,0x11,
    0x28,0x27,0x26,0x25,0x24,0x23,0x22,0x21,
    0x38,0x37,0x36,0x35,0x34,0x33,0x32,0x31
};
static void rejects_mutation(unsigned offset, uint8_t val) {
    uint8_t frame[RP_V133_WIRE_BYTES];
    memcpy(frame,golden,sizeof frame);
    frame[offset]=val;
    rp_v133_action out={1,2,3,4,RP_V133_GREET};
    assert(!rp_v133_wire_decode(frame,sizeof frame,&out));
    assert(out.session_id==0 && out.receiver==0 && out.nonce==0);
}
int main(void) {
    rp_v133_action a={
        UINT64_C(0x0102030405060708),
        UINT64_C(0x1112131415161718),
        UINT64_C(0x3132333435363738),
        UINT64_C(0x2122232425262728),RP_V133_GREET
    };
    uint8_t frame[RP_V133_WIRE_BYTES]={0};
    assert(rp_v133_wire_encode(&a,frame,sizeof frame));
    assert(memcmp(frame,golden,sizeof frame)==0);
    rp_v133_action b={0};
    assert(rp_v133_wire_decode(frame,sizeof frame,&b));
    assert(b.session_id==a.session_id && b.receiver==a.receiver &&
           b.epoch==a.epoch && b.nonce==a.nonce && b.kind==a.kind);
    assert(!rp_v133_wire_decode(frame,sizeof frame-1,&b));
    assert(!rp_v133_wire_decode(frame,sizeof frame+1,&b));
    assert(!rp_v133_wire_decode(NULL,sizeof frame,&b));
    assert(!rp_v133_wire_decode(frame,sizeof frame,NULL));
    uint8_t smaller[4]={0xaa,0xaa,0xaa,0xaa};
    assert(!rp_v133_wire_encode(&a,smaller,sizeof smaller));
    assert(smaller[0]==0xaa);
    rejects_mutation(0,0x41);
    rejects_mutation(4,0x02);
    rejects_mutation(5,0x03);
    rejects_mutation(6,0x01);
    rejects_mutation(7,0x01);
    rp_v133_action invalid=a;
    invalid.receiver=0;
    assert(!rp_v133_wire_encode(&invalid,frame,sizeof frame));
    invalid=a;invalid.nonce=0;
    assert(!rp_v133_wire_encode(&invalid,frame,sizeof frame));
    invalid=a;invalid.epoch=0;
    assert(!rp_v133_wire_encode(&invalid,frame,sizeof frame));
    invalid=a;invalid.session_id=0;
    assert(!rp_v133_wire_encode(&invalid,frame,sizeof frame));
    a.kind=RP_V133_DOCUMENTS;
    assert(rp_v133_wire_encode(&a,frame,sizeof frame));
    assert(frame[5]==2);
    assert(rp_v133_wire_decode(frame,sizeof frame,&b));
    assert(b.kind==RP_V133_DOCUMENTS);
    puts("v13.3 RP diagnostic wire: PASS (golden vector, strict parser, invalid input)");
    return 0;
}
