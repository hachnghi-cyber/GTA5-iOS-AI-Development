#ifndef RBP_WIRE_C_H
#define RBP_WIRE_C_H
/* RBP1 C wire contract, 96 bytes; header has no native padding.
 * Diagnostic PING ONLY. No arbitrary native hashes/commands accepted.
 * A shared key authenticates the configured peer, NOT the GTA session/owner.
 */
#include <stddef.h>
#include <stdint.h>
#include "rbp_handoff.h"
#ifdef __cplusplus
extern "C" {
#endif
#define RBP_WIRE_SIZE 96u
#define RBP_HEADER_SIZE 80u
#define RBP_KEY_SIZE 32u
#define RBP_ID_SIZE 16u
#define RBP_NONCE_SIZE 8u
#define RBP_DIAG_PING 1u
#define RBP_KIND_ACTION 1u
#define RBP_KIND_ACK 2u
#define RBP_KIND_NATIVE_INVOKED 3u /* game-thread native API called, not HUD observed */

typedef struct {
  uint8_t kind; uint16_t action;
  uint64_t sequence, timestamp_ms;
  uint8_t sender[16], target[16], session[16], nonce[8];
} rbp_frame_c;

typedef struct {
  uint8_t self[16], allowed_sender[16], session[16], key[32];
  uint64_t committed_sequence;
  uint8_t committed_nonce[8];
  uint32_t max_skew_ms;
  int has_committed;
} rbp_receiver_c;

typedef enum {
  RBP_RX_BAD=-1, RBP_RX_BUSY=-2, RBP_RX_ACCEPTED=1, RBP_RX_DUPLICATE=2
} rbp_rx_result;

/* Native platform implementation (CommonCrypto on iOS, OpenSSL on host). */
int rbp_hmac_sha256(const uint8_t key[32], const uint8_t *data,
                    size_t len, uint8_t out[32]);
int rbp_wire_encode(const rbp_frame_c *f, const uint8_t key[32],
                    uint8_t result[RBP_WIRE_SIZE]);
int rbp_wire_decode(const uint8_t *packet, size_t length,
                    const uint8_t key[32], rbp_frame_c *out);
/* Validate a decoded queue ACK or delayed native-invoked report against the
 * exact outstanding request. The UDP layer ALSO checks socket source and HMAC
 * before calling this. Never interpret as game visibility or RAGE authority. */
int rbp_response_matches_request(const rbp_frame_c *response,
          const rbp_frame_c *request, uint8_t kind, uint64_t received_ms);
/* Caller serializes this state on a single network receive thread.
 * A full handoff must produce BUSY and NO ACK; retries may later succeed.
 * ACK means queued, NOT native invoked or visualized.
 */
rbp_rx_result rbp_receiver_handle(rbp_receiver_c *s, rbp_handoff *handoff,
       const uint8_t *packet, size_t length, uint64_t now_ms,
       uint8_t ack[RBP_WIRE_SIZE]);
#ifdef __cplusplus
}
#endif
#endif
