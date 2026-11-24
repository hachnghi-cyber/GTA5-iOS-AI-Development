#include "frame.h"
#include <string.h>
#include <stdio.h>
int parse_line(Frame *f,const char *line){
 const char *p=strstr(line,"[rp-r35] ");
 if(p){Frame q={0};int online=0;
 if(sscanf(p,"[rp-r35] ms=%u online=%d slot=%d alive=%d xyz_cm=%d,%d,%d mask=0x%x nearest=%d dist_cm=%d custom=0x%x",&q.ms,&online,&q.slot,&q.alive,&q.x,&q.y,&q.z,&q.mask,&q.target,&q.dist,&q.custom)==11 && online==1 && q.slot>=0&&q.slot<32&&(q.alive==0||q.alive==1)&&q.x>=-2000000&&q.x<=2000000&&q.y>=-2000000&&q.y<=2000000&&q.z>=-2000000&&q.z<=2000000&&q.target>=-1&&q.target<32&&q.target!=q.slot&&((q.target==-1&&q.dist==-1)||(q.target>=0&&q.dist>=0&&q.dist<=300))){q.valid=1;*f=q;return 1;} f->valid=0;return -1;}
 p=strstr(line,"[rp-r35-request] ");if(p){int s,t,d,a;if(f->valid&&(f->custom&128)&&sscanf(p,"[rp-r35-request] slot=%d target=%d dist_cm=%d alive=%d",&s,&t,&d,&a)==4&&s==f->slot&&t==f->target&&d==f->dist&&a==f->alive){f->pressed=1;return 2;}}return 0;
}
