/*
 * GTA5Port v2.0.0 Story Mode Vietnamese installer.
 * Minimal C, no Apple SDK headers needed at compile time. Does not alter Online.
 * Experimental: on-device loader and RPF override behavior are unverified.
 */
#include <stdint.h>
#include <stddef.h>
#if !defined(__APPLE__)
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pthread.h>
#else
extern int open(const char *, int, ...);
extern int close(int);
extern long pread(int, void *, unsigned long, long long);
extern long read(int, void *, unsigned long);
extern long write(int, const void *, unsigned long);
extern long lseek(int, long long, int);
extern int access(const char *, int);
extern int mkdir(const char *, unsigned short);
extern int unlink(const char *);
extern int rename(const char *, const char *);
extern void *malloc(unsigned long);
extern void free(void *);
extern char *realpath(const char *, char *);
extern int snprintf(char *, unsigned long, const char *, ...);
extern unsigned long strlen(const char *);
extern void *memcpy(void *, const void *, unsigned long);
extern int memcmp(const void *, const void *, unsigned long);
extern int strcmp(const char *, const char *);
extern int strncmp(const char *, const char *, unsigned long);
extern char *getenv(const char *);
extern int _NSGetExecutablePath(char *, unsigned int *);
typedef void *pthread_t;
extern int pthread_create(pthread_t *, const void *, void *(*)(void *), void *);
extern int pthread_detach(pthread_t);
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 0x200
#define O_EXCL 0x800
#define O_NOFOLLOW 0x100
#define O_DIRECTORY 0x100000
#define O_TRUNC 0x400
#define SEEK_END 2
#define F_OK 0
#endif

#define PG_MAX_ENTRIES 1300
#define PG_MAX_FILESIZE (64U*1024U*1024U)
#define PG_MAX_INDEX (4U*1024U*1024U)
#define PG_MAX_PATH 128
#define PG_ROOT_NAME "Mods"
#define PG_MARKER ".mugoat_story_v200_installed"
#define PG_MARKER_TEXT "PGVI-V200-ACCENTED-R3\n"
#define PG_MOD_DISPLAY "Việt hoá Cốt truyện"
#define PG_MOD_DISPLAY_OFF "Việt hoá Cốt truyện.off"
#define PG_SEEDED ".pg_story_vietnamese_r5_seeded"
#define PG_SEEDED_TEXT "PGVI-V200-STORY-R5\n"
#define PG_TEMP_DIR ".pg_story_vietnamese_r5_stage"
#define PG_DIAG_FILE "PGVI_Status.log"
#define PG_ACTIVATED_R6 ".pg_story_vietnamese_r6_activated"
#define PG_ACTIVATED_TEXT "PGVI-V200-AUTOON-R6\n"

struct Item { char name[PG_MAX_PATH]; uint64_t off,size; };
struct P { const unsigned char *p, *end; };

