#include "rp_v13_dyld_identity.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned assertions;
#define CHECK(x) do { ++assertions; assert((x)); } while (0)
static void u32(uint8_t *p, uint32_t v) { memcpy(p, &v, sizeof(v)); }
static void make_image(uint8_t dst[56], uint32_t filetype, const uint8_t uuid[16]) {
    memset(dst, 0, 56);
    u32(dst, 0xfeedfacfu);
    u32(dst+4, 0x0100000cu);
    u32(dst+12, filetype);
    u32(dst+16, 1);
    u32(dst+20, 24);
    u32(dst+32, 0x1bu);
    u32(dst+36, 24);
    memcpy(dst+40, uuid, 16);
}
static const uint8_t appid[16]={0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf};
static const uint8_t libid[16]={0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc};
static void parser(void) {
    uint8_t app[56], lib[56], found[16];
    make_image(app,2,appid); make_image(lib,6,libid);
    CHECK(rp_v13_parse_macho_uuid(app,56,2,found)==1);
    CHECK(memcmp(found,appid,16)==0);
    CHECK(rp_v13_parse_macho_uuid(lib,56,6,found)==1);
    CHECK(memcmp(found,libid,16)==0);
    CHECK(!rp_v13_parse_macho_uuid(app,56,6,found));
    CHECK(!rp_v13_parse_macho_uuid(app,55,2,found));
    CHECK(!rp_v13_parse_macho_uuid(NULL,56,2,found));
    CHECK(!rp_v13_parse_macho_uuid(app,56,2,NULL));
    CHECK(!rp_v13_parse_macho_uuid(app,56,9,found));
    CHECK(!rp_v13_parse_macho_uuid(app,31,2,found));
    uint8_t b[56];
    memcpy(b,app,56);u32(b,0);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+4,7);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+16,0);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+16,8193);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+20,1024*1024+1);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+20,16);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+20,32);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+36,0);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+36,23);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+36,32);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+32,0x19);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    memcpy(b,app,56);u32(b+16,2);CHECK(!rp_v13_parse_macho_uuid(b,56,2,found));
    CHECK(memcmp(found,(uint8_t[16]){0},16)==0);
    uint8_t twice[80];
    memcpy(twice,app,56);memcpy(twice+56,app+32,24);
    u32(twice+16,2);u32(twice+20,48);
    CHECK(!rp_v13_parse_macho_uuid(twice,80,2,found));
    CHECK(memcmp(found,(uint8_t[16]){0},16)==0);
}
static void candidate_pairs(void) {
    uint8_t app[56],lib[56];
    make_image(app,2,appid);make_image(lib,6,libid);
    RP_V13_LoadedImageView v[]={{"/private/var/app/GTAV.app/GTA5",app,56},{"/private/var/app/GTAV.app/Frameworks/libgtacompat.dylib",lib,56}};
    RP_V13_IdentityEvidence out;
    CHECK(rp_v13_collect_image_candidates(v,2,&out)==1);
    CHECK(out.abi==RP_V13_IDENTITY_ABI);
    CHECK(memcmp(out.gta5_uuid,appid,16)==0);
    CHECK(memcmp(out.gtacompat_uuid,libid,16)==0);
    CHECK(out.executable_uuid_verified_by_loader==0);
    CHECK(out.compat_uuid_verified_by_loader==0);
    CHECK(rp_v13_identity_check(&out)==RP_V13_IDENTITY_ERR_ATTESTATION);
    CHECK(!rp_v13_collect_image_candidates(NULL,2,&out));
    CHECK(!rp_v13_collect_image_candidates(v,0,&out));
    CHECK(!rp_v13_collect_image_candidates(v,2049,&out));
    CHECK(!rp_v13_collect_image_candidates(v,2,NULL));
    RP_V13_LoadedImageView dup[]={v[0],v[0],v[1]};
    CHECK(!rp_v13_collect_image_candidates(dup,3,&out));
    RP_V13_LoadedImageView wrong[]={v[0],v[1]};
    wrong[1].dyld_path="/private/other/GTAV.app/Frameworks/libgtacompat.dylib";
    CHECK(!rp_v13_collect_image_candidates(wrong,2,&out));
    wrong[1]=v[1];wrong[1].dyld_path="/private/var/app/GTAV.app/Frameworks/libwrong.dylib";
    CHECK(!rp_v13_collect_image_candidates(wrong,2,&out));
    wrong[1]=v[1];wrong[0].dyld_path="/private/var/app/GTAV.app/GTA5wrong";
    CHECK(!rp_v13_collect_image_candidates(wrong,2,&out));
    wrong[0]=v[0];wrong[1]=v[1];wrong[1].macho_header=app;
    CHECK(!rp_v13_collect_image_candidates(wrong,2,&out));
    CHECK(out.abi==0);
    CHECK(out.executable_uuid_verified_by_loader==0);
}
static void mutation_fuzz(void) {
    uint8_t original[56],buf[56],found[16];
    make_image(original,2,appid);
    uint32_t x=0x10f1a7b3u;
    unsigned rejects=0;
    for (unsigned i=0;i<12000;i++) {
        memcpy(buf,original,56);
        x^=x<<13;x^=x>>17;x^=x<<5;
        unsigned at=x%40u; /* mutate structural region, not UUID */
        buf[at]^=(uint8_t)((x>>8)|1u);
        if (!rp_v13_parse_macho_uuid(buf,56,2,found)) ++rejects;
    }
    CHECK(rejects>7000u);
}
int main(void) {
    parser();candidate_pairs();mutation_fuzz();
#ifndef __APPLE__
    RP_V13_IdentityEvidence out={0};
    CHECK(!rp_v13_dyld_collect_identity(&out));
    CHECK(out.executable_uuid_verified_by_loader==0);
#endif
    printf("RP v13 dyld identity host PASS: %u assertions; 12000 bounded mutations (NOT iPhone/dyld runtime)\n", assertions);
    return 0;
}
