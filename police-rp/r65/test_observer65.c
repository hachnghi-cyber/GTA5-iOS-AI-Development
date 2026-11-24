#include "observer65.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
static void *other(void *v){(void)v;for(int i=0;i<10000;i++){rp65_observe(RP65_TICK);rp65_observe(RP65_RX);}return 0;}
static void *stress(void *v){(void)v;for(int i=0;i<50000;i++){rp65_observe(RP65_TICK);rp65_observe(RP65_RX);}return 0;}
int main(void){RP65Snapshot s;pthread_t th[4];assert(!rp65_snapshot(0));rp65_observe(0);rp65_observe(RP65_RX);assert(rp65_snapshot(&s)&&s.rx_before_tick==1&&!s.owner_seen&&!s.ticks);rp65_observe(RP65_TICK);rp65_observe(RP65_RX);assert(!pthread_create(&th[0],0,other,0));assert(!pthread_join(th[0],0));assert(rp65_snapshot(&s)&&s.owner_seen&&s.ticks==10001&&s.rx==10002&&s.tick_other==10000&&s.rx_other==10000&&!s.contended);for(int i=0;i<4;i++)assert(!pthread_create(&th[i],0,stress,0));for(int i=0;i<4;i++)assert(!pthread_join(th[i],0));assert(rp65_snapshot(&s)&&s.ticks+s.rx+s.contended==420003&&s.tick_other==s.ticks-1&&s.rx_other==s.rx-2);printf("PASS 420003 observations accounted for; tick=%llu rx=%llu contended=%u\n",(unsigned long long)s.ticks,(unsigned long long)s.rx,s.contended);return 0;}
