#include "rbp_wire_c.h"
#ifdef RBP_FREESTANDING_ARM64
/* Standalone object compilation WITHOUT pretending an iPhoneOS SDK exists.
 * The real iOS dylib build always uses system libc/string.h.
 */
static void *rbp_memcpy(void *dst,const void *src,size_t len){
    uint8_t *d=(uint8_t*)dst;const uint8_t *s=(const uint8_t*)src;
    for(size_t i=0;i<len;i++)d[i]=s[i];return dst;
}
static void *rbp_memset(void *dst,int v,size_t len){
    uint8_t *d=(uint8_t*)dst;for(size_t i=0;i<len;i++)d[i]=(uint8_t)v;
    return dst;
}
static int rbp_memcmp(const void *a,const void *b,size_t len){
    const uint8_t *x=(const uint8_t*)a,*y=(const uint8_t*)b;
    for(size_t i=0;i<len;i++)if(x[i]!=y[i])return (int)x[i]-(int)y[i];
    return 0;
}
#define memcpy rbp_memcpy
#define memset rbp_memset
#define memcmp rbp_memcmp
#else
#include <string.h>
#endif

static void store64(uint8_t *p, uint64_t v) {
    for (int i=7;i>=0;--i) {p[i]=(uint8_t)v;v>>=8;}
}
static uint64_t load64(const uint8_t *p) {
    uint64_t n=0;
    for(int i=0;i<8;++i) n=(n<<8)|p[i];
    return n;
}
static int constant_equal(const uint8_t *x,const uint8_t *y,size_t n) {
    unsigned bad=0;
    for(size_t i=0;i<n;++i) bad|=(unsigned)(x[i]^y[i]);
    return bad==0;
}
int rbp_wire_encode(const rbp_frame_c *f, const uint8_t key[32],
                    uint8_t out[RBP_WIRE_SIZE]) {
    if(!f||!key||!out || f->sequence==0 ||
       !((f->kind==RBP_KIND_ACTION && f->action==RBP_DIAG_PING) ||
         ((f->kind==RBP_KIND_ACK || f->kind==RBP_KIND_NATIVE_INVOKED) && f->action==0))) return 0;
    memcpy(out,"RBP1",4);
    out[4]=1;out[5]=f->kind;out[6]=(uint8_t)(f->action>>8);out[7]=(uint8_t)f->action;
    store64(out+8,f->sequence);store64(out+16,f->timestamp_ms);
    memcpy(out+24,f->sender,16);memcpy(out+40,f->target,16);
    memcpy(out+56,f->session,16);memcpy(out+72,f->nonce,8);
    uint8_t mac[32];
    if(!rbp_hmac_sha256(key,out,RBP_HEADER_SIZE,mac)) {memset(out,0,RBP_WIRE_SIZE);return 0;}
    memcpy(out+RBP_HEADER_SIZE,mac,16);
    memset(mac,0,sizeof mac);
    return 1;
}
int rbp_wire_decode(const uint8_t *p, size_t length,
                    const uint8_t key[32], rbp_frame_c *out) {
    if(!p||!out||!key||length!=RBP_WIRE_SIZE) return 0;
    uint8_t mac[32];
    if(!rbp_hmac_sha256(key,p,RBP_HEADER_SIZE,mac))return 0;
    int good=constant_equal(mac,p+RBP_HEADER_SIZE,16);
    memset(mac,0,sizeof mac);
    if(!good || memcmp(p,"RBP1",4)!=0 || p[4]!=1)return 0;
    uint16_t action=(uint16_t)((unsigned)p[6]<<8 | p[7]);
    if(!((p[5]==RBP_KIND_ACTION && action==RBP_DIAG_PING) ||
         ((p[5]==RBP_KIND_ACK || p[5]==RBP_KIND_NATIVE_INVOKED) && action==0))) return 0;
    rbp_frame_c local={0};
    local.kind=p[5];local.action=action;local.sequence=load64(p+8);
    local.timestamp_ms=load64(p+16);
    if(local.sequence==0)return 0;
    memcpy(local.sender,p+24,16);memcpy(local.target,p+40,16);
    memcpy(local.session,p+56,16);memcpy(local.nonce,p+72,8);
    *out=local;
    return 1;
}
static int near_ms(uint64_t a,uint64_t b,uint32_t skew) {
    return a>=b ? a-b<=skew : b-a<=skew;
}
int rbp_response_matches_request(const rbp_frame_c *response,
          const rbp_frame_c *request, uint8_t kind, uint64_t received_ms) {
    if(!response || !request ||
       !(kind==RBP_KIND_ACK || kind==RBP_KIND_NATIVE_INVOKED) ||
       request->kind!=RBP_KIND_ACTION || request->action!=RBP_DIAG_PING ||
       response->kind!=kind || response->action!=0 ||
       response->sequence!=request->sequence ||
       !constant_equal(response->nonce,request->nonce,8) ||
       !constant_equal(response->sender,request->target,16) ||
       !constant_equal(response->target,request->sender,16) ||
       !constant_equal(response->session,request->session,16) ||
       !near_ms(response->timestamp_ms,received_ms,15000u))return 0;
    return 1;
}
rbp_rx_result rbp_receiver_handle(rbp_receiver_c *s, rbp_handoff *handoff,
     const uint8_t *packet,size_t length,uint64_t now_ms,
     uint8_t ack[RBP_WIRE_SIZE]) {
    if(!s||!handoff||!ack)return RBP_RX_BAD;
    rbp_frame_c f={0};
    if(!rbp_wire_decode(packet,length,s->key,&f) ||
       f.kind!=RBP_KIND_ACTION ||
       !constant_equal(f.sender,s->allowed_sender,16) ||
       !constant_equal(f.target,s->self,16) ||
       !constant_equal(f.session,s->session,16) ||
       !near_ms(f.timestamp_ms,now_ms,s->max_skew_ms))return RBP_RX_BAD;
    rbp_rx_result result;
    if(s->has_committed && f.sequence==s->committed_sequence &&
       constant_equal(f.nonce,s->committed_nonce,8)) {
        result=RBP_RX_DUPLICATE;
    } else {
        if(s->has_committed && f.sequence<=s->committed_sequence)return RBP_RX_BAD;
        rbp_diag_event ev={0};
        ev.type=1; ev.sequence=f.sequence;memcpy(ev.sender,f.sender,16);memcpy(ev.nonce,f.nonce,8);
        int status=rbp_handoff_push(handoff,&ev);
        if(status==0)return RBP_RX_BUSY; /* do not consume sequence and do not ACK */
        if(status!=1)return RBP_RX_BAD;
        s->committed_sequence=f.sequence;
        memcpy(s->committed_nonce,f.nonce,8);
        s->has_committed=1;
        result=RBP_RX_ACCEPTED;
    }
    rbp_frame_c reply={0};
    reply.kind=RBP_KIND_ACK;reply.action=0;
    reply.sequence=f.sequence;reply.timestamp_ms=now_ms;
    memcpy(reply.sender,s->self,16);memcpy(reply.target,s->allowed_sender,16);
    memcpy(reply.session,s->session,16);memcpy(reply.nonce,f.nonce,8);
    if(!rbp_wire_encode(&reply,s->key,ack))return RBP_RX_BAD;
    return result;
}
