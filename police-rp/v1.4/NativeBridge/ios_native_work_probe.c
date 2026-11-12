/* GTA V iOS v12 native work probe.
 * Compiles ONLY with the Apple iOS SDK. Never writes to game memory.
 * It must NOT be used as a session verifier; job and shift alone are insufficient.
 */
#if !defined(__APPLE__)
#error "Requires Apple SDK / Mach-O dyld"
#endif
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <stdint.h>
#include <string.h>

static const uint8_t kExpectedUUID[16] = {
    0x6a,0x49,0x8e,0x32,0xe7,0x0c,0x33,0x4c,
    0xbc,0xa3,0xaf,0xfd,0x35,0xe8,0xd1,0x71
};
#define PR_GTA5_JOB_VMADDR ((uintptr_t)0x1027b1b2cULL)
#define PR_GTA5_ONSHIFT_VMADDR ((uintptr_t)0x10355ee34ULL)

static int expected_uuid(const struct mach_header_64 *mh) {
    if (!mh || mh->magic!=MH_MAGIC_64 || mh->cputype!=CPU_TYPE_ARM64 ||
        mh->filetype!=MH_EXECUTE || mh->ncmds>2048 || mh->sizeofcmds>1048576)
        return 0;
    const uint8_t *cursor=(const uint8_t*)(mh+1);
    size_t consumed=0;
    for (uint32_t i=0;i<mh->ncmds;i++) {
        if (consumed+sizeof(struct load_command)>mh->sizeofcmds) return 0;
        const struct load_command *cmd=(const struct load_command*)(cursor+consumed);
        if (cmd->cmdsize<sizeof(struct load_command) ||
            consumed+cmd->cmdsize>mh->sizeofcmds) return 0;
        if (cmd->cmd==LC_UUID && cmd->cmdsize>=sizeof(struct uuid_command)) {
            const struct uuid_command *u=(const struct uuid_command*)cmd;
            return memcmp(u->uuid,kExpectedUUID,16)==0;
        }
        consumed+=cmd->cmdsize;
    }
    return 0;
}

/* Outputs are valid only while GTA5 v12 exact UUID is mapped.
 * The caller must invoke this on the game thread, and MUST still use an
 * independently verified session/player identity from the engine. */
int pr_ios_native_work_snapshot(int32_t *job, uint8_t *shift) {
    if (!job || !shift) return 0;
    *job=-1; *shift=0;
    uint32_t image_count=_dyld_image_count();
    for (uint32_t i=0;i<image_count;i++) {
        const struct mach_header *h=_dyld_get_image_header(i);
        const char *name=_dyld_get_image_name(i);
        if (!h || !name) continue;
        const char *base=strrchr(name,'/');
        base=base?base+1:name;
        if (strcmp(base,"GTA5")!=0) continue;
        const struct mach_header_64 *mh=(const struct mach_header_64*)h;
        if (!expected_uuid(mh)) return 0;
        intptr_t slide=_dyld_get_image_vmaddr_slide(i);
        uintptr_t j=(uintptr_t)((intptr_t)PR_GTA5_JOB_VMADDR+slide);
        uintptr_t s=(uintptr_t)((intptr_t)PR_GTA5_ONSHIFT_VMADDR+slide);
        int32_t value=*(volatile const int32_t*)j;
        uint8_t state=*(volatile const uint8_t*)s;
        if (value < -1 || value > 64 || state > 1) return 0;
        *job=value;
        *shift=state;
        return 1;
    }
    return 0;
}
