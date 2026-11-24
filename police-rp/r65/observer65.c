#include "observer65.h"
#include <stdatomic.h>
#include <limits.h>
static atomic_flag gate=ATOMIC_FLAG_INIT;
static _Atomic unsigned contended;
static RP65Snapshot stats;
static uint64_t first_tick,next_tag;
static _Thread_local uint64_t thread_tag;
static void inc(uint64_t *p){if(*p!=UINT64_MAX)++*p;}
static void drop(void){unsigned n=atomic_load_explicit(&contended,memory_order_relaxed);while(n!=UINT_MAX&&!atomic_compare_exchange_weak_explicit(&contended,&n,n+1,memory_order_relaxed,memory_order_relaxed)){} }
void rp65_observe(unsigned source){
 if(source!=RP65_TICK&&source!=RP65_RX)return;
 if(atomic_flag_test_and_set_explicit(&gate,memory_order_acquire)){drop();return;}
 if(!thread_tag){
  if(next_tag==UINT64_MAX){drop();atomic_flag_clear_explicit(&gate,memory_order_release);return;}
  thread_tag=++next_tag;
 }
 uint64_t me=thread_tag;
 if(source==RP65_TICK){
  inc(&stats.ticks);
  if(!stats.owner_seen){first_tick=me;stats.owner_seen=1;}
  else if(first_tick!=me)inc(&stats.tick_other);
 }else{
  inc(&stats.rx);
  if(!stats.owner_seen)inc(&stats.rx_before_tick);
  else if(first_tick!=me)inc(&stats.rx_other);
 }
 atomic_flag_clear_explicit(&gate,memory_order_release);
}
int rp65_snapshot(RP65Snapshot *out){
 if(!out)return 0;
 if(atomic_flag_test_and_set_explicit(&gate,memory_order_acquire))return 0;
 *out=stats;out->contended=atomic_load_explicit(&contended,memory_order_relaxed);
 atomic_flag_clear_explicit(&gate,memory_order_release);return 1;
}
