#include "observer65.h"
#include <stdatomic.h>
#include <limits.h>
/* Independent monotonic counters. Snapshots are quiescently exact, not
 * globally atomic while observations are being recorded. No game authority. */
static _Atomic uint64_t ticks,rx,tick_other,rx_other,rx_before_tick;
static _Atomic uint64_t first_tick,next_tag;
static _Atomic unsigned exhausted;
static _Thread_local uint64_t thread_tag;
static void inc(_Atomic uint64_t *p){
 uint64_t n=atomic_load_explicit(p,memory_order_relaxed);
 while(n!=UINT64_MAX&&!atomic_compare_exchange_weak_explicit(p,&n,n+1,memory_order_relaxed,memory_order_relaxed)){}
}
static void drop(void){unsigned n=atomic_load_explicit(&exhausted,memory_order_relaxed);while(n!=UINT_MAX&&!atomic_compare_exchange_weak_explicit(&exhausted,&n,n+1,memory_order_relaxed,memory_order_relaxed)){} }
static uint64_t tag(void){
 if(thread_tag)return thread_tag;
 uint64_t n=atomic_load_explicit(&next_tag,memory_order_relaxed);
 while(n!=UINT64_MAX){
  if(atomic_compare_exchange_weak_explicit(&next_tag,&n,n+1,memory_order_relaxed,memory_order_relaxed))return thread_tag=n+1;
 }
 return 0;
}
void rp65_observe(unsigned source){
 if(source!=RP65_TICK&&source!=RP65_RX)return;
 uint64_t me=tag();if(!me){drop();return;}
 if(source==RP65_TICK){
  uint64_t owner=0;
  if(!atomic_compare_exchange_strong_explicit(&first_tick,&owner,me,memory_order_acq_rel,memory_order_acquire)&&owner!=me)inc(&tick_other);
  inc(&ticks);
 }else{
  uint64_t owner=atomic_load_explicit(&first_tick,memory_order_acquire);
  if(!owner)inc(&rx_before_tick);else if(owner!=me)inc(&rx_other);
  inc(&rx);
 }
}
int rp65_snapshot(RP65Snapshot *out){
 if(!out)return 0;
 out->ticks=atomic_load_explicit(&ticks,memory_order_relaxed);
 out->rx=atomic_load_explicit(&rx,memory_order_relaxed);
 out->tick_other=atomic_load_explicit(&tick_other,memory_order_relaxed);
 out->rx_other=atomic_load_explicit(&rx_other,memory_order_relaxed);
 out->rx_before_tick=atomic_load_explicit(&rx_before_tick,memory_order_relaxed);
 out->owner_seen=atomic_load_explicit(&first_tick,memory_order_acquire)!=0;
 out->contended=atomic_load_explicit(&exhausted,memory_order_relaxed);
 return 1;
}
