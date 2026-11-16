/* Test-only declarations! NOT Apple SDK headers and NOT an iOS build. */
#ifndef RBP_TEST_MACHO_LOADER_H
#define RBP_TEST_MACHO_LOADER_H
#include <stdint.h>
#define MH_MAGIC_64 0xfeedfacfu
#define LC_UUID 0x1bu
struct mach_header_64 { uint32_t magic; int32_t cputype; int32_t cpusubtype; uint32_t filetype, ncmds, sizeofcmds, flags, reserved; };
struct load_command { uint32_t cmd, cmdsize; };
struct uuid_command { uint32_t cmd, cmdsize; uint8_t uuid[16]; };
#endif
