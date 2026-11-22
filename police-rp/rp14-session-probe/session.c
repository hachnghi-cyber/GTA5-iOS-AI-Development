#include "session.h"
#define SESSION_ROOT 0x103263d60ULL
static int readfield(const RReader*r,uint64_t base,uint64_t offset,void*out,size_t n){
 return base && base<=UINT64_MAX-offset && base+offset<=UINT64_MAX-n && r->read(r->ctx,base+offset,out,n);
}
static int pointer(uint64_t p){return p>=0x1000 && !(p&7);}
static int established(uint32_t v){return (v&~1U)==2U;}
static int same(const SSession*a,const SSession*b){return a->root==b->root&&a->primary==b->primary&&a->id==b->id;}
int rp14_session(const RReader*r,SSession*out){
 *out=(SSession){0};
 if(!r||!r->read)return 10;
 SSession s={0};uint64_t transition=0;uint32_t mainstate=0,rlstate=0,transstate=0;
 if(!readfield(r,SESSION_ROOT,r->slide,&s.root,8)||!pointer(s.root))return 11;
 if(!readfield(r,s.root,0x1864c,&mainstate,4)||mainstate!=5)return 12;
 if(!readfield(r,s.root,0x20,&s.primary,8)||!pointer(s.primary)||!readfield(r,s.primary,0xb0,&rlstate,4)||!established(rlstate)||!readfield(r,s.primary,0x5c8,&s.id,8)||!s.id)return 13;
 if(!readfield(r,s.root,0x28,&transition,8))return 14;
 if(transition&&(!pointer(transition)||!readfield(r,transition,0xb0,&transstate,4)||established(transstate)))return 14;
 *out=s;return 0;
}
int rp14_session_roster(const RReader*r,SSession*out,RSnapshot*s,int*reason){
 SSession a={0},b={0};*out=(SSession){0};*s=(RSnapshot){0};s->slot=-1;
 if((*reason=rp14_session(r,&a)))return 0;
 if(!rp14_roster(r,s)){*reason=16;return 0;}
 if((*reason=rp14_session(r,&b))||!same(&a,&b)){if(!*reason)*reason=15;*s=(RSnapshot){0};s->slot=-1;return 0;}
 *out=b;return 1;
}
void rp14_session_track(STracker*t,const SSession*s,const RSnapshot*r,int valid){
 if(!valid){if(t->active)++t->room_epoch;t->active=0;t->session=(SSession){0};rp14_track(&t->roster,r,0);return;}
 if(!t->active||!same(&t->session,s)){++t->room_epoch;t->roster.valid=0;}
 t->active=1;t->session=*s;rp14_track(&t->roster,r,1);
}
