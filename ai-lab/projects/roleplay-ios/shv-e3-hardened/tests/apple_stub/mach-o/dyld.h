/* Test-only declaration, for Apple-only syntax coverage on Linux. */
#ifndef RBP_TEST_MACH_DYLD_H
#define RBP_TEST_MACH_DYLD_H
#include <stdint.h>
uint32_t _dyld_image_count(void);
const char *_dyld_get_image_name(uint32_t);
#endif
