#ifndef RP_V13_DYLD_HOST_LOADER_H
#define RP_V13_DYLD_HOST_LOADER_H
#include <stdint.h>
#define MH_MAGIC_64 0xfeedfacfu
struct mach_header { uint32_t magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags; };
struct mach_header_64 { uint32_t magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved; };
#endif
