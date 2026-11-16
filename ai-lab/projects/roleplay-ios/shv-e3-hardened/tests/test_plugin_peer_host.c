#define _POSIX_C_SOURCE 200809L
/* Process-level E3 integration with a MOCK ScriptHook scheduler/native ABI.
 * Each process loads its own plugin and config; actual UDP sockets are used. */
#include <assert.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static void (*callback)(void)=NULL;
static unsigned ticks=0, native_calls=0;
static uint64_t ret;
__attribute__((visibility("default")))
void scriptRegister(void *module,void (*func)(void)) {(void)module;assert(!callback);callback=func;}
__attribute__((visibility("default")))
void scriptUnregister(void *module) {(void)module;callback=NULL;}
__attribute__((visibility("default")))
void scriptWait(uint32_t delta) {
    assert(delta==16);
    struct timespec wait={.tv_sec=0,.tv_nsec=5000000};
    nanosleep(&wait,NULL);
    ++ticks;
}
__attribute__((visibility("default")))
void nativeInit(uint64_t hash) {(void)hash;}
__attribute__((visibility("default")))
void nativePush64(uint64_t arg) {(void)arg;}
__attribute__((visibility("default")))
uint64_t *nativeCall(void) {native_calls++;return &ret;}
int main(int argc,char **argv) {
    if(argc!=2){fputs("usage: test_plugin_peer_host /absolute/plugin.so\n",stderr);return 2;}
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if(!h){fprintf(stderr,"dlopen error: %s\n",dlerror());return 2;}
    int (*main_entry)(void*,unsigned,void*)=NULL;
    *(void **)(&main_entry)=dlsym(h,"DllMain");
    assert(main_entry);
    assert(main_entry((void*)(uintptr_t)0x5678,1,NULL));
    assert(callback);
    callback();
    assert(ticks==900);
    assert(native_calls>=3);
    assert(main_entry((void*)(uintptr_t)0x5678,0,NULL));
    assert(callback==NULL);
    assert(dlclose(h)==0);
    fprintf(stderr,"[HOST_MOCK] NATIVE_CALLS=%u TICKS=%u\n",native_calls,ticks);
    return 0;
}
