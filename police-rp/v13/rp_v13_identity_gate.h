#ifndef RP_V13_IDENTITY_GATE_H
#define RP_V13_IDENTITY_GATE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define RP_V13_IDENTITY_ABI 1u
#define RP_V13_UUID_BYTES 16u
typedef struct {
    uint32_t abi;
    uint8_t gta5_uuid[RP_V13_UUID_BYTES];
    uint8_t gtacompat_uuid[RP_V13_UUID_BYTES];
    uint8_t executable_uuid_verified_by_loader;
    uint8_t compat_uuid_verified_by_loader;
} RP_V13_IdentityEvidence;
typedef enum {
    RP_V13_IDENTITY_MATCH = 0,
    RP_V13_IDENTITY_ERR_NULL = -1,
    RP_V13_IDENTITY_ERR_ABI = -2,
    RP_V13_IDENTITY_ERR_ATTESTATION = -3,
    RP_V13_IDENTITY_ERR_EXECUTABLE = -4,
    RP_V13_IDENTITY_ERR_COMPAT = -5
} RP_V13_IdentityResult;
/* Metadata-only identity check against EXACT v13 LC_UUID values.
 * The evidence must come from a verified loader API; not a packet or config.
 * MATCH is NOT gameplay authorization, a RAGE callback, or code-signing proof.
 * The future RP integration must fail open on mismatch. */
RP_V13_IdentityResult rp_v13_identity_check(const RP_V13_IdentityEvidence *e);
const char *rp_v13_identity_result_name(RP_V13_IdentityResult result);
#ifdef __cplusplus
}
#endif
#endif
