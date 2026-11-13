#ifndef RP_V13_DLADDR_IDENTITY_H
#define RP_V13_DLADDR_IDENTITY_H

#include "rp_v13_dyld_identity.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Alternative to dyld index enumeration: inspect the two images containing
 * CODE addresses supplied by a verified, pinned native runtime adapter.
 * The adapter MUST NOT take these pointers from a network packet, user input,
 * stale plugin handles or file offsets. Never execute through the anchors.
 * No GTA5 symbol is discovered or hooked by this source-only component.
 * Apple-only: returns 1 for exact v13 bundle/CPU/Mach-O UUID; zeroes out on
 * failure. No code-signature, device integrity or Online authorization proof.
 * Non-Apple platforms return 0 and zero out. */
int rp_v13_dladdr_collect_identity(const void *gta5_code_anchor,
                                   const void *compat_code_anchor,
                                   RP_V13_IdentityEvidence *out);

#ifdef __cplusplus
}
#endif
#endif
