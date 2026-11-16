#include "rbp_handoff.h"
#include <assert.h>
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <string.h>
#define COUNT 10000
static rbp_handoff g;
static int successes=0;
static void *producer(void *unused) {
 (void)unused;
 rbp_diag_event e={0}; e.type=1;
 for(int i=1;i<=COUNT;i++) {
  e.sequence=(uint64_t)i;
  while(rbp_handoff_push(&g,&e)==0) sched_yield();
 }
 return NULL;
}
int main(void) {
 rbp_handoff_init(&g);
 rbp_diag_event bad={0};assert(rbp_handoff_push(&g,&bad)==-1);
 assert(rbp_handoff_pop_on_game_thread(&g,&bad)==0);
 pthread_t thread; assert(pthread_create(&thread,0,producer,0)==0);
 rbp_diag_event got={0}; uint64_t prev=0;
 while(successes<COUNT) {
  int res=rbp_handoff_pop_on_game_thread(&g,&got);
  if(res==0) { sched_yield(); continue; }
  assert(res==1); assert(got.type==1);assert(got.sequence==prev+1);
  prev=got.sequence; successes++;
 }
 assert(pthread_join(thread,0)==0);
 assert(atomic_load(&g.state)==RBP_EMPTY);
 printf("PASS single-producer/game-thread-consumer: %d events; strict sequence; queue empty\n",successes);
 return 0;
}
