#include "rp_v13_identity_gate.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RP_V13_IdentityEvidence good(void) {
    RP_V13_IdentityEvidence e={0};
    static const uint8_t app[16]={
        0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,
        0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf};
    static const uint8_t compat[16]={
        0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,
        0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc};
    e.abi=RP_V13_IDENTITY_ABI;
    memcpy(e.gta5_uuid,app,16);
    memcpy(e.gtacompat_uuid,compat,16);
    e.executable_uuid_verified_by_loader=1;
    e.compat_uuid_verified_by_loader=1;
    return e;
}
int main(void){
    RP_V13_IdentityEvidence e=good();
    assert(rp_v13_identity_check(NULL)==RP_V13_IDENTITY_ERR_NULL);
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_MATCH);
    assert(strcmp(rp_v13_identity_result_name(RP_V13_IDENTITY_MATCH),
                  "identity-match-only")==0);
    e.abi=0;
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_ERR_ABI);
    e=good();e.executable_uuid_verified_by_loader=0;
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_ERR_ATTESTATION);
    e=good();e.compat_uuid_verified_by_loader=0;
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_ERR_ATTESTATION);
    e=good();e.gta5_uuid[0]^=1;
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_ERR_EXECUTABLE);
    e=good();e.gtacompat_uuid[15]^=1;
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_ERR_COMPAT);
    /* Historical v12 GTA5 UUID must be rejected by v13 gate. */
    e=good();
    static const uint8_t old[16]={
        0x6a,0x49,0x8e,0x32,0xe7,0x0c,0x33,0x4c,
        0xbc,0xa3,0xaf,0xfd,0x35,0xe8,0xd1,0x71};
    memcpy(e.gta5_uuid,old,16);
    assert(rp_v13_identity_check(&e)==RP_V13_IDENTITY_ERR_EXECUTABLE);
    puts("RP v13 identity gate C host regression PASS; no device tested");
    return 0;
}
