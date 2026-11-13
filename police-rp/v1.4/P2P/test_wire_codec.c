/* RP-002 valid-wire coverage: deterministic roundtrips and corrupt fields.
   Host-only. No GTA transport, sockets, credentials or iOS dependencies. */
#include "prp_p2p.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t seed=0x79AC0D53u;
static uint32_t random32(void) {
    seed^=seed<<13;
    seed^=seed>>17;
    seed^=seed<<5;
    return seed;
}
static uint64_t random64(void) {
    return ((uint64_t)random32()<<32)|random32();
}
static unsigned long long checks;
#define CHECK(x) do { assert(x); checks++; } while (0)

static void compare(const PRP_Msg *a,const PRP_Msg *b) {
    CHECK(a->op==b->op);
    CHECK(a->session_id==b->session_id);
    CHECK(a->sender_id==b->sender_id);
    CHECK(a->target_id==b->target_id);
    CHECK(a->seq==b->seq);
    CHECK(a->generation==b->generation);
    CHECK(a->issued_ms==b->issued_ms);
    CHECK(a->jail_ms==b->jail_ms);
    CHECK(a->status==b->status);
    CHECK(a->consent==b->consent);
}
int main(void) {
    for (int i=0;i<10000;i++) {
        PRP_Msg src={0},dst={0};
        src.op=(uint8_t)(PRP_OP_CONSENT+random32()%7u);
        src.session_id=random64()|1u;
        src.sender_id=random64()|1u;
        src.target_id=random64();
        src.seq=random32()|1u;
        src.generation=random32();
        src.issued_ms=random64();
        src.jail_ms=random32()%(PRP_MAX_JAIL_MS+1u);
        src.status=(uint8_t)(random32()%4u);
        src.consent=(uint8_t)(random32()%2u);
        uint8_t wire[PRP_WIRE_SIZE];
        CHECK(prp_encode(wire,&src));
        CHECK(memcmp(wire,"PRP6",4)==0);
        CHECK(wire[4]==PRP_VERSION);
        CHECK(wire[5]==src.op);
        CHECK(wire[6]==0&&wire[7]==0&&wire[54]==0&&wire[55]==0);
        CHECK(prp_decode(&dst,wire,sizeof(wire)));
        compare(&src,&dst);
    }

    PRP_Msg m={0};
    m.op=PRP_OP_CONSENT;m.session_id=123;m.sender_id=4;
    m.target_id=4;m.seq=7;m.consent=1;
    uint8_t wire[PRP_WIRE_SIZE];
    CHECK(prp_encode(wire,&m));
    PRP_Msg decoded={0};
    CHECK(!prp_decode(&decoded,wire,0));
    CHECK(!prp_decode(&decoded,wire,sizeof(wire)-1));
    CHECK(!prp_decode(&decoded,wire,sizeof(wire)+1));
    CHECK(!prp_encode(NULL,&m));
    CHECK(!prp_encode(wire,NULL));
    CHECK(!prp_decode(NULL,wire,sizeof(wire)));
    CHECK(!prp_decode(&decoded,NULL,sizeof(wire)));
    const unsigned reserved[]={6,7,54,55};
    for (size_t i=0;i<sizeof(reserved)/sizeof(reserved[0]);i++) {
        uint8_t corrupt[PRP_WIRE_SIZE];
        memcpy(corrupt,wire,sizeof(corrupt));
        corrupt[reserved[i]]=1;
        CHECK(!prp_decode(&decoded,corrupt,sizeof(corrupt)));
    }
    uint8_t bad[PRP_WIRE_SIZE];
    memcpy(bad,wire,sizeof(bad));
    bad[4]=PRP_VERSION+1;
    CHECK(!prp_decode(&decoded,bad,sizeof(bad)));
    memcpy(bad,wire,sizeof(bad));bad[52]=0xff;
    CHECK(!prp_decode(&decoded,bad,sizeof(bad)));
    memcpy(bad,wire,sizeof(bad));bad[53]=2;
    CHECK(!prp_decode(&decoded,bad,sizeof(bad)));
    memcpy(bad,wire,sizeof(bad));
    bad[48]=bad[49]=bad[50]=bad[51]=0xff;
    CHECK(!prp_decode(&decoded,bad,sizeof(bad)));
    printf("Police RP deterministic wire codec: %llu checks, 10000 valid frames, negative boundary cases OK\n",checks);
    return 0;
}
