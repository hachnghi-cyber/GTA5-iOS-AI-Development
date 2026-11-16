#define _POSIX_C_SOURCE 200809L
#include "rbp_device_network.h"
#include "rbp_device_log.h"
#include <arpa/inet.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static int hex_digit(char c) {
    if(c>='0'&&c<='9')return c-'0';
    if(c>='a'&&c<='f')return c-'a'+10;
    if(c>='A'&&c<='F')return c-'A'+10;
    return -1;
}
static int decode_hex(const char *p,size_t n,uint8_t *out) {
    if(strlen(p)!=n*2)return 0;
    for(size_t i=0;i<n;i++){
        int a=hex_digit(p[i*2]),b=hex_digit(p[i*2+1]);
        if(a<0||b<0)return 0;
        out[i]=(uint8_t)(a*16+b);
    }
    return 1;
}
static void trim_line(char *s) {
    size_t n=strlen(s);
    while(n && (s[n-1]=='\r'||s[n-1]=='\n'||s[n-1]==' '||s[n-1]=='\t'))s[--n]=0;
}
static int parse_port(const char *s,uint16_t *out) {
    if(!s||!*s)return 0;
    char *end=NULL;unsigned long x=strtoul(s,&end,10);
    if(*end||x<1024||x>65535)return 0;
    *out=(uint16_t)x;return 1;
}
int rbp_config_read(const char *path,rbp_device_config *out) {
    if(!path||!out)return 0;
    FILE *fp=fopen(path,"r");if(!fp)return 0;
    rbp_device_config temp={0};
    unsigned seen=0;int valid=1;
    char line[256];
    while(fgets(line,sizeof(line),fp)) {
        if(!strchr(line,'\n') && !feof(fp)) {valid=0;break;} /* no truncated fields */
        trim_line(line);
        if(!line[0]||line[0]=='#')continue;
        char *eq=strchr(line,'=');if(!eq){valid=0;break;}
        *eq=0;const char *v=eq+1;unsigned bit=0;
        if(strcmp(line,"mode")==0){bit=1u<<0; if(strcmp(v,"receiver")==0)temp.mode=1;
            else if(strcmp(v,"sender")==0)temp.mode=2;else valid=0;}
        else if(strcmp(line,"listen_port")==0){bit=1u<<1;valid=parse_port(v,&temp.listen_port);}
        else if(strcmp(line,"peer_port")==0){bit=1u<<2;valid=parse_port(v,&temp.peer_port);}
        else if(strcmp(line,"peer_ipv4")==0){bit=1u<<3;
            if(strlen(v)>=sizeof(temp.peer_ipv4)){valid=0;} else {
               struct in_addr addr;valid=inet_pton(AF_INET,v,&addr)==1;
               if(valid)memcpy(temp.peer_ipv4,v,strlen(v)+1);
            }}
        else if(strcmp(line,"self_id_hex")==0){bit=1u<<4;valid=decode_hex(v,16,temp.self);}
        else if(strcmp(line,"peer_id_hex")==0){bit=1u<<5;valid=decode_hex(v,16,temp.peer);}
        else if(strcmp(line,"session_hex")==0){bit=1u<<6;valid=decode_hex(v,16,temp.session);}
        else if(strcmp(line,"key_hex")==0){bit=1u<<7;valid=decode_hex(v,32,temp.key);}
        else {valid=0;}
        if(!valid || (seen&bit)){valid=0;break;}
        seen|=bit;
    }
    if(ferror(fp))valid=0;
    fclose(fp);
    if(!valid || seen!=0xff || !memcmp(temp.self,temp.peer,16)){
        memset(&temp,0,sizeof(temp));return 0;
    }
    *out=temp;memset(&temp,0,sizeof(temp));return 1;
}
static uint64_t wall_ms(void) {
    struct timeval t;
    if(gettimeofday(&t,NULL))return 0;
    return (uint64_t)t.tv_sec*1000u+(uint64_t)t.tv_usec/1000u;
}
static int open_socket(uint16_t port) {
    int sock=socket(AF_INET,SOCK_DGRAM,0);
    if(sock<0)return -1;
    struct timeval timeout={.tv_sec=0,.tv_usec=250000};
    if(setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout))!=0) {
        close(sock);return -1;
    }
    struct sockaddr_in bindaddr={0};
    bindaddr.sin_family=AF_INET;
    bindaddr.sin_addr.s_addr=htonl(INADDR_ANY);
    bindaddr.sin_port=htons(port);
    if(bind(sock,(struct sockaddr*)&bindaddr,sizeof(bindaddr))!=0){close(sock);return -1;}
    return sock;
}
/* RBP1 stores sequence in bytes [8..15], network byte order. */
static uint64_t wire_sequence(const uint8_t wire[96]) {
    uint64_t seq=0;
    for(unsigned i=8;i<16;i++)seq=(seq<<8)|wire[i];
    return seq;
}
static int same_sockaddr(const struct sockaddr_in *x,const struct sockaddr_in *y) {
    return x->sin_family==y->sin_family &&
           x->sin_port==y->sin_port && x->sin_addr.s_addr==y->sin_addr.s_addr;
}
static int random_nonce(uint8_t nonce[8]) {
#ifdef __APPLE__
    arc4random_buf(nonce,8);return 1;
#else
    FILE *f=fopen("/dev/urandom","rb");if(!f)return 0;
    int good=fread(nonce,1,8,f)==8;fclose(f);return good;
#endif
}
/* Called ONLY on the UDP receive thread. The script thread never sends UDP.
 * Only the last accepted diagnostic action is eligible; a raced/ambiguous
 * sequence is rejected rather than falsely claiming execution on sender A.
 */
