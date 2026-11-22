#include "roster.h"
#define GAME_MGR 0x10286a540ULL
#define RAGE_MGR 0x10359b860ULL
#define TABLE_MGR 0x103ad8580ULL
#define ONLINE_FLAG 0x103263d31ULL
#define SESSION_FLAG 0x1036ad695ULL
static int get(const RReader*r,uint64_t p,void*out,size_t n){return p && n && p<=UINT64_MAX-n && r->read(r->ctx,p,out,n);}
static int field(const RReader*r,uint64_t p,uint64_t o,void*out,size_t n){return p && p<=UINT64_MAX-o && get(r,p+o,out,n);}
static int ptr(const RReader*r,uint64_t p,uint64_t o,uint64_t*out){return field(r,p,o,out,8) && (!*out || ((*out&7)==0 && *out>=0x1000));}
static int once(const RReader*r,RSnapshot*s){
 s->reason=1;
 unsigned char online=0, session=0, slot=255; uint64_t gm=0,rm=0,local=0; uint32_t cap=0,cap2=0;
 if(!field(r,ONLINE_FLAG,r->slide,&online,1)||online!=1||!field(r,SESSION_FLAG,r->slide,&session,1)||session!=1)return 0;
 s->reason=2;
 if(!ptr(r,GAME_MGR,r->slide,&gm)||!ptr(r,RAGE_MGR,r->slide,&rm)||!gm||gm!=rm)return 0;
 if(r->slide>UINT64_MAX-TABLE_MGR)return 0;
 uint64_t table=TABLE_MGR+r->slide;
 s->reason=3;
 if(!field(r,gm,0x2a0,&cap,4)||!field(r,table,0x2a0,&cap2,4)||cap!=cap2||!cap||cap>32)return 0;
 s->reason=4;
 if(!ptr(r,gm,0x100,&local)||!local||!field(r,local,0x21,&slot,1)||slot>=cap)return 0;
 s->reason=5;
 s->manager=gm;s->slot=slot;
 for(unsigned i=0;i<cap;i++){
  uint64_t p=0,p2=0,info=0,ped=0;unsigned char idx=255;
  if(!ptr(r,gm,0x1a0+i*8,&p)||!ptr(r,table,0x1a0+i*8,&p2)||p!=p2)return 0;
  if(!p)continue;
  if(!field(r,p,0x21,&idx,1)||idx!=i)return 0;
  if(!ptr(r,p,0xa0,&info)||(info&&!ptr(r,info,0x358,&ped)))return 0;
  s->player[i]=p;s->ped[i]=ped;s->mask|=1U<<i;if(ped)s->ped_mask|=1U<<i;
 }
 s->reason=6;
 if(s->player[slot]!=local || !s->ped[slot])return 0;
 s->reason=0;return 1;
}
static int same(const RSnapshot*a,const RSnapshot*b){
 if(a->manager!=b->manager||a->slot!=b->slot||a->mask!=b->mask||a->ped_mask!=b->ped_mask)return 0;
 for(unsigned i=0;i<32;i++)if(a->player[i]!=b->player[i]||a->ped[i]!=b->ped[i])return 0;
 return 1;
}
int rp14_roster(const RReader*r,RSnapshot*out){
 RSnapshot a={0},b={0}; *out=(RSnapshot){0};out->slot=-1;
 if(!r||!r->read){out->reason=8;return 0;}
 if(!once(r,&a)){out->reason=a.reason;return 0;}
 if(!once(r,&b)){out->reason=b.reason;return 0;}
 if(!same(&a,&b)){out->reason=7;return 0;}
 *out=b;return 1;
}
void rp14_track(RTracker*t,const RSnapshot*s,int valid){
 ++t->sample;
 if(!valid){if(t->valid)++t->epoch;t->valid=0;return;}
 if(!t->valid||t->previous.manager!=s->manager||t->previous.slot!=s->slot||t->previous.player[s->slot]!=s->player[s->slot]||t->previous.ped[s->slot]!=s->ped[s->slot]){
  ++t->epoch;for(unsigned i=0;i<32;i++)if(s->player[i])++t->generation[i];
 }else for(unsigned i=0;i<32;i++)if(t->previous.player[i]!=s->player[i]||t->previous.ped[i]!=s->ped[i])++t->generation[i];
 t->previous=*s;t->valid=1;
}
