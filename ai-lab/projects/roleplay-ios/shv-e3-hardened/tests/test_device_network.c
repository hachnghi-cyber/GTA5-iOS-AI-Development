#define _POSIX_C_SOURCE 200809L
/* Two independent POSIX UDP sockets on localhost; NOT two iPhones. */
#include "rbp_device_network.h"
#include "rbp_native_adapter.h"
#include <arpa/inet.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <sys/time.h>
#include <unistd.h>
#include <fcntl.h>
static int ninit=0, npush=0, ncall=0;
static uint64_t last_hash=0, dummy_ret=0;
static void mock_init(uint64_t hash) {last_hash=hash;ninit++;}
static void mock_push(uint64_t v) {(void)v;npush++;}
static uint64_t *mock_call(void) {ncall++;return &dummy_ret;}
static int reserve_port(void) {
    int sock=socket(AF_INET,SOCK_DGRAM,0); assert(sock>=0);
    struct sockaddr_in addr={0};addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);addr.sin_port=0;
    assert(bind(sock,(struct sockaddr*)&addr,sizeof(addr))==0);
    socklen_t len=sizeof(addr);assert(getsockname(sock,(struct sockaddr*)&addr,&len)==0);
    int port=ntohs(addr.sin_port);close(sock);return port;
}
static void snooze(long ms) {
    struct timespec t={.tv_sec=ms/1000,.tv_nsec=(ms%1000)*1000000L};
    nanosleep(&t,NULL);
}
static void write_cfg(const char *name,int mode,int self,int peer,int local,int remote,int extra) {
    FILE *fp=fopen(name,"w");assert(fp);
    fprintf(fp,"mode=%s\nlisten_port=%d\npeer_port=%d\npeer_ipv4=127.0.0.1\n",
                mode==1?"receiver":"sender",local,remote);
    fprintf(fp,"self_id_hex=%032x\npeer_id_hex=%032x\nsession_hex=%032x\n",self,peer,0x45);
    fprintf(fp,"key_hex=000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f\n");
    if(extra)fprintf(fp,"mode=sender\n");
    fclose(fp);
}
int main(void) {
    char a[]="/tmp/rbpAXXXXXX",b[]="/tmp/rbpBXXXXXX";
    int fd=mkstemp(a);assert(fd>=0);close(fd);
    fd=mkstemp(b);assert(fd>=0);close(fd);
    int port_a=reserve_port(),port_b=reserve_port();
    while(port_a==port_b)port_b=reserve_port();
    write_cfg(a,2,0x11,0x22,port_a,port_b,0);
    write_cfg(b,1,0x22,0x11,port_b,port_a,0);
    rbp_device_config ca={0},cb={0};
    assert(rbp_config_read(a,&ca));assert(rbp_config_read(b,&cb));
    write_cfg(a,2,0x11,0x22,port_a,port_b,1);
    rbp_device_config invalid={0};assert(!rbp_config_read(a,&invalid));
    write_cfg(a,2,0x11,0x22,port_a,port_b,0);
    rbp_handoff qa,qb;rbp_handoff_init(&qa);rbp_handoff_init(&qb);
    rbp_device_network sender,receiver;
    assert(rbp_network_start(&receiver,&cb,&qb));
    assert(rbp_network_start(&sender,&ca,&qa));
    for(int i=0;i<1000 && (!atomic_load(&sender.active)||!atomic_load(&receiver.active));i++)snooze(5);
    assert(atomic_load(&sender.active)&&atomic_load(&receiver.active));
    /* Negative: a valid HMAC with the correct sender ID/session from the
     * WRONG UDP source port must not get an ACK or enter the game queue. */
    int rogue=socket(AF_INET,SOCK_DGRAM,0); assert(rogue>=0);
    struct sockaddr_in rogue_bind={0};
    rogue_bind.sin_family=AF_INET;
    rogue_bind.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    rogue_bind.sin_port=0;
    assert(bind(rogue,(struct sockaddr*)&rogue_bind,sizeof rogue_bind)==0);
    struct sockaddr_in got_port={0};socklen_t got_len=sizeof got_port;
    assert(getsockname(rogue,(struct sockaddr*)&got_port,&got_len)==0);
    assert(ntohs(got_port.sin_port)!=(uint16_t)port_a);
    rbp_frame_c forged={0};forged.kind=RBP_KIND_ACTION;
    forged.action=RBP_DIAG_PING;forged.sequence=44;
    struct timeval now={0};assert(gettimeofday(&now,NULL)==0);
    forged.timestamp_ms=(uint64_t)now.tv_sec*1000u+(uint64_t)now.tv_usec/1000u;
    memcpy(forged.sender,ca.self,16);
    memcpy(forged.target,ca.peer,16);
    memcpy(forged.session,ca.session,16);
    memset(forged.nonce,0x99,sizeof forged.nonce);
    uint8_t forged_wire[96];assert(rbp_wire_encode(&forged,ca.key,forged_wire));
    struct sockaddr_in addr_b={0};addr_b.sin_family=AF_INET;
    addr_b.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    addr_b.sin_port=htons((uint16_t)port_b);
    assert(sendto(rogue,forged_wire,96,0,(struct sockaddr*)&addr_b,sizeof addr_b)==96);
    struct timeval timeout={.tv_sec=0,.tv_usec=300000};
    assert(setsockopt(rogue,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout)==0);
    uint8_t rogue_reply[96];
    assert(recvfrom(rogue,rogue_reply,96,0,NULL,NULL)<0);
    assert(errno==EAGAIN||errno==EWOULDBLOCK);
    assert(atomic_load(&qb.state)==RBP_EMPTY);
    /* Avoid unsynchronized reads of worker-owned receiver state. If rogue
     * seq=44 had committed, subsequent legitimate seq=1 would be rejected. */
    close(rogue);
    /* Legitimate peer still works after an invalid endpoint is dropped. */
    assert(rbp_network_request_ping(&sender));
    rbp_native_api fake={mock_init,mock_push,mock_call};
    rbp_diag_event receipt={0};int got=0;
    for(int i=0;i<500 && !got;i++) {
        got=rbp_diagnostic_game_tick_with_event(&qb,&fake,&receipt);
        if(!got)snooze(5);
    }
    assert(got==1 && receipt.sequence==1);
    assert(ninit==3 && npush==4 && ncall==3);
    assert(last_hash==UINT64_C(0x9D77056A530643F6));
    assert(rbp_network_report_native_invocation(&receiver,receipt.sequence,receipt.nonce)==1);
    /* Ensure send ACK does NOT trigger second duplicate game-thread event. */
    snooze(500);
    assert(rbp_diagnostic_game_tick(&qb,&fake)==0);
    rbp_network_stop(&sender);rbp_network_stop(&receiver);
    unlink(a);unlink(b);
    puts("PASS E2+E3 MOCK: independent host UDP sockets -> HMAC -> queued -> script-thread mocked native calls, 1 exact action; NOT GTA");
    return 0;
}
