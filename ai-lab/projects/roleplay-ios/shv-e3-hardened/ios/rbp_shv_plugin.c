/*
 * GTA5 v13.3 ScriptHook V addon: native diagnostic E0/E1/E3 only.
 * Built-in SHV loader scans Frameworks/(name ending in .shv.dylib) and calls DllMain(h,1,0).
 * Target evidence: ScriptHookV UUID F768B7B5-AD75-39F4-83D3-8E49234325B5,
 * loader _sh_game_start image-relative offset 0x4bec.
 *
 * E0: register/tick only (default); E1: local HUD; E3: UDP + remote HUD.
 * NO RAGE hooks, no GTA binary patch, no remote ped modification.
 * NOT validated on a real iPhone; use only signed test builds.
 */
#include "rbp_handoff.h"
#include "rbp_native_adapter.h"
#include "rbp_device_network.h"
#include "rbp_device_log.h"
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#if defined(__APPLE__) && !defined(RBP_HOST_TEST)
#include <mach-o/loader.h>
#include <mach-o/dyld.h>
#include <mach/machine.h>
#endif

#ifndef RBP_PROBE_STAGE
#define RBP_PROBE_STAGE 0
#endif
#if RBP_PROBE_STAGE!=0 && RBP_PROBE_STAGE!=1 && RBP_PROBE_STAGE!=3
#error "RBP_PROBE_STAGE must be 0, 1, or 3"
#endif

typedef void (*shv_script_register)(void *,void (*)(void));
typedef void (*shv_script_unregister)(void *);
typedef void (*shv_script_wait)(uint32_t);
/* Static export from v13.3 libgtacompat, read-only shim status, NOT RAGE proof. */
typedef uint8_t (*compat_online_in_session_fn)(void);
static shv_script_register g_reg;
static shv_script_unregister g_unreg;
static shv_script_wait g_wait;
static compat_online_in_session_fn g_online_status;
static void *g_compat_handle;
static rbp_native_api g_api;
static rbp_handoff g_handoff;
#if RBP_PROBE_STAGE>=3
static rbp_device_network g_network;
#endif
static void *g_shv_handle;
static void *g_module;
static int g_registered=0;
static void script_main(void);

/* Verify the runtime image UUID before calling an ABI inferred from the
 * exact shipped ScriptHookV binary. This avoids silently using an unrelated
 * ScriptHook port or a changed version. No memory patch or hook. */
static int verify_shv_runtime_uuid(void) {
#if defined(__APPLE__) && !defined(RBP_HOST_TEST)
    static const uint8_t target_uuid[16]={
        0xf7,0x68,0xb7,0xb5,0xad,0x75,0x39,0xf4,
        0x83,0xd3,0x8e,0x49,0x23,0x43,0x25,0xb5
    };
    Dl_info info={0};
    if(!g_reg || !dladdr((const void *)(uintptr_t)g_reg,&info) || !info.dli_fbase){
        rbp_logf("[RBP_PROBE] SHV_UUID_READ_FAILED"); return 0;
    }
    const struct mach_header_64 *mh=(const struct mach_header_64*)info.dli_fbase;
    if(mh->magic!=MH_MAGIC_64 || mh->cputype!=CPU_TYPE_ARM64 ||
       mh->ncmds>512 || mh->sizeofcmds>(16u<<20))return 0;
    const uint8_t *cursor=(const uint8_t*)mh+sizeof(*mh);
    uint32_t consumed=0;
    for(uint32_t i=0;i<mh->ncmds;i++){
        if(consumed>mh->sizeofcmds || mh->sizeofcmds-consumed<sizeof(struct load_command))break;
        const struct load_command *lc=(const struct load_command*)cursor;
        if(lc->cmdsize<sizeof(*lc) || lc->cmdsize>mh->sizeofcmds-consumed)break;
        if(lc->cmd==LC_UUID && lc->cmdsize>=sizeof(struct uuid_command)){
            const struct uuid_command *uuid=(const struct uuid_command*)cursor;
            int ok=memcmp(uuid->uuid,target_uuid,16)==0;
            rbp_logf("[RBP_PROBE] SCRIPT_HOOK_UUID_MATCH=%d",ok);
            return ok;
        }
        cursor+=lc->cmdsize;
        consumed+=lc->cmdsize;
    }
    rbp_logf("[RBP_PROBE] SHV_UUID_MISSING");
    return 0;
#else
    rbp_logf("[RBP_PROBE] SCRIPT_HOOK_UUID_CHECK=MOCK_HOST");
    return 1;
#endif
}

