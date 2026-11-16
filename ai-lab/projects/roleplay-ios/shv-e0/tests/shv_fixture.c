/* Host-only ScriptHookV dynamic loader fixture. No game calls. */
#include <stdint.h>
static void (*cb)(void);
static unsigned registered,unregistered,wait_calls;
__attribute__((visibility("default"))) void scriptRegister(void *m,void (*f)(void)) {(void)m; cb=f; registered++;}
__attribute__((visibility("default"))) void scriptUnregister(void *m) {(void)m; cb=0; unregistered++;}
__attribute__((visibility("default"))) void scriptWait(uint32_t ms) {(void)ms; wait_calls++;}
__attribute__((visibility("default"))) unsigned fixture_registered(void) {return registered;}
__attribute__((visibility("default"))) unsigned fixture_unregistered(void) {return unregistered;}
__attribute__((visibility("default"))) unsigned fixture_wait_calls(void) {return wait_calls;}
__attribute__((visibility("default"))) void (*fixture_callback(void))(void) {return cb;}
