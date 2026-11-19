#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE 1
#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#ifndef PATH_MAX
#define PATH_MAX 4096
#endif
#define TARGET "RPV08_pose.bin"
#define MAX_DEPTH 5
#define MAX_ENTRIES 1600
#define MAX_LOG_SIZE 32768
static atomic_int exiting = 0;
static char logpath[PATH_MAX], cached[PATH_MAX];
static int logged_missing=0, logged_file=0, logged_bad=0, logged_live=0;
static int have_seq=0;
static uint32_t last_seq=0;

static uint32_t load32(const unsigned char *x) {
    return (uint32_t)x[0] | ((uint32_t)x[1]<<8) | ((uint32_t)x[2]<<16) | ((uint32_t)x[3]<<24);
}
static uint32_t crc44(const unsigned char *x) {
    uint32_t h=2166136261U;
    for (int i=0;i<44;i++) h=(h ^ x[i])*16777619U;
    return h;
}
static void logevent(const char *event, const char *detail) {
    if (!logpath[0]) return;
    int fd=open(logpath,O_WRONLY|O_APPEND|O_CREAT|O_NOFOLLOW,0600);
    if(fd<0) return;
    struct stat st;
    if(fstat(fd,&st)!=0||!S_ISREG(st.st_mode)||st.st_size>MAX_LOG_SIZE) {close(fd);return;}
    char line[512]; time_t now=time(NULL); struct tm t;
    gmtime_r(&now,&t);
    int n=snprintf(line,sizeof(line),"%04d-%02d-%02dT%02d:%02d:%02dZ [RP_V12] %s %s\n",
        t.tm_year+1900,t.tm_mon+1,t.tm_mday,t.tm_hour,t.tm_min,t.tm_sec,event,detail?detail:"");
    if(n>0&&(size_t)n<sizeof(line)) (void)write(fd,line,(size_t)n);
    close(fd);
}
static int checkframe(const char *path,uint32_t *seq) {
    int fd=open(path,O_RDONLY|O_NOFOLLOW);
    if(fd<0) return 0;
    struct stat st; unsigned char a[48],b[48];
    int ok=fstat(fd,&st)==0&&S_ISREG(st.st_mode)&&st.st_size==48;
    if(ok) {
        if(read(fd,a,48)!=48||lseek(fd,0,SEEK_SET)!=0||
           read(fd,b,48)!=48||memcmp(a,b,48)) ok=0;
    }
    close(fd);
    if(!ok) return -1;
    if(memcmp(a,"RPF8",4)||a[4]!=8||a[5]!=0||a[6]!=48||a[7]!=0||
       load32(a+12)!=2||load32(a+40)!=0x08112026U||
       crc44(a)!=load32(a+44)) return -1;
    *seq=load32(a+8);
    if(!*seq||!load32(a+16)||load32(a+16)==UINT32_MAX) return -1;
    return 1;
}
static int walk(const char *dir,int depth,int *budget,char *out) {
    if(depth>MAX_DEPTH||!*budget) return 0;
    DIR *d=opendir(dir); if(!d) return 0;
    struct dirent *e; int found=0;
    while(*budget>0&&(e=readdir(d))) {
        if(!strcmp(e->d_name,".")||!strcmp(e->d_name,".."))continue;
        --(*budget);
        char path[PATH_MAX];
        int n=snprintf(path,sizeof(path),"%s/%s",dir,e->d_name);
        if(n<=0||n>=(int)sizeof(path))continue;
        struct stat st;
        if(lstat(path,&st)||S_ISLNK(st.st_mode))continue;
        if(!strcmp(e->d_name,TARGET)&&S_ISREG(st.st_mode)) {
            snprintf(out,PATH_MAX,"%s",path); found=1;break;
        }
        if(S_ISDIR(st.st_mode)&&depth<MAX_DEPTH&&walk(path,depth+1,budget,out)) {
            found=1;break;
        }
    }
    closedir(d); return found;
}
static int findpose(const char *home,char *out) {
    const char *roots[]={"Documents","Library","tmp"};
    int budget=MAX_ENTRIES;
    for(int i=0;i<3;i++) {
        char path[PATH_MAX];
        int n=snprintf(path,sizeof(path),"%s/%s",home,roots[i]);
        if(n<=0||n>=(int)sizeof(path))continue;
        if(walk(path,0,&budget,out))return 1;
    }
    return 0;
}
static void *worker(void *ignored) {
    (void)ignored;
    const char *home=getenv("HOME");
    if(!home||!*home||strlen(home)>PATH_MAX-64)return NULL;
    snprintf(logpath,sizeof(logpath),"%s/Documents/RPBridgeProbe_v12.log",home);
    logevent("DYLIB_LOADED","read_only=1 no_network=1");
    for(int i=0;i<600&&!atomic_load(&exiting);i++) {
        char path[PATH_MAX]="";
        if(cached[0]&&access(cached,R_OK)==0)snprintf(path,sizeof(path),"%s",cached);
        if(!path[0]&&findpose(home,path))snprintf(cached,sizeof(cached),"%s",path);
        if(!path[0]) {
            if(!logged_missing) {logevent("FILE_NOT_FOUND",TARGET);logged_missing=1;}
        } else {
            if(!logged_file) {logevent("FILE_FOUND","no_coordinates_logged=1");logged_file=1;}
            uint32_t seq=0;int valid=checkframe(path,&seq);
            if(valid!=1) {
                if(!logged_bad) {logevent("INVALID_FRAME","format_or_crc");logged_bad=1;}
            } else if(!have_seq) {
                have_seq=1;last_seq=seq;logevent("POSE_FIRST_FRAME","awaiting_update=1");
            } else if(seq>last_seq) {
                if(!logged_live) {
                    char msg[128];snprintf(msg,sizeof(msg),"old=%u new=%u",last_seq,seq);
                    logevent("POSE_LIVE",msg);logged_live=1;
                }
                last_seq=seq;
            }
        }
        for(int j=0;j<2&&!atomic_load(&exiting);j++)sleep(1);
    }
    logevent("PROBE_EXIT","game_unmodified=1");
    return NULL;
}
__attribute__((constructor)) static void rp_init(void) {
    pthread_t thread;
    if(!pthread_create(&thread,NULL,worker,NULL))pthread_detach(thread);
}
__attribute__((destructor)) static void rp_fini(void) {atomic_store(&exiting,1);}
