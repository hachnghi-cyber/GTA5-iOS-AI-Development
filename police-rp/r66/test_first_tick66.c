#include "observer65.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
static _Atomic unsigned ready,go,done;
static void *worker(void *p){(void)p;atomic_fetch_add(&ready,1);while(!atomic_load(&go)){} for(int i=0;i<10000;i++){rp65_observe(RP65_TICK);rp65_observe(RP65_RX);}atomic_fetch_add(&done,1);return 0;}
int main(void){pthread_t t[8];RP65Snapshot s={0},prev={0};for(int i=0;i<8;i++)assert(!pthread_create(t+i,0,worker,0));while(atomic_load(&ready)!=8){} atomic_store(&go,1);while(atomic_load(&done)!=8){assert(rp65_snapshot(&s));assert(s.ticks>=prev.ticks&&s.rx>=prev.rx&&s.tick_other>=prev.tick_other&&s.rx_other>=prev.rx_other);prev=s;}for(int i=0;i<8;i++)assert(!pthread_join(t[i],0));assert(rp65_snapshot(&s)&&s.ticks==80000&&s.rx==80000&&s.tick_other==70000&&s.rx_other==70000&&s.owner_seen&&!s.rx_before_tick&&!s.contended);puts("PASS 160000 events, simultaneous first tick, zero loss, monotonic snapshots");return 0;}
