/* Host-only test; demonstrates C/Python protocol compatibility, not iPhone networking. */
#include "rbp_wire_c.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
static const uint64_t now_ms=1731868000123ULL;
static const uint8_t key[32]={0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
                              16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31};
static rbp_frame_c frame(uint64_t seq) {
    rbp_frame_c f={0}; f.kind=RBP_KIND_ACTION; f.action=1;
    f.sequence=seq; f.timestamp_ms=now_ms;
    for(int i=0;i<16;i++) {f.sender[i]=(uint8_t)i;f.target[i]=(uint8_t)(i+32);f.session[i]=(uint8_t)(i+64);}
    for(int i=0;i<8;i++) f.nonce[i]=(uint8_t)(i+80);
    return f;
}
static void receiver_setup(rbp_receiver_c *state) {
    memset(state,0,sizeof(*state));
    rbp_frame_c f=frame(42);
    memcpy(state->key,key,32);memcpy(state->allowed_sender,f.sender,16);
    memcpy(state->self,f.target,16);memcpy(state->session,f.session,16);
    state->max_skew_ms=15000;
}
static void golden(const uint8_t p[96]) {
    FILE *fp=fopen("tests/rbp1_golden.hex","r");assert(fp);
    char hex[193]={0};assert(fread(hex,1,192,fp)==192);fclose(fp);
    const char *digits="0123456789abcdef";
    for(unsigned i=0;i<96;i++) {
        assert(hex[i*2]==digits[p[i]>>4]);assert(hex[i*2+1]==digits[p[i]&15]);
    }
}
int main(void) {
    uint8_t pkt[96],ack[96];rbp_frame_c f=frame(42), parsed={0};
    assert(rbp_wire_encode(&f,key,pkt));golden(pkt);
    assert(rbp_wire_decode(pkt,sizeof(pkt),key,&parsed));
    assert(parsed.sequence==42 && parsed.timestamp_ms==now_ms && parsed.kind==1);
    assert(memcmp(parsed.nonce,f.nonce,8)==0);
    for(int i=0;i<96;i++) {
      uint8_t broken[96];memcpy(broken,pkt,96);broken[i]^=0x80;
      assert(!rbp_wire_decode(broken,96,key,&parsed));
    }
    assert(!rbp_wire_decode(pkt,95,key,&parsed));
    assert(!rbp_wire_decode(pkt,97,key,&parsed));
    rbp_receiver_c s;receiver_setup(&s);rbp_handoff q;rbp_handoff_init(&q);
    /* E2/E3 correctness guard: queue backpressure is not delivery success. */
    assert(rbp_receiver_handle(&s,&q,pkt,96,now_ms,ack)==RBP_RX_ACCEPTED);
    assert(s.committed_sequence==42);
    rbp_frame_c ack_parsed={0};assert(rbp_wire_decode(ack,96,key,&ack_parsed));
    assert(ack_parsed.kind==RBP_KIND_ACK && ack_parsed.action==0);
    assert(ack_parsed.sequence==42);
    assert(memcmp(ack_parsed.target,f.sender,16)==0);
    assert(memcmp(ack_parsed.nonce,f.nonce,8)==0);
    assert(rbp_response_matches_request(&ack_parsed,&f,RBP_KIND_ACK,now_ms));
    rbp_frame_c wrong_response=ack_parsed;
    wrong_response.nonce[0]^=1;
    assert(!rbp_response_matches_request(&wrong_response,&f,RBP_KIND_ACK,now_ms));
    wrong_response=ack_parsed;wrong_response.session[0]^=1;
    assert(!rbp_response_matches_request(&wrong_response,&f,RBP_KIND_ACK,now_ms));
    wrong_response=ack_parsed;wrong_response.sender[0]^=1;
    assert(!rbp_response_matches_request(&wrong_response,&f,RBP_KIND_ACK,now_ms));
    wrong_response=ack_parsed;wrong_response.target[0]^=1;
    assert(!rbp_response_matches_request(&wrong_response,&f,RBP_KIND_ACK,now_ms));
    wrong_response=ack_parsed;wrong_response.sequence++;
    assert(!rbp_response_matches_request(&wrong_response,&f,RBP_KIND_ACK,now_ms));
    assert(!rbp_response_matches_request(&ack_parsed,&f,RBP_KIND_NATIVE_INVOKED,now_ms));
    assert(!rbp_response_matches_request(&ack_parsed,&f,RBP_KIND_ACK,now_ms+15001));
    assert(rbp_receiver_handle(&s,&q,pkt,96,now_ms,ack)==RBP_RX_DUPLICATE);
    rbp_frame_c next=frame(43);
    next.nonce[7]^=10;
    uint8_t next_pkt[96];assert(rbp_wire_encode(&next,key,next_pkt));
    uint8_t sentinel[96];memset(sentinel,0x55,96);
    assert(rbp_receiver_handle(&s,&q,next_pkt,96,now_ms,sentinel)==RBP_RX_BUSY);
    for(int i=0;i<96;i++)assert(sentinel[i]==0x55); /* no ACK available */
    assert(s.committed_sequence==42); /* IMPORTANT: not consumed */
    rbp_diag_event e={0};assert(rbp_handoff_pop_on_game_thread(&q,&e)==1);
    assert(e.sequence==42 && memcmp(e.nonce,f.nonce,8)==0);
    rbp_frame_c executed=ack_parsed;executed.kind=RBP_KIND_NATIVE_INVOKED;
    uint8_t execution_packet[96];
    assert(rbp_wire_encode(&executed,key,execution_packet));
    assert(rbp_wire_decode(execution_packet,96,key,&parsed));
    assert(parsed.kind==RBP_KIND_NATIVE_INVOKED && parsed.sequence==42);
    assert(rbp_response_matches_request(&parsed,&f,RBP_KIND_NATIVE_INVOKED,now_ms));
    assert(!rbp_response_matches_request(&parsed,&f,RBP_KIND_ACK,now_ms));
    executed.action=RBP_DIAG_PING;
    assert(!rbp_wire_encode(&executed,key,execution_packet));
    assert(rbp_receiver_handle(&s,&q,next_pkt,96,now_ms,ack)==RBP_RX_ACCEPTED);
    assert(s.committed_sequence==43);
    assert(rbp_handoff_pop_on_game_thread(&q,&e)==1 && e.sequence==43);
    assert(rbp_receiver_handle(&s,&q,pkt,96,now_ms,ack)==RBP_RX_BAD);
    rbp_frame_c wrong=frame(44);
    wrong.target[0]^=1;uint8_t badpkt[96];assert(rbp_wire_encode(&wrong,key,badpkt));
    assert(rbp_receiver_handle(&s,&q,badpkt,96,now_ms,ack)==RBP_RX_BAD);
    wrong=frame(44);wrong.session[0]^=1;assert(rbp_wire_encode(&wrong,key,badpkt));
    assert(rbp_receiver_handle(&s,&q,badpkt,96,now_ms,ack)==RBP_RX_BAD);
    wrong=frame(44);wrong.sender[0]^=1;assert(rbp_wire_encode(&wrong,key,badpkt));
    assert(rbp_receiver_handle(&s,&q,badpkt,96,now_ms,ack)==RBP_RX_BAD);
    wrong=frame(44);assert(rbp_wire_encode(&wrong,key,badpkt));
    assert(rbp_receiver_handle(&s,&q,badpkt,96,now_ms+16000,ack)==RBP_RX_BAD);
    assert(rbp_receiver_handle(&s,&q,badpkt,96,now_ms-16000,ack)==RBP_RX_BAD);
    assert(rbp_receiver_handle(&s,&q,badpkt,96,now_ms+14999,ack)==RBP_RX_ACCEPTED);
    assert(rbp_handoff_pop_on_game_thread(&q,&e)==1 && e.sequence==44);
    /* Parser adversarial smoke: random, length-truncated, malformed input. */
    srand(42);
    for(unsigned i=0;i<10000;i++){
      uint8_t x[100];for(size_t j=0;j<sizeof(x);j++)x[j]=(uint8_t)rand();
      rbp_frame_c garbage={0};assert(!rbp_wire_decode(x,i%101,key,&garbage));
    }
    puts("PASS RBP1 C codec: Python golden vector; authenticated RX/ACK; backpressure retry; replay/session/peer/clock rejection; 10000 fuzz frames");
    return 0;
}
