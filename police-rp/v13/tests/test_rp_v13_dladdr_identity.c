/* Stubbed Apple dladdr + dyld APIs, host-only regression. */
#include "rp_v13_dladdr_identity.h"
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned assertions = 0u;
#define CHECK(x) do { ++assertions; assert(x); } while(0)
static int gta_code_anchor;
static int compat_code_anchor;
static int other_code_anchor;
static uint8_t app[56], compat[56];
static unsigned dladdr_calls = 0, dyld_list_calls = 0;
static const char *app_path = "/private/test/GTAV.app/GTA5";
static const char *compat_path = "/private/test/GTAV.app/Frameworks/libgtacompat.dylib";
static int app_mapped = 1, compat_mapped = 1;
static const uint8_t appid[16] = {0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,
                                  0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf};
static const uint8_t compatid[16] = {0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,
                                     0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc};
static void write_u32(uint8_t *p, uint32_t value) { memcpy(p, &value, 4u); }
static void make_image(uint8_t buf[56], uint32_t filetype, const uint8_t uuid[16]) {
    memset(buf, 0, 56u);
    write_u32(buf, 0xfeedfacfu);
    write_u32(buf+4, 0x0100000cu);
    write_u32(buf+12, filetype);
    write_u32(buf+16, 1u);
    write_u32(buf+20, 24u);
    buf[32] = 0x1bu;
    write_u32(buf+36, 24u);
    memcpy(buf+40, uuid, 16u);
}
int dladdr(const void *anchor, Dl_info *info) {
    ++dladdr_calls;
    if (!info) return 0;
    memset(info, 0, sizeof(*info));
    if (anchor == &gta_code_anchor && app_mapped) {
        info->dli_fname = app_path;
        info->dli_fbase = app;
        return 1;
    }
    if (anchor == &compat_code_anchor && compat_mapped) {
        info->dli_fname = compat_path;
        info->dli_fbase = compat;
        return 1;
    }
    return 0;
}
/* Legacy image index API is intentionally never called by this provider. */
uint32_t _dyld_image_count(void) { ++dyld_list_calls; return 0; }
const struct mach_header *_dyld_get_image_header(uint32_t i) {
    ++dyld_list_calls; (void)i; return NULL;
}
const char *_dyld_get_image_name(uint32_t i) {
    ++dyld_list_calls; (void)i; return NULL;
}
static void fresh_images(void) {
    make_image(app, 2u, appid);
    make_image(compat, 6u, compatid);
    app_path="/private/test/GTAV.app/GTA5";
    compat_path="/private/test/GTAV.app/Frameworks/libgtacompat.dylib";
    app_mapped=compat_mapped=1;
}
static void checks_for_invalid_inputs(void) {
    RP_V13_IdentityEvidence out = {0};
    fresh_images();
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, NULL));
    CHECK(!rp_v13_dladdr_collect_identity(NULL, &compat_code_anchor, &out));
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, NULL, &out));
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &gta_code_anchor, &out));
    CHECK(out.executable_uuid_verified_by_loader == 0);
    CHECK(!rp_v13_dladdr_collect_identity(&other_code_anchor, &compat_code_anchor, &out));
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &other_code_anchor, &out));
    CHECK(out.compat_uuid_verified_by_loader == 0);
}
static void checks_for_identity(void) {
    RP_V13_IdentityEvidence out = {0};
    fresh_images();
    CHECK(rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    CHECK(out.abi == RP_V13_IDENTITY_ABI);
    CHECK(out.executable_uuid_verified_by_loader == 1u);
    CHECK(out.compat_uuid_verified_by_loader == 1u);
    CHECK(rp_v13_identity_check(&out) == RP_V13_IDENTITY_MATCH);
    CHECK(dladdr_calls > 0u);
    CHECK(dyld_list_calls == 0u);
    CHECK(!rp_v13_dladdr_collect_identity(&compat_code_anchor, &gta_code_anchor, &out));
    CHECK(out.abi == 0u);
    fresh_images();
    app_mapped=0;
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    compat_mapped=0; app_mapped=1;
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    compat_path="/private/other/GTAV.app/Frameworks/libgtacompat.dylib";
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    compat_path="/private/test/GTAV.app/GTA5";
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
}
static void checks_for_macho_corruption(void) {
    RP_V13_IdentityEvidence out = {0};
    fresh_images();
    app[40] ^= 1u;
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    CHECK(out.executable_uuid_verified_by_loader == 0u);
    fresh_images();
    compat[40] ^= 1u;
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    write_u32(compat+12, 2u);
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    write_u32(app+4, 7u);
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    write_u32(app, 0u);
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    write_u32(compat+20, 0u);
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    write_u32(compat+20, 1024u*1024u+1u);
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    fresh_images();
    write_u32(compat+36, 0u);
    CHECK(!rp_v13_dladdr_collect_identity(&gta_code_anchor, &compat_code_anchor, &out));
    CHECK(out.abi == 0u);
    CHECK(dyld_list_calls == 0u);
}
int main(void) {
    checks_for_invalid_inputs();
    checks_for_identity();
    checks_for_macho_corruption();
    printf("RP v13 dladdr anchored Apple API shim PASS: %u assertions (host-only; NOT Apple SDK)\n", assertions);
    return 0;
}