/* Resolve an EXISTING loaded image; do not load or initialize extra code.
 * `@loader_path` and `@rpath` may be different aliases for a dyld image,
 * therefore query the exact loaded image path as the last fallback.
 * UUID of ScriptHookV is checked independently after dlsym.
 * Image enumeration is startup-only and not an asynchronous network callback.
 */
static void *loaded_sibling(const char *name) {
#if defined(RBP_HOST_TEST)
    (void)name;
    /* Linux fixture: symbols supplied by the mock executable. */
    return dlopen(NULL,RTLD_NOW);
#else
    void *h=dlopen(name,RTLD_NOW|RTLD_NOLOAD);
#if defined(__APPLE__)
    if(h)return h;
    const char *base=strrchr(name,'/');
    base=base?base+1:name;
    if(!base[0] || strchr(base,'/'))return NULL;
    uint32_t count=_dyld_image_count();
    for(uint32_t i=0;i<count;i++){
        const char *path=_dyld_get_image_name(i);
        if(!path)continue;
        const char *leaf=strrchr(path,'/');
        if(!leaf || strcmp(leaf+1,base)!=0)continue;
        h=dlopen(path,RTLD_NOW|RTLD_NOLOAD);
        if(h){
            rbp_logf("[RBP_PROBE] LOADED_IMAGE_RESOLVED name=%s method=dyld_image_path",base);
            return h;
        }
    }
#endif
    return NULL;
#endif
}
/* POSIX dlsym produces void*, while ISO C does not permit a direct cast
 * to a function pointer under -Wpedantic. Copy the symbol representation only
 * when the sizes match; this is the same explicit ABI contract on Apple ARM64.
 * This also lets Clang and GCC both compile the Linux host diagnostics.
 */
static int rbp_symbol(void *image, const char *name, void *slot, size_t slot_size) {
    void *symbol=dlsym(image,name);
    if(!symbol || !slot || slot_size!=sizeof(symbol))return 0;
    memcpy(slot,&symbol,sizeof symbol);
    return 1;
}
static int resolve_shv(void) {
    /* @loader_path is relative to THIS plugin in Frameworks, whereas @rpath
     * without LC_RPATH is not a valid assumption for a dlopen'ed dylib. */
    void *shv=loaded_sibling("@loader_path/ScriptHookV.dylib");
#ifndef RBP_HOST_TEST
    if(!shv)shv=loaded_sibling("@rpath/ScriptHookV.dylib");
#endif
    if(!shv){ rbp_logf("[RBP_PROBE] SHV_NOT_LOADED_OR_PATH_UNRESOLVED"); return 0; }
    /* On this port, these C symbols are directly exported from ScriptHookV. */
    (void)rbp_symbol(shv,"scriptRegister",&g_reg,sizeof g_reg);
    (void)rbp_symbol(shv,"scriptUnregister",&g_unreg,sizeof g_unreg);
    (void)rbp_symbol(shv,"scriptWait",&g_wait,sizeof g_wait);
    (void)rbp_symbol(shv,"nativeInit",&g_api.init,sizeof g_api.init);
    (void)rbp_symbol(shv,"nativePush64",&g_api.push,sizeof g_api.push);
    (void)rbp_symbol(shv,"nativeCall",&g_api.call,sizeof g_api.call);
    if(!g_reg || !g_wait || !g_unreg){dlclose(shv);return 0;}
    if(!verify_shv_runtime_uuid()){dlclose(shv);return 0;}
#if RBP_PROBE_STAGE>=1
    if(!g_api.init || !g_api.push || !g_api.call){dlclose(shv);return 0;}
#endif
    g_shv_handle=shv;
    void *compat=NULL;
#ifndef RBP_HOST_TEST
    compat=loaded_sibling("@loader_path/libgtacompat.dylib");
    if(!compat)compat=loaded_sibling("@rpath/libgtacompat.dylib");
#endif
    if(compat){
        (void)rbp_symbol(compat,"_Z17online_in_sessionv",&g_online_status,sizeof g_online_status);
        g_compat_handle=compat;
    }
    return 1;
}

