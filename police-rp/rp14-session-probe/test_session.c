#include "session.h"
#include <stdio.h>
#include <assert.h>
#include <string.h>
typedef struct { uint64_t addr,value; size_t len; } Cell;
typedef struct {Cell c[256];unsigned n;unsigned reads;unsigned fail_after;unsigned session_reads;int torn;unsigned room_reads;int room_torn;} Mem;
static void set(Mem*m,uint64_t addr,uint64_t v,size_t len){for(unsigned i=0;i<m->n;i++)if(m->c[i].addr==addr){m->c[i]=(Cell){addr,v,len};return;}assert(m->n<256);m->c[m->n++]=(Cell){addr,v,len};}
static int rd(void*ctx,uint64_t a,void*out,size_t n){Mem*m=ctx; ++m->reads;if(a==0x103263d60 && ++m->room_reads==2 && m->room_torn){set(m,0x205c8,99,8);}if(a==0x1036ad695 && ++m->session_reads==2 && m->torn){set(m,0xd358,0x11000,8);}if(m->fail_after&&m->reads>=m->fail_after)return 0;for(unsigned i=0;i<m->n;i++)if(m->c[i].addr==a&&m->c[i].len==n){memcpy(out,&m->c[i].value,n);return 1;}return 0;}
#define SET(a,b,n) set(m,(a),(b),(n))
static void fixture(Mem*m){memset(m,0,sizeof(*m));SET(0x103263d31,1,1);SET(0x1036ad695,1,1);SET(0x10286a540,0x5000,8);SET(0x10359b860,0x5000,8);SET(0x52a0,32,4);SET(0x103ad8820,32,4);SET(0x5100,0x9000,8);for(unsigned i=0;i<32;i++){uint64_t p=i==0?0x9000:i==4?0xa000:0;SET(0x51a0+i*8,p,8);SET(0x103ad8720+i*8,p,8);}SET(0x9021,0,1);SET(0x90a0,0xb000,8);SET(0xb358,0xc000,8);SET(0xa021,4,1);SET(0xa0a0,0xd000,8);SET(0xd358,0xe000,8);}
static void room(Mem*m){fixture(m);SET(0x103263d60,0x30000,8);SET(0x4864c,5,4);SET(0x30020,0x20000,8);SET(0x30028,0,8);SET(0x200b0,2,4);SET(0x205c8,88,8);}
int main(void){Mem mm,*m=&mm;RReader r={rd,m,0};SSession x;RSnapshot s;STracker t={0};int why;
 room(m);assert(rp14_session_roster(&r,&x,&s,&why)&&x.id==88&&s.slot==0);rp14_session_track(&t,&x,&s,1);assert(t.room_epoch==1);puts("PASS stable session+roster");
 SET(0x205c8,89,8);assert(rp14_session_roster(&r,&x,&s,&why));rp14_session_track(&t,&x,&s,1);assert(t.room_epoch==2&&t.roster.epoch==2);puts("PASS room migration with same roster");
 SET(0x4864c,4,4);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==12);rp14_session_track(&t,&x,&s,0);assert(t.room_epoch==3&&!t.active);puts("PASS state not established");
 room(m);assert(rp14_session_roster(&r,&x,&s,&why));rp14_session_track(&t,&x,&s,1);assert(t.room_epoch==4);puts("PASS rejoin fresh epoch");
 SET(0x30028,0x50000,8);SET(0x500b0,3,4);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==14);puts("PASS transition established rejected");
 SET(0x500b0,0,4);assert(rp14_session_roster(&r,&x,&s,&why));puts("PASS inactive transition");
 SET(0x30028,0x50008,8);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==14);puts("PASS unreadable transition");
 room(m);SET(0x205c8,0,8);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==13);puts("PASS zero session id");
 room(m);SET(0x200b0,4,4);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==13);puts("PASS unestablished primary");
 room(m);SET(0x103263d60,0,8);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==11);puts("PASS null root");
 room(m);m->room_torn=1;assert(!rp14_session_roster(&r,&x,&s,&why)&&why==15&&s.slot==-1);puts("PASS room change between reads");
 room(m);SET(0x103ad8720+32,0,8);assert(!rp14_session_roster(&r,&x,&s,&why)&&why==16);puts("PASS divergent roster");
 assert(!rp14_session_roster(0,&x,&s,&why)&&why==10);puts("PASS null reader");
 fixture(m);RTracker rt={0};
 assert(rp14_roster(&r,&s)&&s.slot==0&&s.mask==17&&s.ped_mask==17);rp14_track(&rt,&s,1);assert(rt.epoch==1&&rt.generation[4]==1);puts("PASS roster local + remote");
 SET(0xd358,0xf000,8);assert(rp14_roster(&r,&s));rp14_track(&rt,&s,1);assert(rt.epoch==1&&rt.generation[4]==2);puts("PASS remote respawn observation");
 SET(0xb358,0x10000,8);assert(rp14_roster(&r,&s));rp14_track(&rt,&s,1);assert(rt.epoch==2);puts("PASS local respawn invalidates epoch");
 SET(0x1036ad695,0,1);assert(!rp14_roster(&r,&s));rp14_track(&rt,&s,0);assert(rt.epoch==3&&!rt.valid);puts("PASS leave invalidation");
 fixture(m);assert(rp14_roster(&r,&s));rp14_track(&rt,&s,1);assert(rt.epoch==4);puts("PASS rejoin new epoch");
 SET(0x10359b860,0x6000,8);assert(!rp14_roster(&r,&s));puts("PASS root mismatch");
 fixture(m);SET(0x52a0,33,4);assert(!rp14_roster(&r,&s));puts("PASS invalid capacity");
 fixture(m);SET(0x103ad8720+32,0,8);assert(!rp14_roster(&r,&s));puts("PASS divergent table");
 fixture(m);SET(0xa021,3,1);assert(!rp14_roster(&r,&s));puts("PASS invalid slot");
 fixture(m);SET(0xb358,0,8);assert(!rp14_roster(&r,&s));puts("PASS missing local ped");
 fixture(m);m->fail_after=90;assert(!rp14_roster(&r,&s)&&s.slot==-1&&s.mask==0);puts("PASS partial read fails closed");
 fixture(m);SET(0x51a0+32,0,8);SET(0x103ad8720+32,0,8);assert(rp14_roster(&r,&s)&&s.mask==1);rp14_track(&rt,&s,1);assert(rt.generation[4]>2);puts("PASS remote leaves");
 fixture(m);m->torn=1;assert(!rp14_roster(&r,&s)&&s.reason==7);puts("PASS torn snapshot rejected");
 return 0;}
