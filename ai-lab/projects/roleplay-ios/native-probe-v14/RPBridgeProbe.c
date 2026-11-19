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
#define MAX_ENTRIES 3000
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
    int n=snprintf(line,sizeof(line),"%04d-%02d-%02dT%02d:%02d:%02dZ [RP_V14] %s %s\n",
        t.tm_year+1900,t.tm_mon+1,t.tm_mday,t.tm_hour,t.tm_min,t.tm_sec,event,detail?detail:"");
    if(n>0&&(size_t)n<sizeof(line)){
        size_t sent=0;
        while(sent<(size_t)n){
            ssize_t wrote=write(fd,line+sent,(size_t)n-sent);
            if(wrote<=0)break;
            sent+=(size_t)wrote;
        }
    }
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

/* No symlink following. Do not expose the private full path in logs. */
static int check_direct(const char *dir,char *out) {
    char name[PATH_MAX];
    int n=snprintf(name,sizeof(name),"%s/%s",dir,TARGET);
    if(n<=0||n>=(int)sizeof(name))return 0;
    struct stat st;
    if(lstat(name,&st)||S_ISLNK(st.st_mode)||!S_ISREG(st.st_mode))return 0;
    snprintf(out,PATH_MAX,"%s",name);
    return 1;
}

/* NativeAssets.m / ModInstaller.swift: default mods = Documents/Mods.
   Check paths before broad recursion, which may exhaust the entry budget. */
static int find_mods(const char *home,char *out,const char **bucket,int *visited) {
    char mods[PATH_MAX];
    int n=snprintf(mods,sizeof(mods),"%s/Documents/Mods",home);
    if(n<=0||n>=(int)sizeof(mods))return 0;
    if(check_direct(mods,out)){*bucket="mods_root";return 1;}
    DIR *d=opendir(mods);
    if(!d)return 0;
    struct dirent *e;int count=0,found=0;
    while(count<512&&(e=readdir(d))){
        if(!strcmp(e->d_name,".")||!strcmp(e->d_name,".."))continue;
        ++count;
        char p[PATH_MAX];
        int m=snprintf(p,sizeof(p),"%s/%s",mods,e->d_name);
        if(m<=0||m>=(int)sizeof(p))continue;
        struct stat st;
        if(lstat(p,&st)||S_ISLNK(st.st_mode)||!S_ISDIR(st.st_mode))continue;
        if(check_direct(p,out)){found=1;*bucket="mods_child";break;}
    }
    closedir(d);
    *visited=count;
    if(found)return 1;
    int budget=MAX_ENTRIES;
    if(walk(mods,0,&budget,out)){
        *bucket="mods_tree";*visited+=MAX_ENTRIES-budget;return 1;
    }
    *visited+=MAX_ENTRIES-budget;
    return 0;
}
static int findpose(const char *home,const char *cwd,char *out,const char **bucket,int *visited) {
    if(find_mods(home,out,bucket,visited))return 1;
    if(cwd&&*cwd&&check_direct(cwd,out)){*bucket="cwd";return 1;}
    if(check_direct(home,out)){*bucket="home_root";return 1;}
    const char *roots[]={"Documents","Library","tmp"};
    for(int i=0;i<3;i++){
        char path[PATH_MAX];
        int n=snprintf(path,sizeof(path),"%s/%s",home,roots[i]);
        if(n<=0||n>=(int)sizeof(path))continue;
        int budget=MAX_ENTRIES;
        if(walk(path,0,&budget,out)){
            *bucket=roots[i];*visited+=MAX_ENTRIES-budget;return 1;
        }
        *visited+=MAX_ENTRIES-budget;
    }
    return 0;
}
static void *worker(void *ignored) {
    (void)ignored;
    const char *home=getenv("HOME");
    if(!home||!*home||strlen(home)>PATH_MAX-64)return NULL;
    snprintf(logpath,sizeof(logpath),"%s/Documents/RPBridgeProbe_v14.log",home);
    char cwd[PATH_MAX]="";
    int cwd_ok=getcwd(cwd,sizeof(cwd))!=NULL;
    const char *relation="unavailable";
    if(cwd_ok){
        size_t hlen=strlen(home);
        relation=(!strncmp(cwd,home,hlen) && (cwd[hlen]=='/'||cwd[hlen]=='\0'))?"inside_home":"outside_home";
    }
    logevent("DYLIB_LOADED","read_only=1 no_network=1 version=v1.4");
    logevent("CWD_CLASS",relation);
    char mods[PATH_MAX];
    int ml=snprintf(mods,sizeof(mods),"%s/Documents/Mods",home);
    DIR *md=(ml>0&&ml<(int)sizeof(mods))?opendir(mods):NULL;
    logevent("MODS_ROOT",md?"readable=1":"readable=0");
    if(md)closedir(md);
    for(int i=0;i<600&&!atomic_load(&exiting);i++) {
        char path[PATH_MAX]="";
        if(cached[0]&&access(cached,R_OK)==0)snprintf(path,sizeof(path),"%s",cached);
        const char *bucket="cached";int visited=0;
        if(!path[0]&&findpose(home,cwd_ok?cwd:NULL,path,&bucket,&visited)){
            snprintf(cached,sizeof(cached),"%s",path);
            char msg[100];snprintf(msg,sizeof(msg),"bucket=%s visited=%d",bucket,visited);
            logevent("FILE_SOURCE",msg);
        }
        if(i==15&&!path[0]){
            char msg[100];snprintf(msg,sizeof(msg),"cwd=%s visited=%d",relation,visited);
            logevent("SEARCH_30S",msg);
        }
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
#if defined(RP_FAST_TEST)
        struct timespec delay={.tv_sec=0,.tv_nsec=150000000L};
        nanosleep(&delay,NULL);
#else
        for(int j=0;j<2&&!atomic_load(&exiting);j++)sleep(1);
#endif
    }
    logevent("PROBE_EXIT","game_unmodified=1");
    return NULL;
}
__attribute__((constructor)) static void rp_init(void) {
    pthread_t thread;
    if(!pthread_create(&thread,NULL,worker,NULL))pthread_detach(thread);
}
__attribute__((destructor)) static void rp_fini(void) {atomic_store(&exiting,1);}
