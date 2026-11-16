#define _POSIX_C_SOURCE 200809L
/* Linux-only shared-library test of DllMain, registration, callback, and
 * sandbox file logging. ALL ScriptHook/native functions are MOCKS, never GTA. */
#include <assert.h>
#include <dlfcn.h>
#include <time.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void (*callback)(void)=NULL;
static unsigned register_count=0,unregister_count=0,wait_count=0;
static int fast_wait=0;
static unsigned native_init_count=0,native_push_count=0,native_call_count=0;
static uint64_t hashes[16]={0}, ret=0;

__attribute__((visibility("default")))
void scriptRegister(void *module,void (*f)(void)) {
    assert(module==(void*)(uintptr_t)0x1234 && !callback);
    callback=f;++register_count;
}
__attribute__((visibility("default")))
void scriptUnregister(void *module) {
    assert(module==(void*)(uintptr_t)0x1234 && callback);
    callback=NULL;++unregister_count;
}
__attribute__((visibility("default")))
void scriptWait(uint32_t duration) {
    assert(duration==16);
    ++wait_count;
    if(!fast_wait){
        struct timespec pause={.tv_sec=0,.tv_nsec=1000000};
        nanosleep(&pause,NULL);
    }
}
__attribute__((visibility("default")))
void nativeInit(uint64_t hash) {
    assert(native_init_count<16);
    hashes[native_init_count++]=hash;
}
__attribute__((visibility("default")))
void nativePush64(uint64_t v) {(void)v;++native_push_count;}
__attribute__((visibility("default")))
uint64_t *nativeCall(void) {++native_call_count;return &ret;}
static int contains(const char *path,const char *needle) {
    FILE *fp=fopen(path,"r");assert(fp);
    char data[8192];size_t n=fread(data,1,sizeof(data)-1,fp);fclose(fp);
    data[n]=0;
    return strstr(data,needle)!=NULL;
}
int main(int argc,char **argv) {
    assert(argc==3 || argc==4);
    fast_wait = (argc==4 && !strcmp(argv[3],"fast"));
    int stage=atoi(argv[2]);assert(stage==0||stage==1||stage==3);
    char dir[]="/tmp/rbp-loader-XXXXXX";
    assert(mkdtemp(dir));
    char docs[512],log_path[512];
    assert(snprintf(docs,sizeof(docs),"%s/Documents",dir)<(int)sizeof(docs));
    assert(snprintf(log_path,sizeof(log_path),"%s/RBPProbe.log",docs)<(int)sizeof(log_path));
    assert(mkdir(docs,0700)==0);
    assert(setenv("HOME",dir,1)==0);
    void *plugin=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if(!plugin){fprintf(stderr,"dlopen failed: %s\n",dlerror());return 2;}
    int (*entry)(void*,unsigned,void*)=NULL;
    *(void **)(&entry)=dlsym(plugin,"DllMain");
    assert(entry);
    assert(entry((void*)(uintptr_t)0x1234,1,NULL)==1);
    assert(entry((void*)(uintptr_t)0x1234,1,NULL)==1); /* idempotent attach */
    assert(register_count==1 && callback);
    callback();
    assert(wait_count==(fast_wait?4u:900u));
    if(stage==0){assert(native_init_count==0&&native_push_count==0&&native_call_count==0);}
    else if(!fast_wait) {
        assert(native_init_count==3&&native_push_count==4&&native_call_count==3);
        assert(hashes[0]==UINT64_C(0xB87A37EEB7FAA67D));
        assert(hashes[1]==UINT64_C(0x6C188BE134E074AA));
        assert(hashes[2]==UINT64_C(0x9D77056A530643F6));
    }
    assert(contains(log_path,"DLLMAIN_ATTACH"));
    assert(contains(log_path,"SCRIPT_REGISTER_ATTEMPTED"));
    assert(contains(log_path,"SCRIPT_CALLBACK_ENTER"));
    assert(contains(log_path,"SCRIPT_TICK tick=1"));
    if(stage>=1 && !fast_wait)assert(contains(log_path,"LOCAL_E1_GAME_ACTION_INVOKED=1"));
    if(stage==3 && !fast_wait)assert(contains(log_path,"CONFIG_MISSING_OR_INVALID_NETWORK_DISABLED"));
    assert(contains(log_path,fast_wait?"SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED":"SCRIPT_CALLBACK_COMPLETE=1 ticks=901"));
    if(fast_wait)assert(contains(log_path,"SCRIPT_CALLBACK_COMPLETE=0 ticks=4"));
    assert(entry((void*)(uintptr_t)0x1234,0,NULL)==1);
    assert(unregister_count==1 && !callback);
    assert(contains(log_path,"DLLMAIN_DETACH"));
    assert(dlclose(plugin)==0);
    unlink(log_path);rmdir(docs);rmdir(dir);
    printf("PASS host MOCK plugin loader E%d: dlopen/DllMain/register/tick/native mocks/file log/detach (NOT iPhone)\n",stage);
    return 0;
}
