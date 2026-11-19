/*
 * GTA5Port RP v1.9 — one-PED Story-Mode experiment, never part of default Online.
 *
 * Gate: exact opt-in file RP19_STORY_TEST.txt + explicit F11 press in Story
 *       + both network-state native guards report false + live RPR1 remote
 *       + valid local RPF8 pose. At most ONE non-networked local PED.
 *
 * This intentionally proves CREATE_PED independently of synchronizing two
 * players. It is NOT multiplayer. Unknown/missing natives must fail closed.
 *
 * Windows x64 ScriptHookV guest: built by clang -target x86_64-pc-windows-msvc
 * without proprietary headers. Mod files live in the SAME mod subfolder.
 */
#include <stdint.h>
#include <stddef.h>

typedef struct {uint32_t generation,epoch;unsigned count;} rp18_mailbox_summary;
extern int rp18_decode(const unsigned char *,unsigned,rp18_mailbox_summary *);

#define RP19_REMOTE_BYTES 764u
#define RP19_LOCAL_BYTES 48u
#define RP19_MAX_TICKS_STALE 16u
#define RP19_MAX_MODEL_TICKS 16u
#define RP19_MODEL_NAME "a_m_m_business_01"

typedef struct {float x,y,z,heading;uint32_t sequence;} rp19_pose;
typedef struct {uint64_t id;rp19_pose pose;uint32_t generation,epoch;} rp19_remote;

