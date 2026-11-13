/* Host-only fake dyld API; does not validate Apple SDK, RAGE or real loading. */
#include "rp_v13_dyld_identity.h"
#include <mach-o/dyld.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned checks;
#define CHECK(x) do { ++checks; assert((x)); } while (0)
static void u32(uint8_t *p,uint32_t n){memcpy(p,&n,4);}
static const uint8_t appid[16]={0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf};
static const uint8_t libid[16]={0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc};
static uint8_t app[56],lib[56];
static const char *paths[]={"/private/test/GTAV.app/GTA5","/private/test/GTAV.app/Frameworks/libgtacompat.dylib", "/private/test/GTAV.app/GTA5"};
static unsigned total=2;
uint32_t _dyld_image_count(void){return total;}
const struct mach_header *_dyld_get_image_header(uint32_t i) {
    if(i==0||i==2)return (const struct mach_header *)(const void *)app;
    if(i==1)return (const struct mach_header *)(const void *)lib;
    return NULL;
}
const char *_dyld_get_image_name(uint32_t i){return i<3?paths[i]:NULL;}
static void make_image(uint8_t p[56],uint32_t type,const uint8_t id[16]) {
    memset(p,0,56);u32(p,0xfeedfacfu);u32(p+4,0x0100000cu);
    u32(p+12,type);u32(p+16,1);u32(p+20,24);u32(p+32,0x1bu);u32(p+36,24);memcpy(p+40,id,16);
}
int main(void){
    RP_V13_IdentityEvidence proof={0};
    make_image(app,2,appid);make_image(lib,6,libid);
    CHECK(rp_v13_dyld_collect_identity(&proof)==1);
    CHECK(proof.executable_uuid_verified_by_loader==1);
    CHECK(proof.compat_uuid_verified_by_loader==1);
    CHECK(rp_v13_identity_check(&proof)==RP_V13_IDENTITY_MATCH);
    lib[40]^=1u;
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    CHECK(proof.executable_uuid_verified_by_loader==0);
    lib[40]^=1u;
    paths[1]="/other/GTAV.app/Frameworks/libgtacompat.dylib";
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    paths[1]="/private/test/GTAV.app/Frameworks/libgtacompat.dylib";
    total=3;
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    total=2;
    u32(app,0u);
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    u32(app,0xfeedfacfu);
    u32(app+20,1024*1024+1);
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    u32(app+20,24);
    total=0;
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    total=2049;
    CHECK(!rp_v13_dyld_collect_identity(&proof));
    total=2;
    CHECK(rp_v13_dyld_collect_identity(NULL)==0);
    CHECK(rp_v13_dyld_collect_identity(&proof)==1);
    printf("RP v13 fake Apple dyld provider host PASS: %u assertions (NOT Apple SDK/runtime)\n",checks);
    return 0;
}
