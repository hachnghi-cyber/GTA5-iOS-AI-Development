#define _POSIX_C_SOURCE 200809L
/* Two independent POSIX UDP sockets on localhost; NOT two iPhones. */
#include "rbp_device_network.h"
#include "rbp_native_adapter.h"
#include <arpa/inet.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
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
