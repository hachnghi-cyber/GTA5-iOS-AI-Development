#ifndef RP_V13_FAKE_DLFCN_H
#define RP_V13_FAKE_DLFCN_H
/* Host-only fake Apple dladdr declaration; NOT an Apple SDK header. */
typedef struct {
    const char *dli_fname;
    void *dli_fbase;
    const char *dli_sname;
    void *dli_saddr;
} Dl_info;
int dladdr(const void *addr, Dl_info *info);
#endif
