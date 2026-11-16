#ifndef RBP_HANDOFF_H
#define RBP_HANDOFF_H
#ifdef RBP_FREESTANDING_ARM64
typedef __UINT64_TYPE__ uint64_t;
typedef __UINT8_TYPE__ uint8_t;
#else
#include <stdint.h>
#endif
#include <stdatomic.h>
/* Single slot bounded handoff. One active consumer/game-thread; multi-producer safe.
 * No game calls are permitted from producers. A full queue drops events (caller retries).
 * This is not a network transport or gameplay integration.
 */
enum {RBP_EMPTY=0, RBP_WRITING=1, RBP_READY=2, RBP_READING=3};
typedef struct {
    uint64_t sequence;
    uint8_t sender[16];
    uint8_t nonce[8]; /* bind delayed game-thread receipt to original ACTION */
    uint8_t type; /* 1=diagnostic ping only; no game mutations */
} rbp_diag_event;
typedef struct {
    atomic_uint state;
    rbp_diag_event item;
} rbp_handoff;
void rbp_handoff_init(rbp_handoff *h);
int rbp_handoff_push(rbp_handoff *h, const rbp_diag_event *event);
int rbp_handoff_pop_on_game_thread(rbp_handoff *h, rbp_diag_event *output);
#endif
