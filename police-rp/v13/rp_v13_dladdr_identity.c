#include "rp_v13_dladdr_identity.h"
#include <string.h>

#define RP_V13_ANCHOR_MH_MAGIC_64 0xfeedfacfu
#define RP_V13_ANCHOR_MAX_COMMAND_BYTES (1024u * 1024u)

#if defined(__APPLE__)
#include <dlfcn.h>

/* The name/header returned by dladdr belongs to dyld. Code anchors must stay
 * mapped for the whole query; a concurrently unloaded module is unsupported.
 * Unlike _dyld_image_count(), we do not iterate a mutable image index list. */
static int anchor_matches_image(const char *path, const char *expected_suffix) {
    if (!path || !expected_suffix) return 0;
    const size_t length = strlen(path);
    const size_t suffix_length = strlen(expected_suffix);
    return length > suffix_length &&
        memcmp(path + length - suffix_length, expected_suffix, suffix_length) == 0;
}

static int view_for_anchor(const void *anchor, RP_V13_LoadedImageView *view) {
    Dl_info info;
    if (!anchor || !view) return 0;
    memset(&info, 0, sizeof(info));
    if (dladdr(anchor, &info) == 0 || !info.dli_fname || !info.dli_fbase)
        return 0;
    const uint8_t *hdr = (const uint8_t *)info.dli_fbase;
    uint32_t magic = 0u;
    uint32_t sizeofcmds = 0u;
    memcpy(&magic, hdr, sizeof(magic));
    if (magic != RP_V13_ANCHOR_MH_MAGIC_64) return 0;
    memcpy(&sizeofcmds, hdr + 20u, sizeof(sizeofcmds));
    if (!sizeofcmds || sizeofcmds > RP_V13_ANCHOR_MAX_COMMAND_BYTES)
        return 0;
    view->dyld_path = info.dli_fname;
    view->macho_header = hdr;
    view->mapped_header_bytes = 32u + (size_t)sizeofcmds;
    return 1;
}

int rp_v13_dladdr_collect_identity(const void *gta5_code_anchor,
                                   const void *compat_code_anchor,
                                   RP_V13_IdentityEvidence *out) {
    if (!out) return 0;
    memset(out, 0, sizeof(*out));
    if (!gta5_code_anchor || !compat_code_anchor ||
        gta5_code_anchor == compat_code_anchor) return 0;
    RP_V13_LoadedImageView views[2] = {{0}};
    if (!view_for_anchor(gta5_code_anchor, &views[0]) ||
        !view_for_anchor(compat_code_anchor, &views[1])) return 0;
    /* Do not silently swap the caller's independently sourced anchors.
     * A reversed pair must not be re-labelled by the order-insensitive
     * portable candidate collector. */
    if (!anchor_matches_image(views[0].dyld_path, "/GTAV.app/GTA5") ||
        !anchor_matches_image(views[1].dyld_path,
                              "/GTAV.app/Frameworks/libgtacompat.dylib"))
        return 0;
    RP_V13_IdentityEvidence candidate = {0};
    if (!rp_v13_collect_image_candidates(views, 2u, &candidate)) return 0;
    candidate.executable_uuid_verified_by_loader = 1u;
    candidate.compat_uuid_verified_by_loader = 1u;
    if (rp_v13_identity_check(&candidate) != RP_V13_IDENTITY_MATCH) return 0;
    *out = candidate;
    return 1;
}
#else
int rp_v13_dladdr_collect_identity(const void *gta5_code_anchor,
                                   const void *compat_code_anchor,
                                   RP_V13_IdentityEvidence *out) {
    (void)gta5_code_anchor;
    (void)compat_code_anchor;
    if (out) memset(out, 0, sizeof(*out));
    return 0;
}
#endif
