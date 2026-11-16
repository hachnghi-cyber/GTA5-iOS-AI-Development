#include "rp_v133_mailbox.h"
#include <string.h>

/* A failed try-lock drops work rather than stalling a network callback. */
static int try_lock(rp_v133_mailbox *box) {
    return !atomic_flag_test_and_set_explicit(&box->lock, memory_order_acquire);
}
static void unlock(rp_v133_mailbox *box) {
    atomic_flag_clear_explicit(&box->lock, memory_order_release);
}

void rp_v133_mailbox_init(rp_v133_mailbox *box) {
    if (!box) return;
    /* Must not run concurrently with any producer, consumer, or reset. */
    memset(box, 0, sizeof(*box));
    atomic_flag_clear(&box->lock);
    atomic_init(&box->dropped_invalid, 0u);
    atomic_init(&box->dropped_busy, 0u);
    atomic_init(&box->dropped_full, 0u);
}

int rp_v133_mailbox_enqueue(rp_v133_mailbox *box,
                            const rp_v133_delivery *trusted,
                            const uint8_t *wire, size_t length) {
    if (!box) return 0;
    if (!trusted || trusted->authenticated != 1 ||
        !trusted->transport_sender || !trusted->transport_session ||
        !trusted->transport_epoch || !wire ||
        length != RP_V133_WIRE_BYTES) {
        atomic_fetch_add_explicit(&box->dropped_invalid, 1u,
                                  memory_order_relaxed);
        return 0;
    }
    if (!try_lock(box)) {
        atomic_fetch_add_explicit(&box->dropped_busy, 1u,
                                  memory_order_relaxed);
        return 0;
    }
    if (box->count >= RP_V133_QUEUE_CAPACITY) {
        atomic_fetch_add_explicit(&box->dropped_full, 1u,
                                  memory_order_relaxed);
        unlock(box);
        return 0;
    }
    rp_v133_queued_event *item = &box->entries[box->tail];
    item->trusted = *trusted;
    memcpy(item->wire, wire, RP_V133_WIRE_BYTES);
    box->tail = (box->tail + 1u) % RP_V133_QUEUE_CAPACITY;
    ++box->count;
    unlock(box);
    return 1;
}

static int pop(rp_v133_mailbox *box, rp_v133_queued_event *out) {
    if (!try_lock(box)) return 0;
    if (!box->count) {
        unlock(box);
        return 0;
    }
    *out = box->entries[box->head];
    /* Do not keep copied payload/identity in reusable queue slots. */
    memset(&box->entries[box->head], 0, sizeof(box->entries[box->head]));
    box->head = (box->head + 1u) % RP_V133_QUEUE_CAPACITY;
    --box->count;
    unlock(box);
    return 1;
}

int rp_v133_mailbox_pump(rp_v133_mailbox *box, rp_v133_gate *gate,
                         rp_v133_pump_report *report) {
    if (report) *report = (rp_v133_pump_report){0};
    if (!box || !gate || !gate->bound ||
        !gate->cb.on_game_thread ||
        !gate->cb.on_game_thread(gate->cb.ctx)) return 0;
    rp_v133_pump_report totals = {0};
    for (unsigned i=0; i<RP_V133_QUEUE_FRAME_BUDGET; ++i) {
        rp_v133_queued_event item;
        if (!pop(box, &item)) break;
        ++totals.processed;
        rp_v133_result r = rp_v133_wire_deliver(
            gate, &item.trusted, item.wire, sizeof item.wire);
        if (r == RP_V133_RECEIVED) ++totals.accepted;
        else ++totals.denied;
        memset(&item, 0, sizeof item);
        /* A handler may revoke the gate. Stop applying events until rebound. */
        if (!gate->bound) break;
    }
    if (report) *report = totals;
    return 1;
}

int rp_v133_mailbox_try_clear(rp_v133_mailbox *box) {
    if (!box || !try_lock(box)) return 0;
    memset(box->entries, 0, sizeof box->entries);
    box->head = box->tail = box->count = 0;
    unlock(box);
    return 1;
}
