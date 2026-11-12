/* Police RP v1.5 — non-invasive iOS duty state diagnostic for EXACT GTA5 v12.
 * Does NOT hook, patch/write game memory, intercept packets, execute game natives,
 * activate Menyoo, or control any players. The 1 s polling callback is on the
 * dispatch main queue (it may not fire if the app does not service that queue).
 * This is instrumentation ONLY; the two fields are NOT proof of network identity.
 */
#include <dispatch/dispatch.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

#define PRP_JOB_ADDR ((uintptr_t)0x1027B1B2CULL)
#define PRP_SHIFT_ADDR ((uintptr_t)0x10355EE34ULL)
#define PRP_MAX_LINES 140
#define PRP_FILE "PoliceRPDuty-v15.txt"

static const uint8_t kUuid[16] = {
    0x6a,0x49,0x8e,0x32,0xe7,0x0c,0x33,0x4c,
    0xbc,0xa3,0xaf,0xfd,0x35,0xe8,0xd1,0x71
};
static dispatch_source_t gTimer;
static const volatile int32_t *gJob;
static const volatile uint8_t *gShift;
static unsigned gTicks, gLines;
static int32_t gLastJob=INT32_MIN;
static int gLastShift=-1;

static int prp_path(char *buffer, size_t cap) {
    const char *home=getenv("HOME");
    if (!home || !*home) return 0;
    int count=snprintf(buffer,cap,"%s/Documents/" PRP_FILE,home);
    return count>0 && (size_t)count<cap;
}
static void prp_write(const char *line, int reset) {
    if (gLines >= PRP_MAX_LINES && !reset) return;
    fprintf(stderr,"%s\n",line);
    char path[1024];
    if (!prp_path(path,sizeof(path))) return;
    FILE *f=fopen(path,reset?"w":"a");
    if (!f) return;
    if (fputs(line,f)>=0 && fputc('\n',f)!=EOF) {
        if (reset) gLines=1;
        else gLines++;
    }
    (void)fclose(f);
}

static int prp_expected_image(const struct mach_header_64 *header) {
    if (!header || header->magic!=MH_MAGIC_64 ||
        header->filetype!=MH_EXECUTE || header->cputype!=CPU_TYPE_ARM64 ||
        header->ncmds>512 || header->sizeofcmds>1024*1024) return 0;
    const uint8_t *cmds=(const uint8_t *)(header+1);
    size_t pos=0;
    int correct_uuid=0, valid_job=0, valid_shift=0;
    for (uint32_t n=0; n<header->ncmds; n++) {
        if (pos>header->sizeofcmds ||
            header->sizeofcmds-pos<sizeof(struct load_command)) return 0;
        const struct load_command *cmd=(const struct load_command *)(cmds+pos);
        if (cmd->cmdsize<sizeof(struct load_command) ||
            cmd->cmdsize>header->sizeofcmds-pos) return 0;
        if (cmd->cmd==LC_UUID && cmd->cmdsize>=sizeof(struct uuid_command)) {
            const struct uuid_command *uuid=(const struct uuid_command *)cmd;
            correct_uuid=(memcmp(uuid->uuid,kUuid,sizeof(kUuid))==0);
        }
        if (cmd->cmd==LC_SEGMENT_64 && cmd->cmdsize>=sizeof(struct segment_command_64)) {
            const struct segment_command_64 *seg=(const struct segment_command_64 *)cmd;
            if (strncmp(seg->segname,"__DATA",16)==0 && seg->vmsize>0) {
                if (seg->vmsize>=sizeof(int32_t) && PRP_JOB_ADDR>=seg->vmaddr &&
                    PRP_JOB_ADDR-seg->vmaddr<=seg->vmsize-sizeof(int32_t)) valid_job=1;
                if (PRP_SHIFT_ADDR>=seg->vmaddr &&
                    PRP_SHIFT_ADDR-seg->vmaddr<seg->vmsize) valid_shift=1;
            }
        }
        pos+=cmd->cmdsize;
    }
    return correct_uuid && valid_job && valid_shift;
}

static int prp_resolve(void) {
    uint32_t images=_dyld_image_count();
    for (uint32_t i=0; i<images; ++i) {
        const char *name=_dyld_get_image_name(i);
        const struct mach_header *raw=_dyld_get_image_header(i);
        if (!name || !raw) continue;
        const char *last=strrchr(name,'/');
        if (strcmp(last?last+1:name,"GTA5")!=0) continue;
        if (!prp_expected_image((const struct mach_header_64 *)raw)) return 0;
        intptr_t slide=_dyld_get_image_vmaddr_slide(i);
        gJob=(const volatile int32_t *)(PRP_JOB_ADDR + (uintptr_t)slide);
        gShift=(const volatile uint8_t *)(PRP_SHIFT_ADDR + (uintptr_t)slide);
        return 1;
    }
    return 0;
}

static void prp_sample(void *ignored) {
    (void)ignored;
    if (!gJob || !gShift) return;
    gTicks++;
    /* Arm64 naturally loads aligned 32-bit and 8-bit scalar values atomically.
       These reads do NOT establish a game-thread synchronization guarantee. */
    int32_t job=__atomic_load_n((const int32_t *)gJob,__ATOMIC_RELAXED);
    uint8_t shift=__atomic_load_n((const uint8_t *)gShift,__ATOMIC_RELAXED);
    if (job < -1 || job > 64 || shift > 1) {
        if (gTicks==1) prp_write("[PRP_DUTY_V15] invalid_snapshot=1 (no gameplay changes)",0);
        return;
    }
    if (job!=gLastJob || (int)shift!=gLastShift || gTicks%30==0) {
        const char *label="other";
        if (job==-1) label="none";
        if (job==0) label="cop_ls";
        if (job==1) label="cop_sandy";
        if (job==2) label="cop_paleto";
        int police_active=(job>=0 && job<=2 && shift==1);
        char line[220];
        snprintf(line,sizeof(line),
            "[PRP_DUTY_V15] tick=%u job=%d shift=%u police_active=%d label=%s",
            gTicks,job,shift,police_active,label);
        prp_write(line,0);
        gLastJob=job;
        gLastShift=shift;
    }
}

__attribute__((constructor))
static void prp_probe_start(void) {
    int verified=prp_resolve();
    char line[180];
    snprintf(line,sizeof(line),
        "[PRP_DIAG_V15] dylib_loaded=1 gta5_uuid_verified=%d hooks=0 "
        "network_events=0 police_gameplay=0 timer=main_queue_1s",verified);
    prp_write(line,1);
    if (!verified) return;
    /* Timer only observes state, does NOT interfere with GTA's scheduler. */
    gTimer=dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER,0,0,dispatch_get_main_queue());
    if (!gTimer) {
        prp_write("[PRP_DUTY_V15] timer_create_failed=1",0);
        return;
    }
    dispatch_source_set_event_handler_f(gTimer,prp_sample);
    dispatch_source_set_timer(gTimer,dispatch_time(DISPATCH_TIME_NOW,1*NSEC_PER_SEC),
                              NSEC_PER_SEC,100*NSEC_PER_MSEC);
    dispatch_resume(gTimer);
}
