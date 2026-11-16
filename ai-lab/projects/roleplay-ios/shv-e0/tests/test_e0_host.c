#define _POSIX_C_SOURCE 200809L
/* This mocks all ScriptHookV calls; no RAGE/iPhone runtime is exercised. */
#include <assert.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>
static void (*callback)(void);
static int registers, unregisters, waits, quick_wait;
__attribute__((visibility("default")))
void scriptRegister(void *mod, void(*func)(void)) {
    assert(mod == (void *)(uintptr_t)0x1234);
    assert(!callback);
    callback = func;
    registers++;
}
__attribute__((visibility("default")))
void scriptUnregister(void *mod) {
    assert(mod == (void *)(uintptr_t)0x1234);
    assert(callback);
    callback = NULL;
    unregisters++;
}
__attribute__((visibility("default")))
void scriptWait(uint32_t ms) {
    assert(ms == 16);
    ++waits;
    if (quick_wait) return;
    struct timespec nap = {.tv_sec = 0, .tv_nsec = 2000000};
    nanosleep(&nap, NULL);
}
static int has(const char *p, const char *needle) {
    FILE *f = fopen(p,"rb"); assert(f);
    char buf[4096];
    size_t n = fread(buf,1,sizeof(buf)-1,f);
    (void)fclose(f);buf[n]=0;
    return strstr(buf,needle)!=NULL;
}
int main(int argc, char **argv) {
    assert(argc == 3);
    assert(!strcmp(argv[2], "normal") || !strcmp(argv[2], "fast"));
    quick_wait = !strcmp(argv[2], "fast");
    char home[] = "/tmp/rbp-e0-test-XXXXXX";
    assert(mkdtemp(home));
    char documents[512], log[512];
    assert(snprintf(documents,sizeof documents,"%s/Documents",home) < (int)sizeof documents);
    assert(mkdir(documents,0700)==0);
    assert(snprintf(log,sizeof log,"%s/RBPProbeE0.log",documents) < (int)sizeof log);
    assert(setenv("HOME",home,1)==0);
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if (!h) {fprintf(stderr,"dlopen: %s\n",dlerror());return 2;}
    int (*entry)(void *,unsigned,void *) = NULL;
    *(void **)(&entry) = dlsym(h,"DllMain");
    assert(entry);
    assert(entry((void *)(uintptr_t)0x1234,1,NULL) == 1);
    assert(entry((void *)(uintptr_t)0x1234,1,NULL) == 1);
    assert(registers == 1 && callback);
    assert(has(log,"SCRIPT_REGISTER_ATTEMPTED=1"));
    assert(!has(log,"CALLBACK_ENTER"));
    callback();
    if (quick_wait) {
        assert(waits == 4);
        assert(has(log,"SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED"));
        assert(!has(log,"SCRIPT_CALLBACK_COMPLETE=1"));
        assert(!has(log,"SCRIPT_TICK=30"));
    } else {
        assert(waits == 120);
        assert(!has(log,"SCRIPT_WAIT_FAST_RETURN=1"));
        assert(has(log,"SCRIPT_TICK=120"));
        assert(has(log,"SCRIPT_CALLBACK_COMPLETE=1"));
    }
    assert(has(log,"SCRIPT_HOOK_UUID_CHECK=HOST_MOCK_ONLY"));
    assert(has(log,"CALLBACK_ENTER"));
    assert(has(log,"SCRIPT_TICK=1"));
    if (!quick_wait) assert(has(log,"SCRIPT_TICK=30"));
    assert(entry((void *)(uintptr_t)0x1234,0,NULL)==1);
    assert(unregisters == 1 && !callback);
    assert(has(log,"DLLMAIN_DETACH"));
    assert(dlclose(h)==0);
    assert(unlink(log)==0);
    assert(rmdir(documents)==0);
    assert(rmdir(home)==0);
    printf("PASS E0 host MOCK mode=%s waits=%d registration, termination, detach; NOT iPhone\n", argv[2], waits);
    return 0;
}
