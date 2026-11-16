/* Host-only regression of dyld allowlist, Mach-O UUID and RTLD_NOLOAD. */
#define _POSIX_C_SOURCE 200809L
#include "fake_dyld.h"
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
static uint32_t count=1;
static const char *name;
static struct { struct mach_header_64 h; struct uuid_command u; } image;
uint32_t _dyld_image_count(void) {return count;}
const char *_dyld_get_image_name(uint32_t i) {return i<count?name:NULL;}
const struct mach_header *_dyld_get_image_header(uint32_t i) {return i<count?(const struct mach_header *)&image:NULL;}
static void init_image(void) {
    memset(&image,0,sizeof(image));
    image.h.magic=MH_MAGIC_64;
    image.h.cputype=CPU_TYPE_ARM64;
    image.h.filetype=6;
    image.h.ncmds=1;
    image.h.sizeofcmds=24;
    image.u.cmd=LC_UUID;
    image.u.cmdsize=24;
    const uint8_t uuid[16]={0xF7,0x68,0xB7,0xB5,0xAD,0x75,0x39,0xF4,0x83,0xD3,0x8E,0x49,0x23,0x43,0x25,0xB5};
    memcpy(image.u.uuid,uuid,16);
}
int main(int argc,char **argv){
    assert(argc==3);
    name=argv[2];
    void *fixture=dlopen(name,RTLD_NOW|RTLD_GLOBAL);
    assert(fixture);
    void *probe=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if (!probe) {fprintf(stderr,"dlopen probe: %s\n",dlerror());return 2;}
    int (*entry)(void*,unsigned,void*)=NULL;
    *(void **)(&entry)=dlsym(probe,"DllMain");assert(entry);
    unsigned (*regs)(void)=NULL,(*unregs)(void)=NULL,(*waits)(void)=NULL;
    void (*(*getcb)(void))(void)=NULL;
    *(void **)(&regs)=dlsym(fixture,"fixture_registered");
    *(void **)(&unregs)=dlsym(fixture,"fixture_unregistered");
    *(void **)(&waits)=dlsym(fixture,"fixture_wait_calls");
    *(void **)(&getcb)=dlsym(fixture,"fixture_callback");
    assert(regs&&unregs&&waits&&getcb);
    init_image();
    image.u.uuid[0]^=1;
    assert(entry((void *)0x1234,1,NULL)==0);
    assert(regs()==0);
    image.u.uuid[0]^=1;
    count=2;
    assert(entry((void *)0x1234,1,NULL)==0);
    count=1;
    image.u.cmdsize=7;
    assert(entry((void *)0x1234,1,NULL)==0);
    image.u.cmdsize=24;
    image.h.sizeofcmds=1024*1024*3u;
    assert(entry((void *)0x1234,1,NULL)==0);
    image.h.sizeofcmds=24;
    assert(entry((void *)0x1234,1,NULL)==1);
    assert(regs()==1 && getcb());
    getcb()();
    assert(waits()==4);
    assert(entry((void *)0x1234,0,NULL)==1);
    assert(unregs()==1 && getcb()==NULL);
    assert(dlclose(probe)==0);
    assert(dlclose(fixture)==0);
    puts("PASS E0 dyld-test: invalid UUID/count/commands rejected; valid registered and detached");
    return 0;
}
