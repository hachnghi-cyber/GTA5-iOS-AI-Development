#ifndef GOJO_TOUCH_QUEUE_H
#define GOJO_TOUCH_QUEUE_H

#include <stdint.h>

#if defined(__GNUC__)
#define GOJO_TOUCH_API __attribute__((visibility("default")))
#else
#define GOJO_TOUCH_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Actions are 0..4: Infinity, Red, Blue, Purple, Void.
// Each press sets one bit; duplicate taps in the same game frame coalesce.
void gojo_touch_press(unsigned int action);
GOJO_TOUCH_API uint32_t gojo_touch_consume(void);
void gojo_touch_clear(void);

// Implemented by the iOS UIKit overlay module.
GOJO_TOUCH_API void gojo_touch_set_enabled(int enabled);

#ifdef __cplusplus
}
#endif

#endif
