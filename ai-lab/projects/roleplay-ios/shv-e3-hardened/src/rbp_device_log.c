#define _POSIX_C_SOURCE 200809L
#include "rbp_device_log.h"
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* An explicit, bounded file log is needed because stderr capture by the
 * port's launcher is NOT established. The file remains inside the app's own
 * sandbox: <HOME>/Documents/RBPProbe.log. No directory creation or entitlements.
 * If the sandbox is unavailable, only stderr is used. Called on worker and
 * ScriptHook callback threads; no RAGE API is called here. */
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
void rbp_logf(const char *format, ...) {
    if (!format) return;
    char line[1024];
    va_list args;
    va_start(args,format);
    int written=vsnprintf(line,sizeof(line)-2,format,args);
    va_end(args);
    if (written < 0) return;
    size_t n=(size_t)written;
    if (n>sizeof(line)-2) n=sizeof(line)-2;
    if (n==0 || line[n-1]!='\n') line[n++]='\n';
    line[n]='\0';
    pthread_mutex_lock(&g_lock);
    /* stderr is best effort and can be redirected/hidden by the host. */
    (void)fwrite(line,1,n,stderr);
    const char *home=getenv("HOME");
    static const char suffix[]="/Documents/RBPProbe.log";
    if (home && home[0]) {
        size_t hlen=strlen(home);
        char path[1024];
        if (hlen+sizeof(suffix) <= sizeof(path)) {
            memcpy(path,home,hlen);
            memcpy(path+hlen,suffix,sizeof(suffix));
            int fd=open(path,O_WRONLY|O_CREAT|O_APPEND|O_CLOEXEC,0600);
            if (fd>=0) {
                size_t offset=0;
                while (offset<n) {
                    ssize_t m=write(fd,line+offset,n-offset);
                    if (m>0) offset+=(size_t)m;
                    else if(m<0 && errno==EINTR) continue;
                    else break;
                }
                (void)close(fd);
            }
        }
    }
    pthread_mutex_unlock(&g_lock);
}
