#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#endif
#define _POSIX_C_SOURCE 200809L
#include "observer65.h"
#include <stdatomic.h>
#include <pthread.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <errno.h>
#include <inttypes.h>
#ifndef RP68_SAMPLES
#define RP68_SAMPLES 120u
#endif
#ifndef RP68_INTERVAL_NS
#define RP68_INTERVAL_NS 5000000000ull
#endif
/* Diagnostic build only. No game pointers, packet data, or RP authority. */
static _Atomic unsigned state; /* 0 idle, 1 starting/running, 2 done, 3 failure */
static int delay(void){
 struct timespec t={(time_t)(RP68_INTERVAL_NS/1000000000ull),(long)(RP68_INTERVAL_NS%1000000000ull)};
 while(nanosleep(&t,&t)!=0)if(errno!=EINTR)return 0;
 return 1;
}
static void *logger(void *unused){
 (void)unused;
 char path[1024]; const char *home=getenv("HOME");
 if(!home||home[0]!='/')goto fail;
 int n=snprintf(path,sizeof path,"%s/Documents/RP68-Thread-%ld.log",home,(long)getpid());
 if(n<0||(size_t)n>=sizeof path)goto fail;
 int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
 if(fd<0)goto fail;
 FILE *f=fdopen(fd,"w");if(!f){close(fd);goto fail;}
 int ok=fputs("RP68 schema=1 diagnostic-only snapshot=nontransactional\n",f)>=0;
 for(unsigned i=0;ok&&i<RP68_SAMPLES;i++){
  RP65Snapshot s;
  ok=rp65_snapshot(&s)&&fprintf(f,"sample=%u ticks=%" PRIu64 " rx=%" PRIu64 " tick_other=%" PRIu64 " rx_other=%" PRIu64 " rx_before_tick=%" PRIu64 " owner_seen=%u exhausted=%u\n",i,s.ticks,s.rx,s.tick_other,s.rx_other,s.rx_before_tick,s.owner_seen,s.contended)>0&&fflush(f)==0;
  if(ok&&i+1<RP68_SAMPLES)ok=delay();
 }
 if(fclose(f)!=0)ok=0;
 atomic_store_explicit(&state,ok?2u:3u,memory_order_release);return NULL;
fail:
 atomic_store_explicit(&state,3,memory_order_release);return NULL;
}
void rp68_observe(unsigned source){
 if(source!=RP65_TICK&&source!=RP65_RX)return;
 rp65_observe(source);
 if(source!=RP65_TICK||atomic_load_explicit(&state,memory_order_relaxed))return;
 unsigned expected=0;
 if(!atomic_compare_exchange_strong_explicit(&state,&expected,1,memory_order_acq_rel,memory_order_relaxed))return;
 pthread_attr_t attr;pthread_t thread;
 if(pthread_attr_init(&attr)!=0){atomic_store(&state,3);return;}
 int rc=pthread_attr_setdetachstate(&attr,PTHREAD_CREATE_DETACHED);
 if(!rc)rc=pthread_create(&thread,&attr,logger,NULL);
 pthread_attr_destroy(&attr);
 if(rc)atomic_store_explicit(&state,3,memory_order_release);
}
#ifdef RP68_TEST
unsigned rp68_test_state(void){return atomic_load_explicit(&state,memory_order_acquire);}
#endif
