#ifndef RBP_DEVICE_NETWORK_H
#define RBP_DEVICE_NETWORK_H
/* OPTIONAL iOS diagnostic transport. One peer/session; not RAGE networking. */
#include <stdint.h>
#include <stdatomic.h>
#include "rbp_handoff.h"
#include "rbp_wire_c.h"

typedef struct {
  int mode; /* 1 = RECEIVER(B), 2 = SENDER(A) */
  uint16_t listen_port, peer_port;
  char peer_ipv4[32];
  uint8_t self[16],peer[16],session[16],key[32];
} rbp_device_config;

typedef struct {
  rbp_device_config conf;
  rbp_receiver_c receiver;
  rbp_handoff *handoff;
  atomic_int running, send_once, active;
  atomic_int receipt_state; /* 0 empty, 1 writer, 2 ready: one-shot diagnostic */
  atomic_int native_receipt_verified; /* sender observed HMAC result; NOT in-game visibility */
  uint64_t receipt_sequence;
  uint8_t receipt_nonce[8];
  void *thread_token; /* points to heap-allocated pthread_t; NEVER used on game thread */
} rbp_device_network;
/* Fail closed: a missing/invalid config disables networking. */
int rbp_config_read(const char *path,rbp_device_config *out);
int rbp_network_start(rbp_device_network *net, const rbp_device_config *conf,rbp_handoff *q);
int rbp_network_request_ping(rbp_device_network *net);
/* Publish a single verified game-thread NATIVE-API-INVOCATION marker.
 * 1 means queued to the UDP worker, NOT transmitted or visually observed. */
int rbp_network_report_native_invocation(rbp_device_network *net,
                                        uint64_t seq, const uint8_t nonce[8]);
void rbp_network_stop(rbp_device_network *net);
#endif
