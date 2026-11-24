#ifndef RP65_OBSERVER_H
#define RP65_OBSERVER_H
#include <stdint.h>
/* Diagnostics only: no game pointers, no authority, no consent inference. */
enum { RP65_TICK=1, RP65_RX=2 };
typedef struct {uint64_t ticks,rx,tick_other,rx_other,rx_before_tick; unsigned owner_seen,contended;} RP65Snapshot;
void rp65_observe(unsigned source);
int rp65_snapshot(RP65Snapshot *out);
#endif
