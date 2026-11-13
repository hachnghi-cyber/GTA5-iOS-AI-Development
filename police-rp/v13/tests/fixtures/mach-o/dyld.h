#ifndef RP_V13_DYLD_HOST_DYLD_H
#define RP_V13_DYLD_HOST_DYLD_H
#include <stdint.h>
#include "loader.h"
uint32_t _dyld_image_count(void);
const struct mach_header *_dyld_get_image_header(uint32_t image_index);
const char *_dyld_get_image_name(uint32_t image_index);
#endif