/* E0/E1/E3: refuse to spin when ScriptHookV has no scheduler TLS.
 * Exact v13.3 _scriptWait offset 0x56b4 returns without swapping when TLS
 * context is null. One finite diagnostic run only (E3 sends at tick 360).
 * A positive delay is not proof of game-thread affinity or HUD visibility.
 */
#define RBP_MAX_SCRIPT_TICKS 900u
#define RBP_WAIT_MS 16u
#define RBP_FAST_RETURN_NS UINT64_C(500000)
#define RBP_FAST_RETURN_LIMIT 4u
static uint64_t rbp_monotonic_ns(void) {
    struct timespec now={0};
    if(clock_gettime(CLOCK_MONOTONIC,&now)!=0 || now.tv_sec<0 ||
       now.tv_nsec<0 || now.tv_nsec>=1000000000L) return 0;
    return (uint64_t)now.tv_sec * UINT64_C(1000000000)+(uint64_t)now.tv_nsec;
}
static void script_main(void) {
    unsigned fast_returns=0;
    unsigned long long tick=0;
    int failed=0;
    rbp_logf("[RBP_PROBE] SCRIPT_CALLBACK_ENTER stage=%d thread=%p\n",
            RBP_PROBE_STAGE,(void*)pthread_self());
    for(tick=1;tick<=RBP_MAX_SCRIPT_TICKS;tick++) {
#if RBP_PROBE_STAGE>=3
        if(tick==10) {
            /* Network off when no explicit, validated configuration exists. */
            const char *home=getenv("HOME");
            char config_path[1024]={0};
            rbp_device_config c={0};
            if(home && strlen(home)+25<sizeof(config_path)) {
                snprintf(config_path,sizeof(config_path),"%s/Documents/RBPProbe.cfg",home);
                if(rbp_config_read(config_path,&c)) {
                    int ok=rbp_network_start(&g_network,&c,&g_handoff);
                    rbp_logf("[RBP_PROBE] NETWORK_START_REQUESTED=%d mode=%d\n",ok,c.mode);
                    memset(&c,0,sizeof c);
                } else rbp_logf("[RBP_PROBE] CONFIG_MISSING_OR_INVALID_NETWORK_DISABLED\n");
            }
        }
#endif
#if RBP_PROBE_STAGE>=1
        if(tick==120) {
            int result=rbp_local_probe_action(&g_api);
            rbp_logf("[RBP_PROBE] LOCAL_E1_GAME_ACTION_INVOKED=%d tick=%llu thread=%p\n",
                    result,tick,(void*)pthread_self());
            /* Only device screen recording can prove HUD actually displayed. */
        }
#endif
#if RBP_PROBE_STAGE>=3
        if(tick==360 && g_network.thread_token && g_network.conf.mode==2) {
            rbp_logf("[RBP_PROBE] SEND_ONCE_REQUESTED=%d\n",
                      rbp_network_request_ping(&g_network));
        }
        rbp_diag_event receipt={0};
        int result=rbp_diagnostic_game_tick_with_event(&g_handoff,&g_api,&receipt);
        if(result!=0) {
            rbp_logf("[RBP_PROBE] REMOTE_E3_GAME_ACTION_INVOKED=%d seq=%llu tick=%llu thread=%p\n",
                    result,(unsigned long long)receipt.sequence,tick,(void*)pthread_self());
            if(result==1 && g_network.conf.mode==1) {
                int enqueued=rbp_network_report_native_invocation(
                    &g_network,receipt.sequence,receipt.nonce);
                rbp_logf("[RBP_PROBE] NATIVE_INVOCATION_REPORT_QUEUED=%d seq=%llu (NOT visual proof)\n",
                         enqueued,(unsigned long long)receipt.sequence);
            }
        }
        memset(&receipt,0,sizeof(receipt));
#endif
        if(tick==1 || tick==180 || tick==600 || tick==RBP_MAX_SCRIPT_TICKS){
            rbp_logf("[RBP_PROBE] SCRIPT_TICK tick=%llu thread=%p\n",tick,(void*)pthread_self());
            rbp_logf("[RBP_PROBE] COMPAT_ONLINE_SESSION_SHIM=%d (not RAGE authority)\n",
                    g_online_status?(int)g_online_status():-1);
        }
        uint64_t before=rbp_monotonic_ns();
        if(!before || !g_wait) {
            rbp_logf("[RBP_PROBE] SCHEDULER_CLOCK_OR_WAIT_INVALID FAIL_CLOSED\n");
            failed=1;break;
        }
        g_wait(RBP_WAIT_MS); /* cooperative scheduler; NO network/game calls here */
        uint64_t after=rbp_monotonic_ns();
        if(!after || after<before) {
            rbp_logf("[RBP_PROBE] SCHEDULER_CLOCK_OR_WAIT_INVALID FAIL_CLOSED\n");
            failed=1;break;
        }
        fast_returns = (after-before < RBP_FAST_RETURN_NS) ? fast_returns+1 : 0;
        if(fast_returns >= RBP_FAST_RETURN_LIMIT) {
            rbp_logf("[RBP_PROBE] SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED\n");
            failed=1;break;
        }
    }
#if RBP_PROBE_STAGE>=3
    /* Exit diagnostic worker before ScriptHook marks callback finished.
     * Network recv SO_RCVTIMEO is 250ms; do not join per-frame. */
    if(g_network.thread_token)rbp_network_stop(&g_network);
#endif
    rbp_logf("[RBP_PROBE] SCRIPT_CALLBACK_COMPLETE=%d ticks=%llu\n",
             !failed,(unsigned long long)tick);
}