static void space(struct P *s) {
  while(s->p<s->end && (*s->p==' ' || *s->p=='\t' || *s->p=='\n' || *s->p=='\r'))++s->p;
}
static int eat(struct P *s,unsigned char c) {
  space(s);if(s->p>=s->end || *s->p!=c)return 0;++s->p;return 1;
}
static int number(struct P *s,uint64_t *out) {
  uint64_t x=0;int found=0;space(s);
  while(s->p<s->end && *s->p>='0' && *s->p<='9') {
    unsigned v=*s->p++-'0';
    if(x>(UINT64_MAX-v)/10)return 0;
    x=x*10+v;found=1;
  }
  *out=x;return found;
}
static int safe_name(const char *s) {
  static const char *fonts[]={
    "common/data/ui/fontmap.xml",
    "x64/data/cdimages/scaleform_frontend.rpf/font_lib_editor.gfx",
    "x64/data/cdimages/scaleform_frontend.rpf/font_lib_sc.gfx",
    "x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.gfx",
    "x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.ytd"
  };
  for(unsigned i=0;i<5;i++)if(strcmp(s,fonts[i])==0)return 1;
  const char *p1="x64/data/lang/american.rpf/";
  const char *p2="x64/data/lang/american_REL.rpf/";
  unsigned n1=(unsigned)strlen(p1),n2=(unsigned)strlen(p2);
  const char *name=0;
  if(strncmp(s,p1,n1)==0)name=s+n1;
  else if(strncmp(s,p2,n2)==0)name=s+n2;
  if(!name || !*name)return 0;
  unsigned n=(unsigned)strlen(name);
  if(n<=5 || strcmp(name+n-5,".gxt2")!=0)return 0;
  for(unsigned i=0;i<n;i++)if(name[i]=='/' || name[i]=='\\' || name[i]==':')return 0;
  return 1;
}
static int quoted_name(struct P *s,char *out) {
  if(!eat(s,'"'))return 0;
  unsigned n=0;
  while(s->p<s->end && *s->p!='"') {
    char c=(char)*s->p++;
    if(n+1>=PG_MAX_PATH || c=='\\' ||
       (c=='.' && s->p<s->end && *s->p=='.'))return 0;
    if(!((c>='A'&&c<='Z') || (c>='a'&&c<='z') ||
         (c>='0'&&c<='9') || c=='/' || c=='.' || c=='-' || c=='_'))return 0;
    out[n++]=c;
  }
  if(!eat(s,'"'))return 0;
  out[n]=0;return safe_name(out);
}
static int parse(const unsigned char *index,unsigned n,uint64_t payload,struct Item *out,int *count) {
  struct P s={index,index+n};uint64_t last=0;int total=0;
  if(!eat(&s,'['))return 0;
  while(1) {
    if(total>=PG_MAX_ENTRIES || !eat(&s,'['))return 0;
    struct Item *e=&out[total];
    if(!quoted_name(&s,e->name) || !eat(&s,',') ||
       !number(&s,&e->off) || !eat(&s,',') ||
       !number(&s,&e->size) || !eat(&s,']'))return 0;
    if(e->off!=last || e->size>payload-last)return 0;
    last+=e->size;
    for(int i=0;i<total;i++)if(strcmp(out[i].name,e->name)==0)return 0;
    total++;
    if(eat(&s,']'))break;
    if(!eat(&s,','))return 0;
  }
  space(&s);
  if(s.p!=s.end || last!=payload || total!=1221)return 0;
  *count=total;return 1;
}
static int cat(char *out,unsigned cap,const char *base,const char *tail) {
  unsigned a=(unsigned)strlen(base),b=(unsigned)strlen(tail);
  if(a+1+b+1>cap)return 0;
  memcpy(out,base,a);out[a]='/';memcpy(out+a+1,tail,b+1);return 1;
}
static int full_read(int fd,void *buf,unsigned n,uint64_t off) {
  unsigned char *p=(unsigned char *)buf;
  while(n) {
    unsigned part=n>65536?65536:n;
    long k=pread(fd,p,part,(long long)off);
    if(k<=0)return 0;
    p+=(unsigned)k;off+=(unsigned)k;n-=(unsigned)k;
  }
  return 1;
}
static int write_all(int fd,const void *data,unsigned n) {
  const unsigned char *p=(const unsigned char *)data;
  while(n) {
    long k=write(fd,p,n);if(k<=0)return 0;
    p+=(unsigned)k;n-=(unsigned)k;
  }
  return 1;
}
static int ensure_dir(char *base) {
  unsigned n=(unsigned)strlen(base);
  for(unsigned i=1;i<=n;i++) {
    if(base[i]!='/' && base[i]!=0)continue;
    char ch=base[i];base[i]=0;
    if(mkdir(base,0755)!=0) {
      int fd=open(base,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
      if(fd<0) {base[i]=ch;return 0;}
      close(fd);
    }
    base[i]=ch;
  }
  return 1;
}
static int marker_ok(const char *docs) {
  char path[4096],x[64];
  if(!cat(path,sizeof(path),docs,PG_MARKER))return 0;
  int fd=open(path,O_RDONLY|O_NOFOLLOW);
  if(fd<0)return 0;
  long k=read(fd,x,sizeof(x));close(fd);
  return k==(long)strlen(PG_MARKER_TEXT) && memcmp(x,PG_MARKER_TEXT,(unsigned)k)==0;
}
static int existing_matches(int fd,const char *mods,const struct Item *e,uint64_t begin) {
  char path[4096];unsigned char expected[65536],actual[65536];
  if(!cat(path,sizeof(path),mods,e->name))return 0;
  int file=open(path,O_RDONLY|O_NOFOLLOW);
  if(file<0)return 0;
  long long size=lseek(file,0,SEEK_END);
  int ok=(size>=0 && (uint64_t)size==e->size);
  uint64_t done=0;
  while(ok && done<e->size) {
    unsigned n=(unsigned)((e->size-done)>sizeof(actual)?sizeof(actual):(e->size-done));
    if(!full_read(fd,expected,n,begin+e->off+done) ||
       !full_read(file,actual,n,done) || memcmp(expected,actual,n)!=0)ok=0;
    done+=n;
  }
  close(file);return ok;
}
static int check_parent_and_write(int fd,const char *mods,const struct Item *e,uint64_t begin) {
  char path[4096],par[4096];unsigned char buf[65536];
  if(!cat(path,sizeof(path),mods,e->name))return 0;
  unsigned len=(unsigned)strlen(path);int i=(int)len-1;
  while(i>0 && path[i]!='/')i--;
  if(i<=0)return 0;
  memcpy(par,path,(unsigned)i);par[i]=0;
  if(!ensure_dir(par))return 0;
  int to=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0644);
  if(to<0)return 0;
  int ok=1;uint64_t done=0;
  while(done<e->size) {
    unsigned n=(unsigned)((e->size-done)>sizeof(buf)?sizeof(buf):(e->size-done));
    if(!full_read(fd,buf,n,begin+e->off+done) || !write_all(to,buf,n)) {
      ok=0;break;
    }
    done+=n;
  }
  if(close(to)!=0)ok=0;
  if(!ok)unlink(path);
  return ok;
}
/* State marker survives deliberate deletion from the existing Mods UI. */
static int state_marker_ok(const char *docs) {
    char p[4096],value[64];
    if(!cat(p,sizeof(p),docs,PG_SEEDED))return 0;
    int fd=open(p,O_RDONLY|O_NOFOLLOW);if(fd<0)return 0;
    long n=read(fd,value,sizeof(value));close(fd);
    return n==(long)strlen(PG_SEEDED_TEXT) && memcmp(value,PG_SEEDED_TEXT,(unsigned)n)==0;
}
static int write_state_marker(const char *docs) {
    char p[4096],tmp[4096];
    if(!cat(p,sizeof(p),docs,PG_SEEDED)||
       !cat(tmp,sizeof(tmp),docs,".pg_story_vietnamese_r5_writing"))return 0;
    int fd=open(tmp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if(fd<0)return 0;
    int ok=write_all(fd,PG_SEEDED_TEXT,(unsigned)strlen(PG_SEEDED_TEXT));
    if(close(fd)!=0)ok=0;
    if(ok&&rename(tmp,p)==0)return 1;
    unlink(tmp);return 0;
}
static int safe_directory(const char *p) {
    int fd=open(p,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if(fd>=0){close(fd);return 1;}
    return access(p,F_OK)==0?-1:0;
}
static int matches_pack(int pack,const char *root,struct Item *items,
                        int count,uint64_t begin) {
    for(int i=0;i<count;i++)
      if(!existing_matches(pack,root,&items[i],begin))return 0;
    return 1;
}
/* Delete only legacy R4 bytes identical to the supplied Vietnamese pack. */
static int cleanup_r4_files(int pack,const char *root,struct Item *items,
                            int count,uint64_t begin) {
    for(int i=0;i<count;i++) {
      char p[4096];if(!cat(p,sizeof(p),root,items[i].name))return 0;
      if(access(p,F_OK)!=0)continue;
      if(!existing_matches(pack,root,&items[i],begin))return 0;
      if(unlink(p)!=0)return 0;
    }
    return 1;
}
static int r6_activated(const char *docs) {
    char p[4096],x[64];
    if(!cat(p,sizeof(p),docs,PG_ACTIVATED_R6))return 0;
    int fd=open(p,O_RDONLY|O_NOFOLLOW);
    if(fd<0)return 0;
    long n=read(fd,x,sizeof(x));close(fd);
    return n==(long)strlen(PG_ACTIVATED_TEXT) &&
        memcmp(x,PG_ACTIVATED_TEXT,(unsigned)n)==0;
}
static int write_r6_activation(const char *docs) {
    char p[4096],tmp[4096];
    if(!cat(p,sizeof(p),docs,PG_ACTIVATED_R6) ||
       !cat(tmp,sizeof(tmp),docs,".pg_story_vietnamese_r6_writing"))return 0;
    int fd=open(tmp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if(fd<0)return 0;
    int ok=write_all(fd,PG_ACTIVATED_TEXT,(unsigned)strlen(PG_ACTIVATED_TEXT));
    if(close(fd)!=0)ok=0;
    if(ok && rename(tmp,p)==0)return 1;
    unlink(tmp);return 0;
}
/* Write a small deterministic status file, without leaking app/container paths.
 * Failure to record diagnostics must not block Story Mode.
 */
static void report_status(const char *docs,int code,int enabled,int disabled,
                          int wasSeeded,int hadLegacy) {
    char p[4096],line[256];
    if(!cat(p,sizeof(p),docs,PG_DIAG_FILE))return;
    int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);
    if(fd<0)return;
    int count=snprintf(line,sizeof(line),
      "PGVI Story R6\nresult=%d\nmod_on=%d\nmod_off=%d\nr5_seeded=%d\nr4_marker=%d\n"
      "engine_overlay=unverified\nnote=RPF-internal mods require local game files\n",
      code,enabled,disabled,wasSeeded,hadLegacy);
    if(count>0 && count<(int)sizeof(line))write_all(fd,line,(unsigned)count);
    close(fd);
}
/* A top-level named Mods directory becomes an existing UISwitch entry.
 * The .off suffix means OFF; we seed OFF and preserve subsequent choices.
 */
int PGVietHoaInstall(const char *bundleNvp,const char *docs) {
    if(!bundleNvp||!docs)return -1;
    /* Canonicalize iOS /var symlink in the trusted sandbox prefix. Below
       Documents we still reject symlinked Mods directories. */
    char canonicalDocs[4096];
    if(!realpath(docs,canonicalDocs))return -15;
    docs=canonicalDocs;
    int fd=-1,result=-1,count=0;
    unsigned char head[16];unsigned char *index=0;
    struct Item *items=0;
    char mods[4096],oldMarker[4096],seedMarker[4096];
    char on[4096],off[4096],stage[4096];
    if(!cat(mods,sizeof(mods),docs,PG_ROOT_NAME)||
       !cat(oldMarker,sizeof(oldMarker),docs,PG_MARKER)||
       !cat(seedMarker,sizeof(seedMarker),docs,PG_SEEDED)||
       !cat(on,sizeof(on),mods,PG_MOD_DISPLAY)||
       !cat(off,sizeof(off),mods,PG_MOD_DISPLAY_OFF)||
       !cat(stage,sizeof(stage),docs,PG_TEMP_DIR))return -1;
    int seeded=state_marker_ok(docs);
    if(!seeded && access(seedMarker,F_OK)==0){report_status(docs,-2,0,0,0,0);return -2;}
    int legacy=marker_ok(docs);
    if(!legacy && access(oldMarker,F_OK)==0){report_status(docs,-2,0,0,seeded,0);return -2;}
    fd=open(bundleNvp,O_RDONLY|O_NOFOLLOW);if(fd<0){report_status(docs,-3,0,0,seeded,legacy);return -3;}
    long long sz=lseek(fd,0,SEEK_END);
    if(sz<=16||sz>PG_MAX_FILESIZE+PG_MAX_INDEX+16LL||
       !full_read(fd,head,16,0)||memcmp(head,"NOVAPAK1",8))goto done;
    uint64_t idx=0;
    for(int i=0;i<8;i++)idx|=(uint64_t)head[8+i]<<(8*i);
    if(!idx||idx>PG_MAX_INDEX||idx+16>=(uint64_t)sz)goto done;
    index=(unsigned char *)malloc((unsigned long)idx);
    items=(struct Item *)malloc(sizeof(struct Item)*PG_MAX_ENTRIES);
    if(!index||!items||!full_read(fd,index,(unsigned)idx,16))goto done;
    if(!parse(index,(unsigned)idx,(uint64_t)sz-idx-16,items,&count))goto done;
    free(index);index=0;
    uint64_t begin=16+idx;
    int isOn=safe_directory(on),isOff=safe_directory(off);
    int activated=r6_activated(docs);
    if(isOn<0||isOff<0||(isOn&&isOff)){result=-6;goto done;}
    const char *live=isOn?on:isOff?off:0;
    if(seeded) {
        if(!live){result=0;goto done;} /* Removed deliberately by user */
        if(!matches_pack(fd,live,items,count,begin)){result=-4;goto done;}
        /* One-time R5->R6 activation: restore VI by default, keep UISwitch.
         * Future user OFF choices are preserved by the R6 activation marker. */
        if(!activated) {
            if(isOff && rename(off,on)!=0){result=-16;goto done;}
            if(!write_r6_activation(docs)){result=-17;goto done;}
        }
        result=0;goto done;
    }
    if(live) {
        if(!matches_pack(fd,live,items,count,begin)){result=-4;goto done;}
    } else {
        if(safe_directory(stage)!=0){result=-7;goto done;}
        for(int i=0;i<count;i++) {
            char p[4096];
            if(!cat(p,sizeof(p),mods,items[i].name))goto done;
            if(access(p,F_OK)==0&&!legacy){result=-8;goto done;}
        }
        if(legacy&&!matches_pack(fd,mods,items,count,begin)){result=-9;goto done;}
        char root[4096];
        if(strlen(mods)+1>sizeof(root)||strlen(stage)+1>sizeof(root))goto done;
        memcpy(root,mods,strlen(mods)+1);
        if(!ensure_dir(root))goto done;
        memcpy(root,stage,strlen(stage)+1);
        if(!ensure_dir(root))goto done;
        for(int i=0;i<count;i++) {
            if(!check_parent_and_write(fd,stage,&items[i],begin)){result=-10;goto done;}
        }
        if(rename(stage,on)!=0){result=-11;goto done;}
        live=on;
    }
    if(legacy) {
        if(!cleanup_r4_files(fd,mods,items,count,begin)){result=-12;goto done;}
        if(unlink(oldMarker)!=0){result=-13;goto done;}
    }
    if(!write_state_marker(docs)){result=-14;goto done;}
    if(!write_r6_activation(docs)){result=-17;goto done;}
    result=0;
done:
    report_status(docs,result,safe_directory(on)==1,safe_directory(off)==1,seeded,legacy);
    if(fd>=0)close(fd);
    if(index)free(index);
    if(items)free(items);
    return result;
}
#if defined(__APPLE__)
static void *run_install(void *arg) {
  (void)arg;char exe[4096];unsigned cap=(unsigned)sizeof(exe);
  const char *home=getenv("HOME");
  if(!home || _NSGetExecutablePath(exe,&cap)!=0)return 0;
  unsigned n=(unsigned)strlen(exe);
  while(n && exe[n-1]!='/')n--;
  if(!n)return 0;
  exe[n-1]=0;
  char pack[4096],docs[4096];
  if(!cat(pack,sizeof(pack),exe,"VietnameseAccented.nvp") ||
     !cat(docs,sizeof(docs),home,"Documents"))return 0;
  (void)PGVietHoaInstall(pack,docs);
  return 0;
}
__attribute__((constructor)) static void boot(void) {
  pthread_t th=0;
  /* Avoid blocking app start while copying 1,221 small resource files. */
  if(pthread_create(&th,0,run_install,0)==0)pthread_detach(th);
}
#endif
