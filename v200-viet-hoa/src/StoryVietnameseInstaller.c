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
static int finalize_marker(const char *docs) {
  char name[4096],tmp[4096];
  if(!cat(name,sizeof(name),docs,PG_MARKER) ||
     !cat(tmp,sizeof(tmp),docs,".mugoat_story_v200_pending"))return 0;
  int fd=open(tmp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
  if(fd<0)return 0;
  int ok=write_all(fd,PG_MARKER_TEXT,(unsigned)strlen(PG_MARKER_TEXT));
  if(close(fd)!=0)ok=0;
  if(ok && rename(tmp,name)==0)return 1;
  unlink(tmp);return 0;
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
int PGVietHoaInstall(const char *bundleNvp,const char *docs) {
  if(!bundleNvp || !docs)return -1;
  int fd=-1,result=-1,count=0;
  unsigned char head[16];unsigned char *index=0;struct Item *entries=0;
  char mods[4096],marker[4096];
  if(!cat(mods,sizeof(mods),docs,PG_ROOT_NAME) ||
     !cat(marker,sizeof(marker),docs,PG_MARKER))return -1;
  int has_marker=marker_ok(docs);
  if(!has_marker && access(marker,F_OK)==0)return -2;
  fd=open(bundleNvp,O_RDONLY|O_NOFOLLOW);if(fd<0)return -3;
  long long sz=lseek(fd,0,SEEK_END);
  if(sz<=16 || sz>PG_MAX_FILESIZE+PG_MAX_INDEX+16LL ||
     !full_read(fd,head,16,0) || memcmp(head,"NOVAPAK1",8))goto end;
  uint64_t index_size=0;
  for(int i=0;i<8;i++)index_size|=(uint64_t)head[8+i]<<(8*i);
  if(!index_size || index_size>PG_MAX_INDEX || index_size+16>=(uint64_t)sz)goto end;
  index=(unsigned char *)malloc((unsigned long)index_size);
  entries=(struct Item *)malloc(sizeof(struct Item)*PG_MAX_ENTRIES);
  if(!index || !entries || !full_read(fd,index,(unsigned)index_size,16))goto end;
  if(!parse(index,(unsigned)index_size,(uint64_t)sz-index_size-16,entries,&count))goto end;
  free(index);index=0;
  if(has_marker) {
    for(int i=0;i<count;i++)
      if(!existing_matches(fd,mods,&entries[i],16+index_size)) {
        result=-4;goto end;
      }
    result=0;goto end;
  }
  for(int i=0;i<count;i++) {
    char path[4096];
    if(!cat(path,sizeof(path),mods,entries[i].name) || access(path,F_OK)==0)goto end;
  }
  {char root[4096];
   if(strlen(mods)+1>sizeof(root))goto end;
   memcpy(root,mods,strlen(mods)+1);
   if(!ensure_dir(root))goto end;}
  int written=0;
  for(int i=0;i<count;i++) {
    if(!check_parent_and_write(fd,mods,&entries[i],16+index_size))goto rollback;
    written++;
  }
  if(!finalize_marker(docs))goto rollback;
  result=0;goto end;
rollback:
  for(int i=0;i<written;i++) {
    char path[4096];
    if(cat(path,sizeof(path),mods,entries[i].name))unlink(path);
  }
end:
  if(fd>=0)close(fd);
  if(index)free(index);
  if(entries)free(entries);
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
