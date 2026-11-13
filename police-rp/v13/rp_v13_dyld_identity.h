#ifndef RP_V13_DYLD_IDENTITY_H
#define RP_V13_DYLD_IDENTITY_H

#include <stddef.h>
#include <stdint.h>
#include "rp_v13_identity_gate.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Read-only candidate view; host fixtures are NOT attested runtime images. */
typedef struct {
    const char *dyld_path;
    const uint8_t *macho_header;
    size_t mapped_header_bytes;
} RP_V13_LoadedImageView;

/* Parse a bounded, native-endian, thin ARM64 MH_MAGIC_64 image header.
 * expected_filetype: 2 (MH_EXECUTE), 6 (MH_DYLIB). All failure paths zero out.
 * This does not verify code signing or prove the image was loaded by dyld. */
int rp_v13_parse_macho_uuid(const uint8_t *header, size_t header_bytes,
                             uint32_t expected_filetype, uint8_t uuid_out[16]);

/* Portable, testable candidate enumeration. The returned UUIDs are *always*
 * untrusted metadata (verified_by_loader flags == 0), even if they match.
 * Only the Apple-specific dyld entry point may mark live image evidence. */
int rp_v13_collect_image_candidates(const RP_V13_LoadedImageView *views,
                                     size_t count, RP_V13_IdentityEvidence *out);

/* On iOS/macOS only: inspect images reported by dyld. Return 1 iff the
 * exact GTA5 + libgtacompat UUID pair passes rp_v13_identity_check().
 * Not an Apple signature, loaded code hash, RAGE hook or network proof.
 * Call at a controlled lifecycle point; dyld enumeration is not thread-safe
 * against concurrent image loads/unloads. On non-Apple platforms returns 0. */
int rp_v13_dyld_collect_identity(RP_V13_IdentityEvidence *out);

#ifdef __cplusplus
}
#endif
#endif
