/* Police RP v12 v1.4 diagnostic-only dylib.
 * This file DOES NOT hook game execution, write game memory, send packets,
 * read personal data or enable Menyoo/ScriptHook in Online.
 * Built as an iOS arm64 dylib by Xcode/macOS GitHub Actions.
 */
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const uint8_t expected_uuid[16] = {
    0x6a,0x49,0x8e,0x32,0xe7,0x0c,0x33,0x4c,
    0xbc,0xa3,0xaf,0xfd,0x35,0xe8,0xd1,0x71
};

static int match_gta5_uuid(const struct mach_header_64 *mh) {
    if (!mh || mh->magic != MH_MAGIC_64 || mh->filetype != MH_EXECUTE ||
        mh->cputype != CPU_TYPE_ARM64 || mh->ncmds > 512 ||
        mh->sizeofcmds > 1024 * 1024) return 0;
    size_t pos = 0;
    const uint8_t *base = (const uint8_t *)(mh + 1);
    for (uint32_t i=0; i<mh->ncmds; i++) {
        if (pos > mh->sizeofcmds || mh->sizeofcmds - pos < sizeof(struct load_command))
            return 0;
        const struct load_command *cmd=(const struct load_command *)(base+pos);
        if (cmd->cmdsize<sizeof(struct load_command) || cmd->cmdsize>mh->sizeofcmds-pos)
            return 0;
        if (cmd->cmd==LC_UUID && cmd->cmdsize >= sizeof(struct uuid_command)) {
            const struct uuid_command *u=(const struct uuid_command *)cmd;
            return memcmp(u->uuid,expected_uuid,sizeof(expected_uuid))==0;
        }
        pos += cmd->cmdsize;
    }
    return 0;
}

__attribute__((visibility("default")))
int PRPProbeVerifyGTA12(void) {
    uint32_t n=_dyld_image_count();
    for (uint32_t i=0; i<n; i++) {
        const char *name=_dyld_get_image_name(i);
        const struct mach_header *h=_dyld_get_image_header(i);
        if (!name || !h) continue;
        const char *basename=strrchr(name,'/');
        basename=basename?basename+1:name;
        if (strcmp(basename,"GTA5")!=0) continue;
        return match_gta5_uuid((const struct mach_header_64 *)h);
    }
    return 0;
}

/* The v12 app declares UIFileSharingEnabled, so its Documents directory
 * can usually be inspected from iOS Files. Writing this one small marker
 * is diagnostic-only; it never touches gameplay, NPCs, or networking.
 * This file intentionally contains no local account identifiers or IPs.
 */
static int PRPWriteDocumentsMarker(const char *message) {
    const char *home=getenv("HOME");
    if (!home || !home[0]) return 0;
    char path[1024];
    int n=snprintf(path,sizeof(path),"%s/Documents/PoliceRPProbe-v14.txt",home);
    if (n<=0 || (size_t)n>=sizeof(path)) return 0;
    FILE *f=fopen(path,"w");
    if (!f) return 0;
    int ok=(fputs(message,f)>=0 && fputc('\n',f)!=EOF);
    if (fclose(f)!=0) ok=0;
    return ok;
}

__attribute__((constructor))
static void PRPProbeOnLoad(void) {
    int correct=PRPProbeVerifyGTA12();
    char message[192];
    int n=snprintf(message,sizeof(message),
        "[PRP_DIAG_V14] dylib_loaded=1 gta5_uuid_verified=%d hooks=0 "
        "network_events=0 police_gameplay=0",correct);
    if (n<=0 || (size_t)n>=sizeof(message)) return;
    fprintf(stderr,"%s\n",message);
    fflush(stderr);
    (void)PRPWriteDocumentsMarker(message);
}
