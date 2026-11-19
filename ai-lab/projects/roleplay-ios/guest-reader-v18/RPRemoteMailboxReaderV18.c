/* GTA5Port Roleplay v1.8 — ScriptHookV guest mailbox proof, NO game natives.
 * Read RPV10_remote.bin written by the ARM64 v1.6 host bridge into the ASI's
 * own Mods subfolder. All values are untrusted; validate before logging.
 * No PED spawn, no Online hooks, no network, no secrets, no coordinates in log.
 * The public GTA5Port 1.5.2 source is reference ONLY; actual target is v2.0.0.
 */
#include <stdint.h>
#include <stddef.h>

#define RP18_BYTES 764u
#define RP18_MAX_PEERS 31u

typedef struct {
    uint32_t generation;
    uint32_t epoch;
    unsigned count;
} rp18_mailbox_summary;

static uint32_t rp18_u32(const unsigned char *b) {
    return (uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
static uint64_t rp18_u64(const unsigned char *b) {
    return (uint64_t)rp18_u32(b)|((uint64_t)rp18_u32(b+4)<<32);
}
static uint32_t rp18_crc(const unsigned char *b, unsigned n) {
    uint32_t h=2166136261u;
    for (unsigned i=0;i<n;i++) h=(h^(uint32_t)b[i])*16777619u;
    return h;
}
static int rp18_float_bound(uint32_t bits, unsigned bound) {
    /* Reject all NaN and +/-Infinity first. Bounds as floats, not raw bit ordering. */
    if ((bits&0x7f800000u)==0x7f800000u) return 0;
    union {uint32_t u;float f;} value;
    value.u=bits;
    return value.f <= (float)bound && value.f >= -(float)bound;
}
int rp18_decode(const unsigned char *frame, unsigned n, rp18_mailbox_summary *out) {
    if (!frame||!out||n!=RP18_BYTES) return -1;
    if (frame[0]!='R'||frame[1]!='P'||frame[2]!='R'||frame[3]!='1'||
        frame[4]!=1||frame[5]>RP18_MAX_PEERS||frame[6]||frame[7])return -2;
    if (rp18_crc(frame,RP18_BYTES-4)!=rp18_u32(frame+RP18_BYTES-4))return -3;
    uint32_t generation=rp18_u32(frame+8),epoch=rp18_u32(frame+12);
    if (!generation||!epoch)return -4;
    unsigned count=frame[5];
    for (unsigned i=0;i<count;i++) {
        const unsigned char *p=frame+16+24u*i;
        uint64_t id=rp18_u64(p);
        if (!id||id>0x0000ffffffffffffULL)return -5;
        for (unsigned j=0;j<i;j++) {
            if(id==rp18_u64(frame+16+24u*j))return -6;
        }
        if (!rp18_float_bound(rp18_u32(p+8),100000u)||
            !rp18_float_bound(rp18_u32(p+12),100000u)||
            !rp18_float_bound(rp18_u32(p+16),20000u)||
            !rp18_float_bound(rp18_u32(p+20),360000u))return -7;
    }
    out->count=count;out->generation=generation;out->epoch=epoch;
    return 0;
}

#ifndef RP18_TEST
/* The port intercepts Win64 IAT calls by symbol name in its Blink ScriptHookV
 * runtime. This deliberately requires no proprietary headers or game code. */
__declspec(dllimport) void *CreateFileA(const char *,unsigned,unsigned,
                                        void *,unsigned,unsigned,void *);
__declspec(dllimport) int ReadFile(void *,void *,unsigned,unsigned *,void *);
__declspec(dllimport) int CloseHandle(void *);
__declspec(dllimport) int WriteFile(void *,const void *,unsigned,unsigned *,void *);
__declspec(dllimport) void scriptRegister(void *,void (*)(void));
__declspec(dllimport) void scriptWait(unsigned);
enum { RP18_GENERIC_READ=0x80000000u, RP18_SHARE_ALL=7u,
       RP18_OPEN_EXISTING=3u, RP18_FILE_ATTRIBUTE_NORMAL=128u };

static void rp18_log(const char *message,unsigned count,uint32_t generation) {
    char out[110];unsigned n=0,written=0;
    const char *prefix="RP18 ";
    while (*prefix&&n<sizeof(out)-1)out[n++]=*prefix++;
    while (*message&&n<sizeof(out)-1)out[n++]=*message++;
    if (generation) {
        const char *a=" count=";while(*a&&n<sizeof(out)-1)out[n++]=*a++;
        uint32_t values[2]={count,generation};
        for(int k=0;k<2;k++){
            char digits[12];unsigned j=0;uint32_t v=values[k];
            do {digits[j++]=(char)('0'+v%10);v/=10;}while(v&&j<sizeof(digits));
            while(j&&n<sizeof(out)-1)out[n++]=digits[--j];
            if (!k){const char *b=" frame=";while(*b&&n<sizeof(out)-1)out[n++]=*b++;}
        }
    }
    out[n++]='\n';
    /* stdout HANDLE in the port's Win32 shim; native-port.log prints "ASI console: RP18 ..." */
    (void)WriteFile((void *)(uintptr_t)0x11u,out,n,&written,(void *)0);
}
static int rp18_read(rp18_mailbox_summary *summary) {
    const char *name="RPV10_remote.bin";
    void *handle=CreateFileA(name,RP18_GENERIC_READ,RP18_SHARE_ALL,
                             (void*)0,RP18_OPEN_EXISTING,RP18_FILE_ATTRIBUTE_NORMAL,(void*)0);
    if (!handle||(uintptr_t)handle==(uintptr_t)-1)return -10;
    unsigned char frame[RP18_BYTES];unsigned got=0;unsigned char extra=0;unsigned more=0;
    int ok=ReadFile(handle,frame,RP18_BYTES,&got,(void*)0);
    int extra_ok=ok && got==RP18_BYTES ?
         ReadFile(handle,&extra,1,&more,(void*)0):0;
    (void)CloseHandle(handle);
    if(!ok||got!=RP18_BYTES||!extra_ok||more)return -11;
    return rp18_decode(frame,RP18_BYTES,summary);
}
static void rp18_script(void) {
    uint32_t last_epoch=0,last_generation=0;
    int last_error=12345;
    rp18_log("READER_STARTED",0,0);
    for (;;) {
        rp18_mailbox_summary summary={0};
        int code=rp18_read(&summary);
        if(!code) {
            if(last_epoch!=summary.epoch||summary.generation>last_generation) {
                rp18_log("MAILBOX_VALID",summary.count,summary.generation);
                last_epoch=summary.epoch;last_generation=summary.generation;
            } else if(summary.epoch==last_epoch&&summary.generation<last_generation) {
                code=-12; /* stale update; do not accept older frames */
            }
        }
        if(code!=last_error) {
            if(code==-10)rp18_log("FILE_MISSING",0,0);
            else if(code==-12)rp18_log("STALE_FRAME",0,0);
            else if(code)rp18_log("INVALID_FRAME",0,0);
            last_error=code;
        }
        scriptWait(250);
    }
}
int __stdcall DllMainCRTStartup(void *module,unsigned reason,void *reserved) {
    (void)reserved;
    if(reason==1)scriptRegister(module,rp18_script);
    return 1;
}
#endif
