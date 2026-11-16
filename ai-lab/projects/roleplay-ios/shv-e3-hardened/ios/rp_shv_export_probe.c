/* Read-only exported symbol probe. No method swizzling, native invocation,
 * code patching, network access or game mutation.
 * Intended to be called only after host has initialized the ScriptHook dylib.
 * Compile/link/codesign on macOS with the real iPhoneOS SDK before device use.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>

__attribute__((visibility("default")))
int rbp_probe_exports(void) {
    const char *names[] = {"scriptRegister", "nativeInit", "nativePush64", "nativeCall", "scriptWait"};
    int present = 0;
    void *handle = dlopen("@rpath/ScriptHookV.dylib", RTLD_NOW | RTLD_NOLOAD);
    if (!handle) {
        fprintf(stderr, "[RBP_PROBE] shv_loaded=0 symbols=0/5 engine_action=0\n");
        return 0;
    }
    for (unsigned i=0; i<5; ++i) {
        void *p = dlsym(handle, names[i]);
        fprintf(stderr, "[RBP_PROBE] exported_%s=%d\n", names[i], p != 0);
        present += (p != 0);
    }
    dlclose(handle);
    fprintf(stderr,"[RBP_PROBE] shv_loaded=1 symbols=%d/5 engine_action=0\n",present);
    return present;
}
