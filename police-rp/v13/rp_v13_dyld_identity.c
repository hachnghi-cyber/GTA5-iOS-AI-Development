#include "rp_v13_dyld_identity.h"
#include <string.h>

#define RP_V13_MH_MAGIC_64 0xfeedfacfu
#define RP_V13_CPU_TYPE_ARM64 0x0100000cu
#define RP_V13_LC_UUID 0x1bu
#define RP_V13_MAX_LOADCMDS 8192u
#define RP_V13_MAX_COMMAND_BYTES (1024u * 1024u)
#define RP_V13_MAX_IMAGES 2048u
#define RP_V13_MACH_HEADER_64_SIZE 32u

static uint32_t get_u32(const uint8_t *p) {
    uint32_t value;
    memcpy(&value, p, sizeof(value));
    return value;
}

int rp_v13_parse_macho_uuid(const uint8_t *header, size_t header_bytes,
                             uint32_t expected_filetype, uint8_t uuid_out[16]) {
    if (!uuid_out) return 0;
    memset(uuid_out, 0, 16);
    if (!header || header_bytes < RP_V13_MACH_HEADER_64_SIZE ||
        (expected_filetype != 2u && expected_filetype != 6u)) return 0;
    if (get_u32(header) != RP_V13_MH_MAGIC_64 ||
        get_u32(header+4) != RP_V13_CPU_TYPE_ARM64 ||
        get_u32(header+12) != expected_filetype) return 0;
    const uint32_t ncmds = get_u32(header+16);
    const uint32_t sizeofcmds = get_u32(header+20);
    if (!ncmds || ncmds > RP_V13_MAX_LOADCMDS ||
        !sizeofcmds || sizeofcmds > RP_V13_MAX_COMMAND_BYTES ||
        sizeofcmds > header_bytes - RP_V13_MACH_HEADER_64_SIZE) return 0;
    const size_t end = RP_V13_MACH_HEADER_64_SIZE + (size_t)sizeofcmds;
    size_t pos = RP_V13_MACH_HEADER_64_SIZE;
    int found_uuid = 0;
    uint8_t selected[16] = {0};
    for (uint32_t i = 0; i < ncmds; ++i) {
        if (end - pos < 8u) return 0;
        const uint32_t cmd = get_u32(header+pos);
        const uint32_t cmdsize = get_u32(header+pos+4);
        if (cmdsize < 8u || (cmdsize & 7u) != 0u ||
            cmdsize > end - pos) return 0;
        if (cmd == RP_V13_LC_UUID) {
            if (cmdsize != 24u || found_uuid) return 0;
            memcpy(selected, header+pos+8, 16);
            found_uuid = 1;
        }
        pos += cmdsize;
    }
    if (!found_uuid || pos != end) return 0;
    memcpy(uuid_out, selected, 16);
    return 1;
}

static size_t path_prefix_len(const char *path, const char *suffix) {
    if (!path || !suffix) return (size_t)-1;
    const size_t full = strlen(path), tail = strlen(suffix);
    if (full <= tail || memcmp(path + full - tail, suffix, tail) != 0)
        return (size_t)-1;
    return full - tail;
}

int rp_v13_collect_image_candidates(const RP_V13_LoadedImageView *views,
                                     size_t count, RP_V13_IdentityEvidence *out) {
    static const char main_suffix[] = "/GTAV.app/GTA5";
    static const char compat_suffix[] = "/GTAV.app/Frameworks/libgtacompat.dylib";
    if (!out) return 0;
    memset(out, 0, sizeof(*out));
    if (!views || !count || count > RP_V13_MAX_IMAGES) return 0;
    size_t main_index = count, compat_index = count;
    size_t main_prefix = 0u, compat_prefix = 0u;
    for (size_t i = 0; i < count; ++i) {
        const size_t a = path_prefix_len(views[i].dyld_path, main_suffix);
        const size_t b = path_prefix_len(views[i].dyld_path, compat_suffix);
        if (a != (size_t)-1) {
            if (main_index != count) return 0;
            main_index = i; main_prefix = a;
        }
        if (b != (size_t)-1) {
            if (compat_index != count) return 0;
            compat_index = i; compat_prefix = b;
        }
    }
    if (main_index == count || compat_index == count ||
        main_prefix != compat_prefix ||
        memcmp(views[main_index].dyld_path,
               views[compat_index].dyld_path, main_prefix) != 0) return 0;
    uint8_t app[16], compat[16];
    if (!rp_v13_parse_macho_uuid(views[main_index].macho_header,
                                 views[main_index].mapped_header_bytes, 2u, app) ||
        !rp_v13_parse_macho_uuid(views[compat_index].macho_header,
                                 views[compat_index].mapped_header_bytes, 6u, compat)) return 0;
    out->abi = RP_V13_IDENTITY_ABI;
    memcpy(out->gta5_uuid, app, 16);
    memcpy(out->gtacompat_uuid, compat, 16);
    /* The portable/test path deliberately does not assert dyld provenance. */
    return 1;
}

#if defined(__APPLE__)
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

int rp_v13_dyld_collect_identity(RP_V13_IdentityEvidence *out) {
    if (!out) return 0;
    memset(out, 0, sizeof(*out));
    /* A dyld image enumeration is not an atomic, thread-safe snapshot.
     * Use this at a controlled lifecycle point, not from network callbacks. */
    const uint32_t count = _dyld_image_count();
    if (!count || count > RP_V13_MAX_IMAGES) return 0;
    RP_V13_LoadedImageView candidates[2] = {{0}};
    size_t selected = 0u;
    for (uint32_t i = 0; i < count; ++i) {
        const char *name = _dyld_get_image_name(i);
        if (!name) continue;
        if (path_prefix_len(name, "/GTAV.app/GTA5") == (size_t)-1 &&
            path_prefix_len(name, "/GTAV.app/Frameworks/libgtacompat.dylib") == (size_t)-1)
            continue;
        /* Reject ambiguous duplicate names or a missing mapped image. */
        if (selected == 2u) return 0;
        const struct mach_header *header = _dyld_get_image_header(i);
        if (!header || header->magic != MH_MAGIC_64) return 0;
        const struct mach_header_64 *h64 = (const struct mach_header_64 *)(const void *)header;
        if (h64->sizeofcmds > RP_V13_MAX_COMMAND_BYTES) return 0;
        candidates[selected].dyld_path = name;
        candidates[selected].macho_header = (const uint8_t *)(const void *)header;
        candidates[selected].mapped_header_bytes = sizeof(*h64) + (size_t)h64->sizeofcmds;
        ++selected;
    }
    RP_V13_IdentityEvidence untrusted = {0};
    if (!rp_v13_collect_image_candidates(candidates, selected, &untrusted)) return 0;
    untrusted.executable_uuid_verified_by_loader = 1u;
    untrusted.compat_uuid_verified_by_loader = 1u;
    if (rp_v13_identity_check(&untrusted) != RP_V13_IDENTITY_MATCH) return 0;
    *out = untrusted;
    return 1;
}
#else
int rp_v13_dyld_collect_identity(RP_V13_IdentityEvidence *out) {
    if (out) memset(out, 0, sizeof(*out));
    return 0;
}
#endif
