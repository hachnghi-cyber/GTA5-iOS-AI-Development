#ifndef RP_AUTHORITY_FFI_H
#define RP_AUTHORITY_FFI_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#define RP_SERVER_API __declspec(dllexport)
#elif defined(__GNUC__)
#define RP_SERVER_API __attribute__((visibility("default")))
#else
#define RP_SERVER_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define RP_SERVER_FACT_COUNT 7u
#define RP_SERVER_SNAPSHOT_COUNT 10u

/* ABI 3. One trusted, serialized in-process authority owner uses each handle.
 * This adapter neither authenticates sockets nor binds an RP principal to a
 * GTA player. The TLS owner must derive sender from its certificate registry,
 * assign roles itself, and call leave on disconnect or admission expiry.
 * Never populate sender, role or facts from an untrusted command payload.
 * Restart with a fresh session/epoch; this module has no durable replay store.
 */
RP_SERVER_API uint32_t rp_server_abi(void);
RP_SERVER_API void *rp_server_create(uint64_t session, uint64_t epoch);
RP_SERVER_API void rp_server_destroy(void *handle);
RP_SERVER_API int rp_server_admit(void *handle, uint64_t id, uint32_t role);
RP_SERVER_API int rp_server_leave(void *handle, uint64_t id);
/* Trusted owner only. End this game admission without closing the RP link. */
RP_SERVER_API int rp_server_reset_game_member(void *handle, uint64_t id);
/* Trusted owner only. Clears the officer's duty and any custody they hold. */
RP_SERVER_API int rp_server_revoke_duty(void *handle, uint64_t id);
RP_SERVER_API int rp_server_tick(void *handle, uint64_t now_ms);

/* Optional facts is NULL/count 0, or exactly seven uint64_t values:
 * observed_at_ms, vehicle_id, distance_cm, seat, flags, actor, target.
 * Flags: same game instance=1, eligible native duty=2, police vehicle=4,
 * seat available=8, both at jail intake=16. Unknown bits are rejected.
 * Facts must come from the authority's independent observation source.
 * With no facts, self consent/revocation works; duty/custody is denied.
 * Session and epoch are supplied by the authority world, never by facts.
 * wire_size and ack_size must both be 40 bytes (PRPC and PRPA respectively).
 * Returns 1 if an ACK was produced, including policy denial and exact retry.
 * Returns 0 on invalid input; ack is unchanged. An ACK is a transaction
 * decision, not a current state snapshot or proof of native gameplay.
 */
RP_SERVER_API int rp_server_dispatch(void *handle, uint64_t sender, uint64_t now_ms,
                                     const uint8_t *wire, size_t wire_size,
                                     const uint64_t *facts, size_t facts_count,
                                     uint8_t *ack, size_t ack_size);

/* Exactly ten uint64_t values: id, role, consent, on_duty, custody, custodian,
 * vehicle_id, seat, jail_until_ms, last_nonce. Returns 0 if absent. A valid
 * output buffer is zeroed on absence; invalid output size leaves it unchanged.
 */
RP_SERVER_API int rp_server_snapshot(void *handle, uint64_t id,
                                     uint64_t *out, size_t out_count);

#ifdef __cplusplus
}
#endif
#endif
