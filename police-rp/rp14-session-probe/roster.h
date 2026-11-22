#ifndef RP14_ROSTER_H
#define RP14_ROSTER_H
#include <stdint.h>
#include <stddef.h>
typedef int (*rp14_read)(void *, uint64_t, void *, size_t);
typedef struct { rp14_read read; void *ctx; uint64_t slide; } RReader;
typedef struct { uint64_t manager, player[32], ped[32]; uint32_t mask, ped_mask; int slot, reason; } RSnapshot;
typedef struct { RSnapshot previous; uint64_t epoch, sample, generation[32]; int valid; } RTracker;
int rp14_roster(const RReader*, RSnapshot*);
void rp14_track(RTracker*,const RSnapshot*,int);
#endif
