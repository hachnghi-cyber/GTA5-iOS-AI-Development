#ifndef RP_V133_AUTHORITY_CLIENT_H
#define RP_V133_AUTHORITY_CLIENT_H

#include "rp_v133_police_tx.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RP_AUTHORITY_HEADER_BYTES 5u
#define RP_AUTHORITY_REQUEST_BYTES (RP_AUTHORITY_HEADER_BYTES + RP_POLICE_TX_BYTES)
#define RP_AUTHORITY_MAX_RECORD_BYTES 4096u
#define RP_AUTHORITY_MEMBER_FIELDS 10u

typedef enum {
    RP_AUTHORITY_WELCOME = 1,
    RP_AUTHORITY_REQUEST,
    RP_AUTHORITY_ACK,
    RP_AUTHORITY_SNAPSHOT,
    RP_AUTHORITY_PING,
    RP_AUTHORITY_PONG
} rp_authority_record_kind;

/* A single owner uses this POD only after its external TLS adapter verifies
 * the CA, server certificate pin, hostname and police-rp-authority/1 ALPN.
 * Parsing does not perform that verification. These IDs and snapshots belong
 * only to the RP server; they never identify a GTA player or authorize natives.
 * ready means WELCOME accepted. revision != 0 means a snapshot was accepted.
 */
typedef struct {
    bool ready;
    bool pending;
    uint64_t expected_id;
    uint64_t session;
    uint64_t epoch;
    uint64_t last_nonce;
    uint64_t revision;
    rp_police_command pending_command;
    rp_police_ack last_ack; /* Historical decision, never current custody. */
    /* Rows: id, role, consent, on_duty, custody, custodian, vehicle_id,
     * seat, jail_until_ms, last_nonce. No native pointers or game binding. */
    uint64_t members[RP_V133_POLICE_CAPACITY][RP_AUTHORITY_MEMBER_FIELDS];
    uint32_t member_count;
} rp_authority_client;

bool rp_authority_client_init(rp_authority_client *client, uint64_t expected_id);
/* Clears every field. Reconnect requires init after fresh TLS verification.
 * Call on EOF, timeout, cancellation, partial write or any transport failure. */
void rp_authority_client_stop(rp_authority_client *client);

/* Decode exactly one five-byte inbound server header. Only WELCOME, ACK,
 * SNAPSHOT and PONG are accepted, with their fixed/bounded payload lengths.
 * Failure zeroes nonnull output values. Caller must stop client on failure. */
bool rp_authority_record_header(const uint8_t *wire, size_t size,
                                 uint8_t *kind, uint32_t *payload_size);

/* Receives an entire payload after read-exact framing. Invalid/unexpected
 * records clear all client state. ACK must match the sole pending command;
 * it never changes snapshots. Same-revision snapshots must be identical. */
bool rp_authority_client_receive(rp_authority_client *client, uint8_t kind,
                                  const uint8_t *payload, size_t size);

/* Produces one complete 45-byte REQUEST. Success consumes the next nonce
 * before any transport write and blocks another request until matching ACK.
 * Failure leaves client and output unchanged; there is no nonce wraparound.
 * A failed/cancelled write requires stop, not reuse of the pending channel. */
bool rp_authority_client_request(rp_authority_client *client,
                                  rp_police_operation operation, uint64_t target,
                                  uint8_t *out, size_t size);
/* Produces a five-byte PING, also while a request is pending. */
bool rp_authority_client_ping(const rp_authority_client *client,
                               uint8_t *out, size_t size);

/* Optional local diagnostic. Call after successfully consuming a frame. It
 * verifies ACK plus snapshot for self opt-in/out, without gameplay effects. */
typedef enum {
    RP_CONSENT_PROBE_INITIAL = 0,
    RP_CONSENT_PROBE_OPTING_IN,
    RP_CONSENT_PROBE_OPTING_OUT
} rp_consent_probe_phase;

typedef enum {
    RP_CONSENT_PROBE_WAIT = 0,
    RP_CONSENT_PROBE_SEND,
    RP_CONSENT_PROBE_PASSED,
    RP_CONSENT_PROBE_FAILED
} rp_consent_probe_result;

rp_consent_probe_result rp_authority_consent_probe_step(rp_authority_client *client,
    rp_consent_probe_phase *phase, uint8_t *out, size_t size);

#ifdef __cplusplus
}
#endif
#endif
