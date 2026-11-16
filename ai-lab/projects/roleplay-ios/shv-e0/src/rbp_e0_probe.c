/*
 * GTA V iOS v13.3: E0-only ScriptHookV scheduler diagnostic.
 * No network, natives, gameplay edits, binary patches or runtime hooks.
 * Only this exact ScriptHookV UUID is allowed to register a callback.
 * iPhone results remain UNVERIFIED until collected from a signed test app.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/time.h>
#include <time.h>
#include <dlfcn.h>
#if defined(RBP_E0_TEST_DYLD)
#include "../tests/fake_dyld.h" /* host-only Mach-O/dyld boundary regression */
#elif defined(__APPLE__) && !defined(RBP_E0_HOST_TEST)
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/machine.h>
#endif

typedef void (*register_fn)(void *, void (*)(void));
typedef void (*unregister_fn)(void *);
typedef void (*wait_fn)(uint32_t);
static register_fn g_register;
static unregister_fn g_unregister;
static wait_fn g_wait;
static void *g_shv;
static void *g_module;
static int g_attempted;
static pthread_mutex_t g_log_mutex = PTHREAD_MUTEX_INITIALIZER;

static void e0_log(const char *format, ...) {
    char line[448];
    va_list args;
    va_start(args, format);
    int n = vsnprintf(line, sizeof line - 2, format, args);
    va_end(args);
    if (n < 0) return;
    size_t len = (size_t)n;
    if (len > sizeof line - 2) len = sizeof line - 2;
    if (!len || line[len - 1] != '\n') line[len++] = '\n';
    line[len] = 0;
    pthread_mutex_lock(&g_log_mutex);
    (void)fwrite(line, 1, len, stderr);
    const char *home = getenv("HOME");
    static const char suffix[] = "/Documents/RBPProbeE0.log";
    if (home && *home) {
        size_t hl = strlen(home);
        char path[1024];
        if (hl + sizeof suffix <= sizeof path) {
            memcpy(path, home, hl);
            memcpy(path + hl, suffix, sizeof suffix);
            int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
            if (fd >= 0) {
                for (size_t off = 0; off < len;) {
                    ssize_t wrote = write(fd, line + off, len - off);
                    if (wrote > 0) off += (size_t)wrote;
                    else if (wrote < 0 && errno == EINTR) continue;
                    else break;
                }
                (void)close(fd);
            }
        }
    }
    pthread_mutex_unlock(&g_log_mutex);
}

#if (defined(__APPLE__) && !defined(RBP_E0_HOST_TEST)) || defined(RBP_E0_TEST_DYLD)
static const uint8_t k_target_uuid[16] = {
    0xF7,0x68,0xB7,0xB5,0xAD,0x75,0x39,0xF4,
    0x83,0xD3,0x8E,0x49,0x23,0x43,0x25,0xB5
};
static int check_macho_uuid(const struct mach_header *header) {
    if (!header || header->magic != MH_MAGIC_64 ||
        header->cputype != CPU_TYPE_ARM64) return 0;
    const struct mach_header_64 *h = (const struct mach_header_64 *)header;
    if (h->ncmds == 0 || h->ncmds > 512 || h->sizeofcmds > (2u << 20)) return 0;
    const uint8_t *cur = (const uint8_t *)h + sizeof(*h);
    uint32_t offset = 0;
    for (uint32_t i = 0; i < h->ncmds; i++) {
        if (offset > h->sizeofcmds || h->sizeofcmds - offset < sizeof(struct load_command)) return 0;
        const struct load_command *lc = (const struct load_command *)cur;
        if (lc->cmdsize < sizeof(*lc) || (lc->cmdsize & 7u) ||
            lc->cmdsize > h->sizeofcmds - offset) return 0;
        if (lc->cmd == LC_UUID && lc->cmdsize >= sizeof(struct uuid_command)) {
            const struct uuid_command *uuid = (const struct uuid_command *)cur;
            return memcmp(uuid->uuid, k_target_uuid, sizeof k_target_uuid) == 0;
        }
        offset += lc->cmdsize;
        cur += lc->cmdsize;
    }
    return 0;
}

