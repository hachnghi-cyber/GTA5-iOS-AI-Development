#include "GojoTouchQueue.h"
#include <stdatomic.h>

static atomic_uint_fast32_t pending_actions = ATOMIC_VAR_INIT(0);

void gojo_touch_press(unsigned int action)
{
    if (action >= 5u) return;
    atomic_fetch_or_explicit(&pending_actions, (uint_fast32_t)1u << action,
                             memory_order_release);
}

uint32_t gojo_touch_consume(void)
{
    return (uint32_t)atomic_exchange_explicit(&pending_actions, 0,
                                              memory_order_acq_rel);
}

void gojo_touch_clear(void)
{
    atomic_store_explicit(&pending_actions, 0, memory_order_release);
}