static uint32_t rp19_u32(const unsigned char *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static uint64_t rp19_u64(const unsigned char *p) {
    return (uint64_t)rp19_u32(p)|((uint64_t)rp19_u32(p+4)<<32);
}
static float rp19_float(const unsigned char *p) {
    uint32_t bits=rp19_u32(p);
    float f;
    __builtin_memcpy(&f,&bits,sizeof f);
    return f;
}
static int rp19_finite_bounds(float f,float bound) {
    /* Comparisons reject NaN and infinities without CRT imports. */
    return f>=-bound && f<=bound;
}
static uint32_t rp19_fnv(const unsigned char *p,unsigned size) {
    uint32_t h=2166136261u;
    for(unsigned i=0;i<size;i++)h=(h^p[i])*16777619u;
    return h;
}
int rp19_local_decode(const unsigned char *p,unsigned n,rp19_pose *out) {
    if(!p||!out||n!=RP19_LOCAL_BYTES)return 0;
    if(p[0]!='R'||p[1]!='P'||p[2]!='F'||p[3]!='8'||p[4]!=8||
       p[5]!=0||p[6]!=48||p[7]!=0||rp19_u32(p+12)!=2||
       rp19_u32(p+40)!=0x08112026u||rp19_fnv(p,44)!=rp19_u32(p+44))return 0;
    float x=rp19_float(p+20),y=rp19_float(p+24);
    float z=rp19_float(p+28),h=rp19_float(p+32);
    if(!rp19_u32(p+8)||!rp19_u32(p+16)||rp19_u32(p+16)==UINT32_MAX||
       !rp19_finite_bounds(x,100000.f)||!rp19_finite_bounds(y,100000.f)||
       !rp19_finite_bounds(z,20000.f)||!rp19_finite_bounds(h,360000.f))return 0;
    *out=(rp19_pose){x,y,z,h,rp19_u32(p+8)};
    return 1;
}
int rp19_remote_decode(const unsigned char *p,unsigned n,rp19_remote *out) {
    rp18_mailbox_summary summary={0};
    if(!p||!out||rp18_decode(p,n,&summary)!=0||summary.count!=1)return 0;
    const unsigned char *v=p+16;
    uint64_t id=rp19_u64(v);
    if(!id)return 0;
    *out=(rp19_remote){.id=id,.pose={
          rp19_float(v+8),rp19_float(v+12),rp19_float(v+16),
          rp19_float(v+20),summary.generation},
        .generation=summary.generation,.epoch=summary.epoch};
    return 1;
}
static uint32_t rp19_joaat(const char *s) {
    uint32_t h=0;
    for(;*s;s++){
        unsigned char c=(unsigned char)*s;
        if(c>='A'&&c<='Z')c=(unsigned char)(c+32);
        h+=c;h+=(h<<10);h^=h>>6;
    }
    h+=h<<3;h^=h>>11;h+=h<<15;
    return h;
}
uint32_t rp19_test_model(void){return rp19_joaat(RP19_MODEL_NAME);}

/* Pure gate; applies before ANY game-mutating native. */
int rp19_gate(int file_enabled,int user_armed,int network_offline,
              int local_valid,int remote_valid,int recently_updated) {
    return file_enabled==1 && user_armed==1 && network_offline==1 &&
           local_valid==1 && remote_valid==1 && recently_updated==1;
}

#ifndef RP19_TEST
#define RP19_VK_F11 0x7Au
#define RP19_READ 0x80000000u
#define RP19_OPEN_EXISTING 3u
#define RP19_NORMAL 128u
#define RP19_STDOUT ((void *)(uintptr_t)0x11u)

__declspec(dllimport) void *CreateFileA(const char*,unsigned,unsigned,void*,unsigned,unsigned,void*);
__declspec(dllimport) int ReadFile(void*,void*,unsigned,unsigned*,void*);
__declspec(dllimport) int CloseHandle(void*);
__declspec(dllimport) int WriteFile(void*,const void*,unsigned,unsigned*,void*);
__declspec(dllimport) short GetAsyncKeyState(int);
__declspec(dllimport) void scriptRegister(void*,void (*)(void));
__declspec(dllimport) void scriptWait(unsigned);
__declspec(dllimport) void nativeInit(uint64_t);
__declspec(dllimport) void nativePush64(uint64_t);
__declspec(dllimport) uint64_t *nativeCall(void);

#define H_NETWORK_SESSION 0xD83C2B94E7508980ULL
#define H_NETWORK_GAME 0x10FAB35428CCC9D7ULL
#define H_REQUEST_MODEL 0x963D27A58DF860ACULL
#define H_HAS_MODEL 0x98A4EB5D89A0C952ULL
#define H_IS_PED_MODEL 0x75816577FEA6DAD5ULL
#define H_IS_MODEL_VALID 0xC0296A2EDF545E92ULL
#define H_CREATE_PED 0xD49F9B0955C367DEULL
#define H_DELETE_PED 0x9614299DCB53E54BULL
#define H_PED_EXISTS 0x7239B21A38F536BAULL
#define H_FREEZE 0x428CA6DBD1094446ULL
#define H_MODEL_RELEASE 0xE532F5D78798DAABULL

static uint64_t rp19_ret(uint64_t hash,const uint64_t *args,unsigned count) {
    nativeInit(hash);
    for(unsigned i=0;i<count;i++)nativePush64(args[i]);
    const uint64_t *p=nativeCall();
    return p ? *p : 0;
}
static uint64_t rp19_call1(uint64_t hash,uint64_t arg) {
    return rp19_ret(hash,&arg,1);
}
static uint64_t rp19_floatarg(float f) {
    uint32_t bits;
    __builtin_memcpy(&bits,&f,4);
    return (uint64_t)bits;
}
static void rp19_log(const char *s) {
    char buf[128];unsigned i=0,done=0;
    const char *pre="RP19 ";while(*pre&&i<120)buf[i++]=*pre++;
    while(*s&&i<120)buf[i++]=*s++;
    buf[i++]='\n';
    (void)WriteFile(RP19_STDOUT,buf,i,&done,0);
}
static int rp19_read_exact(const char *file,void *dest,unsigned n) {
    void *fd=CreateFileA(file,RP19_READ,7u,0,RP19_OPEN_EXISTING,RP19_NORMAL,0);
    if(!fd||(uintptr_t)fd==(uintptr_t)-1)return 0;
    unsigned got=0,extra=0;unsigned char pad=0;
    int ok=ReadFile(fd,dest,n,&got,0);
    int second=ok&&got==n ? ReadFile(fd,&pad,1,&extra,0):0;
    (void)CloseHandle(fd);
    return ok&&got==n&&second&&extra==0;
}
static int rp19_opted_in(void) {
    static const char token[]="RP19_STORY_TEST=1\n";
    unsigned char data[sizeof token-1];
    if(!rp19_read_exact("RP19_STORY_TEST.txt",data,sizeof data))return 0;
    for(unsigned i=0;i<sizeof data;i++)if(data[i]!=(unsigned char)token[i])return 0;
    return 1;
}
static int rp19_offline(void) {
    /* Neither of these is a positive Story-mode attestation.
       The marker + per-launch F11 are additional deliberate opt-in gates. */
    return rp19_ret(H_NETWORK_SESSION,0,0)==0 &&
           rp19_ret(H_NETWORK_GAME,0,0)==0;
}
static void rp19_delete(uint32_t *ped) {
    if(!*ped)return;
    if(rp19_call1(H_PED_EXISTS,*ped)) {
        uint32_t handle=*ped;
        uint64_t args[]={ (uint64_t)(uintptr_t)&handle };
        (void)rp19_ret(H_DELETE_PED,args,1);
    }
    *ped=0;
    rp19_log("PED_CLEANUP");
}
static void rp19_script(void) {
    uint32_t ped=0,peer_epoch=0,peer_frame=0;
    uint64_t peer_id=0;
    unsigned stale=0,model_ticks=0;
    int armed=0,pressed=0,pending=0,had_error=0;
    const uint32_t model=rp19_test_model();
    rp19_log("DISARMED_F11_REQUIRED");
    for(;;){
        int key=(GetAsyncKeyState(RP19_VK_F11)&0x8000)!=0;
        if(key&&!pressed){
            armed=!armed;
            rp19_log(armed?"ARM_REQUEST":"DISARM");
        }
        pressed=key;
        int opt=rp19_opted_in();
        int offline=rp19_offline();
        if(!opt||!armed||!offline){
            rp19_delete(&ped);
            if(pending){(void)rp19_call1(H_MODEL_RELEASE,model);pending=0;}
            stale=0;model_ticks=0;peer_frame=0;peer_epoch=0;peer_id=0;
            if(!offline&&!had_error){rp19_log("ONLINE_GUARD_BLOCK");had_error=1;}
            scriptWait(250);
            continue;
        }
        had_error=0;
        unsigned char file[RP19_REMOTE_BYTES],local_raw[RP19_LOCAL_BYTES];
        rp19_remote remote={0};rp19_pose local={0};
        int rv=rp19_read_exact("RPV10_remote.bin",file,sizeof file)&&
               rp19_remote_decode(file,sizeof file,&remote);
        int lv=rp19_read_exact("RPV08_pose.bin",local_raw,sizeof local_raw)&&
               rp19_local_decode(local_raw,sizeof local_raw,&local);
        if(rv&&remote.epoch==peer_epoch&&remote.generation==peer_frame)stale++;
        else if(rv&&(remote.epoch!=peer_epoch||remote.generation>peer_frame)){
            if(remote.id!=peer_id&&peer_id)rp19_delete(&ped);
            peer_id=remote.id;peer_epoch=remote.epoch;peer_frame=remote.generation;
            stale=0;
        }else{rv=0;stale=RP19_MAX_TICKS_STALE+1;}
        if(!rp19_gate(opt,armed,offline,lv,rv,stale<=RP19_MAX_TICKS_STALE)){
            rp19_delete(&ped);
            if(pending){(void)rp19_call1(H_MODEL_RELEASE,model);pending=0;}
            scriptWait(250);
            continue;
        }
        if(!ped){
            if(!pending){
                if(!rp19_call1(H_IS_MODEL_VALID,model)||!rp19_call1(H_IS_PED_MODEL,model)){
                    rp19_log("MODEL_NOT_SUPPORTED");
                    armed=0;scriptWait(250);continue;
                }
                (void)rp19_call1(H_REQUEST_MODEL,model);
                pending=1;model_ticks=0;
                rp19_log("MODEL_REQUESTED");
            }
            if(!rp19_call1(H_HAS_MODEL,model)){
                if(++model_ticks>RP19_MAX_MODEL_TICKS){
                    rp19_log("MODEL_TIMEOUT");
                    (void)rp19_call1(H_MODEL_RELEASE,model);pending=0;armed=0;
                }
                scriptWait(250);continue;
            }
            /* Spawn harmless one non-networked local PED near the player's local RPF8 pose.
               Remote coordinates are deliberately NOT applied in this prototype. */
            float x=local.x+3.f,y=local.y+2.f,z=local.z+0.2f,h=local.heading;
            uint64_t args[]={4u,model,rp19_floatarg(x),rp19_floatarg(y),
                rp19_floatarg(z),rp19_floatarg(h),0u,0u};
            ped=(uint32_t)rp19_ret(H_CREATE_PED,args,8);
            (void)rp19_call1(H_MODEL_RELEASE,model);pending=0;
            if(ped&&rp19_call1(H_PED_EXISTS,ped)){
                uint64_t freeze[]={ped,1u};
                (void)rp19_ret(H_FREEZE,freeze,2);
                rp19_log("PED_CREATED_SINGLE_LOCAL_PROTOTYPE");
            }else{ped=0;armed=0;rp19_log("CREATE_PED_FAILED");}
        }
        scriptWait(250);
    }
}
int __stdcall DllMainCRTStartup(void *module,unsigned reason,void *reserved) {
    (void)reserved;
    if(reason==1)scriptRegister(module,rp19_script);
    return 1;
}
#endif