static void *find_existing_script_hook(void) {
    const char *chosen = NULL;
    const struct mach_header *chosen_header = NULL;
    unsigned matches = 0;
    uint32_t count = _dyld_image_count();
    for (uint32_t i = 0; i < count; i++) {
        const char *path = _dyld_get_image_name(i);
        if (!path) continue;
        const char *slash = strrchr(path, '/');
        const char *base = slash ? slash + 1 : path;
        if (strcmp(base, "ScriptHookV.dylib") != 0) continue;
        matches++;
        chosen = path;
        chosen_header = _dyld_get_image_header(i);
    }
    if (matches != 1) {
        e0_log("[RBP_E0] SHV_IMAGE_COUNT=%u FAIL_CLOSED", matches);
        return NULL;
    }
    if (!check_macho_uuid(chosen_header)) {
        e0_log("[RBP_E0] SCRIPT_HOOK_UUID_MATCH=0 FAIL_CLOSED");
        return NULL;
    }
    e0_log("[RBP_E0] SCRIPT_HOOK_UUID_MATCH=1");
    void *handle = dlopen(chosen, RTLD_NOW | RTLD_NOLOAD);
    if (!handle) e0_log("[RBP_E0] SHV_NOLOAD_RESOLUTION_FAILED");
    return handle;
}
#else
static void *find_existing_script_hook(void) {
    e0_log("[RBP_E0] SCRIPT_HOOK_UUID_CHECK=HOST_MOCK_ONLY");
    return dlopen(NULL, RTLD_NOW);
}
#endif

/* Actual ScriptHookV _scriptWait on this UUID can return immediately when the
 * current script context is NULL; do not spin forever in the game thread. */
#define E0_WAIT_MILLISECONDS 16u
#define E0_MAX_TICKS 120u
#define E0_FAST_RETURN_NS 500000ull
#define E0_MAX_CONSECUTIVE_FAST_RETURNS 4u
static uint64_t monotonic_ns(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 ||
        now.tv_sec < 0 || now.tv_nsec < 0 || now.tv_nsec >= 1000000000L)
        return 0;
    return (uint64_t)now.tv_sec * 1000000000ull + (uint64_t)now.tv_nsec;
}
static void script_entry(void) {
    e0_log("[RBP_E0] CALLBACK_ENTER");
    unsigned fast_returns = 0;
    for (uint32_t tick = 1; tick <= E0_MAX_TICKS; tick++) {
        if (tick == 1 || tick == 30 || tick == E0_MAX_TICKS)
            e0_log("[RBP_E0] SCRIPT_TICK=%u", tick);
        const uint64_t before = monotonic_ns();
        if (!before || !g_wait) {
            e0_log("[RBP_E0] SCRIPT_CLOCK_OR_WAIT_INVALID=1 FAIL_CLOSED");
            return;
        }
        g_wait(E0_WAIT_MILLISECONDS);
        const uint64_t after = monotonic_ns();
        if (!after || after < before) {
            e0_log("[RBP_E0] SCRIPT_CLOCK_OR_WAIT_INVALID=1 FAIL_CLOSED");
            return;
        }
        if (after - before < E0_FAST_RETURN_NS) {
            fast_returns++;
            if (fast_returns >= E0_MAX_CONSECUTIVE_FAST_RETURNS) {
                e0_log("[RBP_E0] SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED");
                return;
            }
        } else {
            fast_returns = 0;
        }
    }
    e0_log("[RBP_E0] SCRIPT_CALLBACK_COMPLETE=1");
}

__attribute__((visibility("default")))
int DllMain(void *module, unsigned reason, void *unused) {
    (void)unused;
    if (reason == 1) {
        if (g_attempted) return 1;
        struct timeval now = {0};
        (void)gettimeofday(&now, NULL);
        e0_log("[RBP_E0] RUN_BEGIN VERSION=1 pid=%ld timestamp_ms=%llu",
               (long)getpid(), (unsigned long long)now.tv_sec * 1000u +
               (unsigned long long)now.tv_usec / 1000u);
        e0_log("[RBP_E0] DLLMAIN_ATTACH");
        g_shv = find_existing_script_hook();
        if (!g_shv) return 0;
        g_register = (register_fn)dlsym(g_shv, "scriptRegister");
        g_unregister = (unregister_fn)dlsym(g_shv, "scriptUnregister");
        g_wait = (wait_fn)dlsym(g_shv, "scriptWait");
        if (!g_register || !g_unregister || !g_wait) {
            e0_log("[RBP_E0] REQUIRED_SYMBOL_MISSING FAIL_CLOSED");
            (void)dlclose(g_shv);
            g_shv = NULL;
            return 0;
        }
        g_module = module;
        g_register(module, script_entry);
        g_attempted = 1;
        e0_log("[RBP_E0] SCRIPT_REGISTER_ATTEMPTED=1 (void API)");
    } else if (reason == 0 && g_attempted) {
        e0_log("[RBP_E0] DLLMAIN_DETACH");
        g_unregister(g_module);
        g_attempted = 0;
        if (g_shv) (void)dlclose(g_shv);
        g_shv = NULL;
        g_register = NULL;
        g_unregister = NULL;
        g_wait = NULL;
    }
    return 1;
}
