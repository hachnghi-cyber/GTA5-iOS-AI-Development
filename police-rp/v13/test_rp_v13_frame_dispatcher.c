#include "rp_v13_frame_dispatcher.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned checks;
#define CHECK(c) do { ++checks; assert((c)); } while (0)

typedef struct {
    unsigned frames;
    unsigned stops;
    int frame_result;
    int stop_result;
} FakeBridge;

static int process(void *ctx) {
    FakeBridge *b=(FakeBridge *)ctx;
    ++b->frames;
    return b->frame_result;
}
static int stop(void *ctx) {
    FakeBridge *b=(FakeBridge *)ctx;
    ++b->stops;
    return b->stop_result;
}
static RP_V13_IdentityEvidence identity(void) {
    static const uint8_t app[16]={0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,
                                  0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf};
    static const uint8_t compat[16]={0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,
                                     0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc};
    RP_V13_IdentityEvidence v={0};
    v.abi=RP_V13_IDENTITY_ABI;
    memcpy(v.gta5_uuid,app,16);
    memcpy(v.gtacompat_uuid,compat,16);
    v.executable_uuid_verified_by_loader=1;
    v.compat_uuid_verified_by_loader=1;
    return v;
}
static RP_V13_SessionEvidence session(void) {
    RP_V13_SessionEvidence s={0};
    s.abi=RP_V13_SESSION_ABI;
    s.session_id=81;
    s.local_player_id=12;
    s.host_player_id=22;
    s.monotonic_ms=1500;
    s.peer_generation=5;
    s.online=1;
    s.game_thread_verified=1;
    s.session_verified=1;
    s.carrier_authenticated=1;
    s.local_peer_connected=1;
    s.host_peer_connected=1;
    return s;
}

static void test_normal_and_host_migration(void) {
    RP_V13_FrameDispatcher d;
    RP_V13_IdentityEvidence i=identity();
    RP_V13_SessionEvidence s=session();
    FakeBridge b={0,0,1,1};
    rp_v13_dispatcher_init(NULL,process,stop,&b);
    CHECK(rp_v13_dispatcher_tick(NULL,&i,&s)==RP_V13_DISPATCH_BLOCKED);
    rp_v13_dispatcher_init(&d,process,stop,&b);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    CHECK(b.frames==1 && b.stops==0);
    s.monotonic_ms+=16;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    CHECK(b.frames==2);
    s.host_player_id+=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.stops==1 && b.frames==2);
    CHECK(!rp_v13_session_gate_is_ready(&d.gate));
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    CHECK(b.frames==3 && b.stops==1);
}

static void test_frame_failure_and_stop_retry(void) {
    RP_V13_FrameDispatcher d;
    RP_V13_IdentityEvidence i=identity();
    RP_V13_SessionEvidence s=session();
    FakeBridge b={0,0,0,0};
    rp_v13_dispatcher_init(&d,process,stop,&b);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.frames==1 && b.stops==1);
    CHECK(!rp_v13_session_gate_is_ready(&d.gate));
    b.frame_result=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.frames==1 && b.stops==2);
    b.stop_result=-1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.frames==1 && b.stops==3);
    b.stop_result=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.frames==1 && b.stops==4);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    CHECK(b.frames==2 && b.stops==4);
}

static void test_game_thread_lost_before_stop(void) {
    RP_V13_FrameDispatcher d;
    RP_V13_IdentityEvidence i=identity();
    RP_V13_SessionEvidence s=session();
    FakeBridge b={0,0,1,1};
    rp_v13_dispatcher_init(&d,process,stop,&b);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    s.game_thread_verified=0;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.frames==1 && b.stops==0);
    CHECK(rp_v13_dispatcher_tick(&d,&i,NULL)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.frames==1 && b.stops==0);
    s.game_thread_verified=2;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.stops==0);
    s.game_thread_verified=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.stops==1 && b.frames==1);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    CHECK(b.frames==2);
}

static void test_identity_offline_and_missing_callbacks(void) {
    RP_V13_FrameDispatcher d;
    RP_V13_IdentityEvidence i=identity();
    RP_V13_SessionEvidence s=session();
    FakeBridge b={0,0,1,1};
    rp_v13_dispatcher_init(&d,NULL,stop,&b);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_BLOCKED);
    CHECK(b.frames==0 && b.stops==0);
    d.process=process;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    d.stop_local=NULL;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASE_PENDING);
    CHECK(b.stops==0 && b.frames==1);
    d.stop_local=stop;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.stops==1);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    i.gta5_uuid[0] ^= 1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.frames==2 && b.stops==2);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_BLOCKED);
    i=identity();
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    s.online=0;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.frames==3 && b.stops==3);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_BLOCKED);
}

static void test_session_variants_and_zero_evidence(void) {
    RP_V13_FrameDispatcher d;
    RP_V13_IdentityEvidence i=identity();
    RP_V13_SessionEvidence s=session();
    FakeBridge b={0,0,1,1};
    rp_v13_dispatcher_init(&d,process,stop,&b);
    CHECK(rp_v13_dispatcher_tick(&d,NULL,&s)==RP_V13_DISPATCH_BLOCKED);
    CHECK(rp_v13_dispatcher_tick(&d,&i,NULL)==RP_V13_DISPATCH_BLOCKED);
    CHECK(b.frames==0 && b.stops==0);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    s.peer_generation+=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.frames==1 && b.stops==1);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    s.session_id+=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.frames==2 && b.stops==2);
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_PROCESSED);
    s.monotonic_ms-=1;
    CHECK(rp_v13_dispatcher_tick(&d,&i,&s)==RP_V13_DISPATCH_RELEASED);
    CHECK(b.frames==3 && b.stops==3);
}

int main(void) {
    test_normal_and_host_migration();
    test_frame_failure_and_stop_retry();
    test_game_thread_lost_before_stop();
    test_identity_offline_and_missing_callbacks();
    test_session_variants_and_zero_evidence();
    printf("RP v13 frame dispatcher PASS: %u assertions (host-only)\n",checks);
    return 0;
}
