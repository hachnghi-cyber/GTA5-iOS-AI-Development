/* Phase 7: read-only same-process telemetry, no native calls or game memory writes. */
#include "session.h"
#include <mach-o/dyld.h>
#include <mach/mach.h>
#include <stdio.h>
#include <stdlib.h>
#include <dispatch/dispatch.h>
typedef unsigned int u32; typedef unsigned long u64;
static long slide; static char path[1024]; static unsigned ticks;
static const unsigned char uuid[16]={0xd7,0x88,0x01,0x47,0x4e,0xee,0x33,0x50,0xa1,0x9b,0xd6,0xa1,0x8b,0x2f,0x0d,0x24};
static int equal(const unsigned char*a,const unsigned char*b){for(int i=0;i<16;i++)if(a[i]!=b[i])return 0;return 1;}
static int image_ok(void){const unsigned char *h=(const unsigned char *)_dyld_get_image_header(0);if(!h||*(const u32*)h!=0xfeedfacf||*(const u32*)(h+4)!=0x0100000c)return 0;u32 n=*(const u32*)(h+16), size=*(const u32*)(h+20), off=32; if(n>128||size>16000)return 0;int match=0, data=0;for(u32 i=0;i<n;i++){if(off+8>32+size)return 0;const unsigned char*p=h+off;u32 cmd=*(const u32*)p,len=*(const u32*)(p+4);if(len<8||len>32+size-off)return 0;if(cmd==0x1b&&len==24)match=equal(p+8,uuid);if(cmd==0x19&&len>=72){u64 va=*(const u64*)(p+24),vs=*(const u64*)(p+32);if(va==0x1028f4000UL && vs==0x015a8000UL)data=1;}off+=len;}return match&&data;}
static STracker tracker;
static int readcopy(void *unused,uint64_t addr,void *out,size_t n){
 (void)unused;vm_size_t got=0;
 return vm_read_overwrite(mach_task_self(),(vm_address_t)addr,(vm_size_t)n,(vm_address_t)out,&got)==KERN_SUCCESS && got==n;
}
static void sample(void *unused){
 (void)unused; ++ticks;
 RReader rd={readcopy,0,(uint64_t)slide}; RSnapshot snap;
 SSession ss; int session_reason; int ok=rp14_session_roster(&rd,&ss,&snap,&session_reason);rp14_session_track(&tracker,&ss,&snap,ok);
 FILE *f=fopen(path,"a");if(f){
 fprintf(f,"{\"tick\":%u,\"valid\":%d,\"reason\":%d,\"session_reason\":%d,\"room_epoch\":%llu,\"epoch\":%llu,\"slot\":%d,\"mask\":%u,\"ped_mask\":%u,\"generation\":[",ticks,ok,snap.reason,session_reason,(unsigned long long)tracker.room_epoch,(unsigned long long)tracker.roster.epoch,snap.slot,snap.mask,snap.ped_mask);
 for(unsigned i=0;i<32;i++)fprintf(f,"%s%llu",i?",":"",(unsigned long long)tracker.roster.generation[i]);
 fputs("]}\n",f);fclose(f);}
 if(ticks<7200)dispatch_after_f(dispatch_time(0,500000000LL),dispatch_get_main_queue(),0,sample);
}
__attribute__((constructor)) static void init(void){
 const char *home=getenv("HOME");if(!home)return;
 int n=snprintf(path,sizeof(path),"%s/Documents/RP14SessionProbe.jsonl",home);if(n<0||(size_t)n>=sizeof(path))return;
 FILE*f=fopen(path,"w");if(!f)return;int ok=image_ok();fprintf(f,"{\"probe\":7,\"uuid_ok\":%d}\n",ok);fclose(f);if(!ok)return;
 slide=_dyld_get_image_vmaddr_slide(0);if(slide<0)return;
 dispatch_after_f(dispatch_time(0,2000000000LL),dispatch_get_main_queue(),0,sample);
}