/* SHV calls exactly DllMain(handle, 1, NULL) in its addon load path.
 * Reason 0, if issued by the loader, unregisters; do not assume hot-unload safe.
 */
__attribute__((visibility("default")))
int DllMain(void *module, unsigned reason, void *reserved) {
    (void)reserved;
    if(reason==1) {
        if(g_registered)return 1;
        struct timeval started={0};
        (void)gettimeofday(&started,NULL);
#if defined(__APPLE__) && !defined(RBP_HOST_TEST)
        const char *platform="iphoneos-target";
#else
        const char *platform="host-mock";
#endif
        rbp_logf("[RBP_PROBE] RUN_BEGIN phase=4 stage=%d platform=%s pid=%ld start_ms=%llu",
                 RBP_PROBE_STAGE,platform,(long)getpid(),
                 (unsigned long long)started.tv_sec*1000u + (unsigned long long)started.tv_usec/1000u);
        rbp_logf("[RBP_PROBE] SOURCE_CHECKPOINT=phase12-e3-receipt-retry\n");
        rbp_logf("[RBP_PROBE] DLLMAIN_ATTACH stage=%d\n",RBP_PROBE_STAGE);
        if(!resolve_shv()){
            rbp_logf("[RBP_PROBE] SHV_SYMBOL_RESOLUTION_FAILED\n");return 0;
        }
        g_module=module;
        rbp_handoff_init(&g_handoff);
        g_reg(module,script_main);
        g_registered=1;
        rbp_logf("[RBP_PROBE] SCRIPT_REGISTER_ATTEMPTED (void API; only a script tick proves registration)\n");
    } else if(reason==0 && g_registered) {
        rbp_logf("[RBP_PROBE] DLLMAIN_DETACH\n");
#if RBP_PROBE_STAGE>=3
        rbp_network_stop(&g_network);
#endif
        g_unreg(g_module);
        g_registered=0;
        if(g_shv_handle)dlclose(g_shv_handle);
        if(g_compat_handle)dlclose(g_compat_handle);
        g_shv_handle=NULL;g_compat_handle=NULL;
    }
    return 1;
}
