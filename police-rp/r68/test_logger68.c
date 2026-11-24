#define _POSIX_C_SOURCE 200809L
#include "observer65.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
void rp68_observe(unsigned source);
unsigned rp68_test_state(void);
static void *tick(void *p){(void)p;for(int i=0;i<1000;i++){rp68_observe(RP65_TICK);rp68_observe(RP65_RX);}return NULL;}
int main(int argc,char **argv){
 assert(argc==2);char home[]="/tmp/rp68-XXXXXX";assert(mkdtemp(home));assert(!setenv("HOME",home,1));
 char docs[256],path[512];snprintf(docs,sizeof docs,"%s/Documents",home);assert(!mkdir(docs,0700));snprintf(path,sizeof path,"%s/RP68-Thread-%ld.log",docs,(long)getpid());
 int collision=!strcmp(argv[1],"collision"),missing=!strcmp(argv[1],"missing");
 if(collision){FILE *f=fopen(path,"w");assert(f);assert(fputs("preserve\n",f)>=0);assert(!fclose(f));}
 if(missing)assert(!rmdir(docs));
 rp68_observe(0);rp68_observe(RP65_RX);assert(!rp68_test_state());
 pthread_t t[8];for(int i=0;i<8;i++)assert(!pthread_create(t+i,NULL,tick,NULL));for(int i=0;i<8;i++)assert(!pthread_join(t[i],NULL));
 struct timespec delay={0,1000000};for(int i=0;i<5000&&rp68_test_state()==1;i++)nanosleep(&delay,NULL);
 assert(rp68_test_state()==(collision||missing?3u:2u));
 RP65Snapshot s;assert(rp65_snapshot(&s)&&s.ticks==8000&&s.rx==8001&&!s.contended);
 if(!missing){FILE *f=fopen(path,"r");assert(f);char line[512];assert(fgets(line,sizeof line,f));if(collision){assert(!strcmp(line,"preserve\n")&&!fgets(line,sizeof line,f));}else{
 assert(!strcmp(line,"RP68 schema=1 diagnostic-only snapshot=nontransactional\n"));for(unsigned i=0;i<4;i++){unsigned sample;assert(fgets(line,sizeof line,f)&&sscanf(line,"sample=%u",&sample)==1&&sample==i);}assert(!fgets(line,sizeof line,f));struct stat st;assert(!stat(path,&st)&&!(st.st_mode&077));}
 fclose(f);assert(!unlink(path));assert(!rmdir(docs));}
 assert(!rmdir(home));printf("PASS %s; single startup, 16001 observations, state=%u\n",argv[1],rp68_test_state());return 0;
}
