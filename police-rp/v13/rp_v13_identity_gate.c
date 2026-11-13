#include "rp_v13_identity_gate.h"
#include <string.h>
/* Source: user-provided GTAV-v13(4).ipa, SHA256
 * cb1dd746c1fdc2faeb251aaaad9b7eedf4e46876b40a71b71d5b1180f4933361.
 * UUID bytes parsed from Mach-O LC_UUID load commands.
 * Do not use v12 offsets or treat this as evidence of actual dyld loading. */
static const uint8_t gta5_v13_uuid[16] = {
    0xdb,0xf9,0xce,0xca,0xc9,0x73,0x3a,0xfd,
    0xbf,0xa0,0x43,0x5f,0x45,0x3d,0xdf,0xcf
};
static const uint8_t compat_v13_uuid[16] = {
    0x8f,0xbc,0xb3,0xaa,0x62,0x5b,0x31,0x6c,
    0xa5,0xd2,0x64,0xda,0x46,0xc6,0xce,0xfc
};
RP_V13_IdentityResult rp_v13_identity_check(const RP_V13_IdentityEvidence *e) {
    if (!e) return RP_V13_IDENTITY_ERR_NULL;
    if (e->abi != RP_V13_IDENTITY_ABI) return RP_V13_IDENTITY_ERR_ABI;
    if (e->executable_uuid_verified_by_loader != 1u ||
        e->compat_uuid_verified_by_loader != 1u)
        return RP_V13_IDENTITY_ERR_ATTESTATION;
    if (memcmp(e->gta5_uuid,gta5_v13_uuid,16) != 0)
        return RP_V13_IDENTITY_ERR_EXECUTABLE;
    if (memcmp(e->gtacompat_uuid,compat_v13_uuid,16) != 0)
        return RP_V13_IDENTITY_ERR_COMPAT;
    return RP_V13_IDENTITY_MATCH;
}
const char *rp_v13_identity_result_name(RP_V13_IdentityResult result) {
    switch(result) {
      case RP_V13_IDENTITY_MATCH: return "identity-match-only";
      case RP_V13_IDENTITY_ERR_NULL: return "missing-evidence";
      case RP_V13_IDENTITY_ERR_ABI: return "wrong-gate-abi";
      case RP_V13_IDENTITY_ERR_ATTESTATION: return "unverified-loader-image";
      case RP_V13_IDENTITY_ERR_EXECUTABLE: return "wrong-gta5-uuid";
      case RP_V13_IDENTITY_ERR_COMPAT: return "wrong-gtacompat-uuid";
      default: return "unknown-identity-result";
    }
}
