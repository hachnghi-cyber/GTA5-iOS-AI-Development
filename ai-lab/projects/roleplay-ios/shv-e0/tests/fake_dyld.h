/* Test-only Mach-O and dyld API stand-ins. Do not ship in iOS builds. */
#ifndef RBP_FAKE_DYLD_H
#define RBP_FAKE_DYLD_H
#include <stdint.h>
#define MH_MAGIC_64 0xFEEDFACFu
#define CPU_TYPE_ARM64 0x0100000Cu
#define LC_UUID 0x1Bu
struct mach_header {uint32_t magic; int32_t cputype,cpusubtype; uint32_t filetype,ncmds,sizeofcmds,flags;};
struct mach_header_64 {uint32_t magic; int32_t cputype,cpusubtype; uint32_t filetype,ncmds,sizeofcmds,flags,reserved;};
struct load_command {uint32_t cmd,cmdsize;};
struct uuid_command {uint32_t cmd,cmdsize;uint8_t uuid[16];};
extern uint32_t _dyld_image_count(void);
extern const char *_dyld_get_image_name(uint32_t index);
extern const struct mach_header *_dyld_get_image_header(uint32_t index);
#endif
