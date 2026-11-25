#ifndef RP_V133_MAILBOX_H
#define RP_V133_MAILBOX_H
/*
 * Source-only v13.3 PRP3 network-thread -> game-thread mailbox.
 * Does not discover a GTA callback, authenticate a channel, hook Mach-O,
 * or modify any gameplay. Engine integration must provide trusted metadata.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>
#include "rp_v133_wire.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RP_V133_QUEUE_CAPACITY 64u
#define RP_V133_QUEUE_FRAME_BUDGET 8u

typedef struct {
    rp_v133_delivery trusted;
    uint8_t wire[RP_V133_WIRE_BYTES];
} rp_v133_queued_event;

typedef struct {
    atomic_flag lock;
    atomic_uint dropped_invalid;
    atomic_uint dropped_busy;
    atomic_uint dropped_full;
    uint32_t head;
    uint32_t tail;
    uint32_t count;
    rp_v133_queued_event entries[RP_V133_QUEUE_CAPACITY];
} rp_v133_mailbox;

typedef struct {
    uint32_t processed;
    uint32_t accepted; /* gate accepted, not confirmed as gameplay */
    uint32_t denied;
} rp_v133_pump_report;

/* Call once before concurrent access; never while producer is active. */
void rp_v133_mailbox_init(rp_v133_mailbox *box);

/* Nonblocking producer: only copy 40 bytes and transport-owned metadata.
 * This API cannot prove that the caller really owns a trusted GTA channel. */
int rp_v133_mailbox_enqueue(rp_v133_mailbox *box,
                            const rp_v133_delivery *trusted,
                            const uint8_t *wire, size_t length);

/* Called on the actual game thread only. Returns 0 if not on game thread.
 * Never invokes any game native except through gate's supplied callbacks.
 * Pops at most 8 frames to avoid unbounded per-frame work. */
int rp_v133_mailbox_pump(rp_v133_mailbox *box, rp_v133_gate *gate,
                         rp_v133_pump_report *report);

/* Nonblocking reset on disconnect, host migration, or app shutdown.
 * 0 means contention: game integrator must retry; do not reuse queue.
 * Even when a reset is deferred, the gate rejects stale session/epoch. */
int rp_v133_mailbox_try_clear(rp_v133_mailbox *box);

#ifdef __cplusplus
}
#endif
#endif