static void emit_native_invocation_report(rbp_device_network *s,int sock,
                                          const struct sockaddr_in *last_peer,
                                          socklen_t last_len,int has_peer) {
    if(atomic_load_explicit(&s->receipt_state,memory_order_acquire)!=2)return;
    uint64_t seq=s->receipt_sequence;
    uint8_t nonce[8];memcpy(nonce,s->receipt_nonce,8);
    if(!has_peer || !seq || seq!=s->receiver.committed_sequence ||
       memcmp(nonce,s->receiver.committed_nonce,8)!=0) {
        rbp_logf("[RBP_NET] NATIVE_REPORT_STALE_OR_NO_PEER_DROP\n");
        atomic_store_explicit(&s->receipt_state,0,memory_order_release);
        memset(nonce,0,sizeof nonce);return;
    }
    rbp_frame_c report={0};report.kind=RBP_KIND_NATIVE_INVOKED;
    report.sequence=seq;report.timestamp_ms=wall_ms();
    memcpy(report.sender,s->conf.self,16);
    memcpy(report.target,s->conf.peer,16);
    memcpy(report.session,s->conf.session,16);
    memcpy(report.nonce,nonce,8);
    uint8_t wire[96];int transmitted=0;
    if(rbp_wire_encode(&report,s->conf.key,wire)) {
        transmitted=sendto(sock,wire,sizeof wire,0,
                      (const struct sockaddr*)last_peer,last_len)==(ssize_t)sizeof wire;
    }
    rbp_logf("[RBP_NET] NATIVE_INVOCATION_REPORT_SENT=%d seq=%llu (API call only)\n",
             transmitted,(unsigned long long)seq);
    memset(nonce,0,sizeof nonce);
    memset(s->receipt_nonce,0,sizeof(s->receipt_nonce));
    s->receipt_sequence=0;
    atomic_store_explicit(&s->receipt_state,0,memory_order_release);
}
static void network_receiver(rbp_device_network *s,int sock) {
    /* Accept diagnostic traffic only from the explicitly configured LAN peer.
     * HMAC protects packet bytes but does not attest UDP source IP/port.
     * Do not permit a different socket to replace last_peer or receive ACK. */
    struct sockaddr_in authorized_peer={0};
    authorized_peer.sin_family=AF_INET;
    authorized_peer.sin_port=htons(s->conf.peer_port);
    if(inet_pton(AF_INET,s->conf.peer_ipv4,&authorized_peer.sin_addr)!=1){
        rbp_logf("[RBP_NET] PEER_IPV4_INVALID_FAIL_CLOSED\n");
        return;
    }
    uint8_t buffer[512],ack[96];
    struct sockaddr_in last_peer={0};socklen_t last_len=sizeof(last_peer);
    int has_peer=0;
    for(;atomic_load(&s->running);) {
        emit_native_invocation_report(s,sock,&last_peer,last_len,has_peer);
        struct sockaddr_in peer={0};socklen_t n=sizeof(peer);
        ssize_t bytes=recvfrom(sock,buffer,sizeof(buffer),0,(struct sockaddr*)&peer,&n);
        if(bytes<0){
            if(errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR){
                rbp_logf("[RBP_NET] RX_SOCKET_ERROR=%d\n",errno);
            }
            continue;
        }
        if(!same_sockaddr(&peer,&authorized_peer)) {
            /* Never print addresses, IDs or credentials in diagnostic logs. */
            rbp_logf("[RBP_NET] UNEXPECTED_UDP_ENDPOINT_DROP\n");
            continue;
        }
        rbp_rx_result status=rbp_receiver_handle(&s->receiver,s->handoff,
                                      buffer,(size_t)bytes,wall_ms(),ack);
        if(status==RBP_RX_ACCEPTED||status==RBP_RX_DUPLICATE) {
            if(status==RBP_RX_ACCEPTED){last_peer=peer;last_len=n;has_peer=1;}
            /* ACK only QUEUE_ACCEPTED; does not mean HUD/engine action executed. */
            ssize_t sent=sendto(sock,ack,96,0,(struct sockaddr*)&peer,n);
            rbp_logf("[RBP_NET] %s seq=%llu ack_sent=%d\n",
              status==RBP_RX_DUPLICATE?"PACKET_DUPLICATE":"PACKET_ACCEPTED",
              (unsigned long long)wire_sequence(ack),sent==96);
        } else if(status==RBP_RX_BUSY) {
            rbp_logf("[RBP_NET] QUEUE_BUSY_NO_ACK\n");
        } else {
            rbp_logf("[RBP_NET] REJECTED_PACKET\n");
        }
    }
}
static void network_sender(rbp_device_network *s,int sock) {
    struct sockaddr_in peer={0};
    peer.sin_family=AF_INET;peer.sin_port=htons(s->conf.peer_port);
    if(inet_pton(AF_INET,s->conf.peer_ipv4,&peer.sin_addr)!=1)return;
    for(uint64_t seq=1;atomic_load(&s->running);) {
        if(!atomic_exchange(&s->send_once,0)){
            struct timespec pause={.tv_sec=0,.tv_nsec=50000000};
            nanosleep(&pause,NULL);continue;
        }
        rbp_frame_c f={0};f.kind=RBP_KIND_ACTION;f.action=RBP_DIAG_PING;
        f.sequence=seq++;f.timestamp_ms=wall_ms();
        memcpy(f.sender,s->conf.self,16);memcpy(f.target,s->conf.peer,16);
        memcpy(f.session,s->conf.session,16);
        if(!random_nonce(f.nonce)){rbp_logf("[RBP_NET] NO_ENTROPY\n");continue;}
        uint8_t wire[96];
        if(!rbp_wire_encode(&f,s->conf.key,wire))continue;
        int verified=0, report_verified=0;
        for(unsigned try_count=0;try_count<8 && atomic_load(&s->running) && !verified;try_count++) {
            if(sendto(sock,wire,96,0,(struct sockaddr*)&peer,sizeof(peer))!=96)continue;
            rbp_logf("[RBP_NET] PACKET_TRANSMITTED seq=%llu attempt=%u\n",
                    (unsigned long long)f.sequence,try_count+1);
            uint8_t buf[512];struct sockaddr_in src={0};socklen_t len=sizeof(src);
            ssize_t n=recvfrom(sock,buf,sizeof(buf),0,(struct sockaddr*)&src,&len);
            rbp_frame_c response={0};
            uint64_t received_ms=wall_ms();
            if(n==96 && same_sockaddr(&peer,&src) &&
               rbp_wire_decode(buf,96,s->conf.key,&response)) {
                if(rbp_response_matches_request(&response,&f,RBP_KIND_ACK,received_ms))verified=1;
                if(rbp_response_matches_request(&response,&f,RBP_KIND_NATIVE_INVOKED,received_ms))report_verified=1;
            }
        }
        rbp_logf("[RBP_NET] %s seq=%llu (queue receipt ONLY)\n",
            verified?"ACK_VERIFIED":"ACK_TIMEOUT",(unsigned long long)f.sequence);
        /* The game-thread marker can arrive after the queue ACK.
         * It proves that the native API sequence was called, not that RAGE
         * displayed the HUD. No retries of native gameplay are attempted. */
        for(unsigned trial=0;verified && !report_verified && trial<10 &&
            atomic_load(&s->running);trial++) {
            uint8_t buf[512];struct sockaddr_in src={0};socklen_t len=sizeof src;
            ssize_t n=recvfrom(sock,buf,sizeof buf,0,(struct sockaddr*)&src,&len);
            rbp_frame_c report={0};uint64_t current_ms=wall_ms();
            if(n==96 && same_sockaddr(&peer,&src) &&
               rbp_wire_decode(buf,96,s->conf.key,&report) &&
               rbp_response_matches_request(&report,&f,RBP_KIND_NATIVE_INVOKED,current_ms))
               report_verified=1;
        }
        rbp_logf("[RBP_NET] %s seq=%llu (native API invoked, NOT HUD observed)\n",
                 verified && report_verified ? "NATIVE_INVOCATION_REPORT_VERIFIED" :
                 "NATIVE_INVOCATION_REPORT_UNCONFIRMED",
                 (unsigned long long)f.sequence);
    }
}
static void *network_main(void *ctx) {
    rbp_device_network *s=(rbp_device_network*)ctx;
    int sock=open_socket(s->conf.listen_port);
    if(sock<0){rbp_logf("[RBP_NET] BIND_FAILED\n");atomic_store(&s->active,0);return NULL;}
    atomic_store(&s->active,1);
    rbp_logf("[RBP_NET] NETWORK_ACTIVE mode=%s port=%u\n",
                s->conf.mode==1?"receiver":"sender",s->conf.listen_port);
    if(s->conf.mode==1)network_receiver(s,sock);
    else if(s->conf.mode==2)network_sender(s,sock);
    close(sock);atomic_store(&s->active,0);return NULL;
}
int rbp_network_start(rbp_device_network *s, const rbp_device_config *conf,rbp_handoff *q) {
    if(!s||!conf||!q||!(conf->mode==1||conf->mode==2))return 0;
    memset(s,0,sizeof(*s));s->conf=*conf;s->handoff=q;
    memcpy(s->receiver.self,conf->self,16);
    memcpy(s->receiver.allowed_sender,conf->peer,16);
    memcpy(s->receiver.key,conf->key,32);
    memcpy(s->receiver.session,conf->session,16);
    s->receiver.max_skew_ms=15000;
    atomic_init(&s->running,1);atomic_init(&s->send_once,0);atomic_init(&s->active,0);atomic_init(&s->receipt_state,0);
    pthread_t *p=malloc(sizeof(*p));if(!p){atomic_store(&s->running,0);return 0;}
    if(pthread_create(p,NULL,network_main,s)!=0){free(p);atomic_store(&s->running,0);return 0;}
    s->thread_token=p;return 1;
}
int rbp_network_request_ping(rbp_device_network *s) {
    if(!s||s->conf.mode!=2||!atomic_load(&s->active))return 0;
    /* One outstanding diagnostic request only; producer is script callback. */
    return atomic_exchange(&s->send_once,1)==0;
}
int rbp_network_report_native_invocation(rbp_device_network *s,
                                        uint64_t seq,const uint8_t nonce[8]) {
    if(!s || !nonce || !seq || !s->thread_token ||
       s->conf.mode!=1 || !atomic_load(&s->active))return 0;
    int expected=0;
    if(!atomic_compare_exchange_strong_explicit(&s->receipt_state,&expected,1,
                                                 memory_order_acq_rel,memory_order_acquire))
        return 0; /* Single-slot: preserve earlier report. */
    s->receipt_sequence=seq;
    memcpy(s->receipt_nonce,nonce,8);
    atomic_store_explicit(&s->receipt_state,2,memory_order_release);
    return 1;
}
void rbp_network_stop(rbp_device_network *s) {
    if(!s||!s->thread_token)return;
    atomic_store(&s->running,0);
    pthread_t *p=(pthread_t*)s->thread_token;
    pthread_join(*p,NULL);free(p);
    s->thread_token=NULL;
    memset(s->conf.key,0,sizeof(s->conf.key));
    memset(s->receiver.key,0,sizeof(s->receiver.key));
}
