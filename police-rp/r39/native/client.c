#include "portable.h"
#include "frame.h"
static char config[1024],logpath[1024],statuspath[1024],tmppath[1024];
static char token[81],ip[32],binding[33];static int port,slot;static long long seq;
static long long ms(void){struct timespec t={0};clock_gettime(CLOCK_MONO,&t);return t.tv_sec*1000LL+t.tv_nsec/1000000;}
static int safe_token(const char *s){int n=0;for(;*s;s++,n++)if(!((*s>='A'&&*s<='Z')||(*s>='a'&&*s<='z')||(*s>='0'&&*s<='9')||*s=='-'||*s=='_'))return 0;return n>=32&&n<=80;}
static int private_ip(const char*s,unsigned char out[4]){unsigned a,b,c,d;char more;if(sscanf(s,"%u.%u.%u.%u%c",&a,&b,&c,&d,&more)!=4||a>255||b>255||c>255||d>255)return 0;if(!(a==10||(a==192&&b==168)||(a==172&&b>=16&&b<=31)))return 0;out[0]=a;out[1]=b;out[2]=c;out[3]=d;return 1;}
static int waitfd(int fd,short ev,long long end){for(;;){long long left=end-ms();if(left<=0)return 0;struct pollfd p={fd,ev,0};int n=poll(&p,1,(int)left);if(n<0&&ERRNO==EINTR)continue;return n>0&&(p.revents&(ev|POLLHUP));}}
static int http(const char*path,const char*body,char*out,int cap){unsigned char addr[4];if(!private_ip(ip,addr))return 0;int fd=socket(AF_INET,SOCK_STREAM,0);if(fd<0)return 0;int ok=0;long long end=ms()+2200;struct sockaddr_in a={0};
#ifdef __APPLE__
 a.sin_len=sizeof(a);int yes=1;if(setsockopt(fd,SOL,SO_NOSIGPIPE,&yes,sizeof(yes)))goto done;
#endif
 a.sin_family=AF_INET;unsigned char *p=(unsigned char*)&a.sin_port;p[0]=(unsigned)port>>8;p[1]=port; p=(unsigned char*)&a.sin_addr;for(int i=0;i<4;i++)p[i]=addr[i];
 if(fcntl(fd,F_SETFL,NONBLOCK)<0)goto done;
 if(connect(fd,(const void*)&a,sizeof(a))<0){if(ERRNO!=EINPROGRESS||!waitfd(fd,POLLOUT,end))goto done;int e=0;socklen_t n=sizeof(e);if(getsockopt(fd,SOL,SOERR,&e,&n)||e)goto done;}
 char req[1500];int n=snprintf(req,sizeof(req),"%s %s HTTP/1.0\r\nHost: %s:%d\r\nAuthorization: Bearer %s\r\nContent-Type: application/json\r\nContent-Length: %lu\r\nConnection: close\r\n\r\n%s",body?"POST":"GET",path,ip,port,token,(unsigned long)(body?strlen(body):0),body?body:"");if(n<0||n>=(int)sizeof(req))goto done;
 for(int sent=0;sent<n;){if(!waitfd(fd,POLLOUT,end))goto done;ssize_t k=send(fd,req+sent,n-sent,SEND_FLAGS);if(k<0&&(ERRNO==EAGAIN||ERRNO==EINTR))continue;if(k<=0)goto done;sent+=(int)k;}
 int got=0;while(got<cap-1){if(!waitfd(fd,POLLIN,end))goto done;ssize_t k=recv(fd,out+got,cap-1-got,0);if(k<0&&(ERRNO==EAGAIN||ERRNO==EINTR))continue;if(k<0)goto done;if(!k)break;got+=(int)k;}if(got==cap-1)goto done;out[got]=0;int code=0;if(sscanf(out,"HTTP/%*s %d",&code)!=1)goto done;ok=code;
 done:close(fd);return ok;}
static void status(const char*s){FILE*f=fopen(tmppath,"w");if(f){fputs(s,f);fclose(f);rename(tmppath,statuspath);}}
static int load_config(void){char buf[256],extra;unsigned char a[4];FILE*f=fopen(config,"r");if(!f)return 0;int ok=fgets(buf,sizeof(buf),f)!=0;fclose(f);return ok&&sscanf(buf,"%31s %d %80s %c",ip,&port,token,&extra)==3&&private_ip(ip,a)&&port>0&&port<=65535&&safe_token(token);}
static int hello(void){char out[4096];int code=http("/v1/native/binding",0,out,sizeof(out));if(code!=200)return 0;char*p=strstr(out,"\r\n\r\n");if(!p||sscanf(p+4,"RP38 %32[0-9a-f] %d %lld",binding,&slot,&seq)!=3||strlen(binding)!=32||slot<0||slot>31||seq< -1||seq>=9007199254740990LL)return 0;return 1;}
static int publish(Frame*f){char req[512],out[4096];if(f->slot!=slot)return 409;if(seq>=9007199254740990LL)return 409;++seq;snprintf(req,sizeof(req),"{\"binding\":\"%s\",\"slot\":%d,\"seq\":%lld,\"pos\":[%.2f,%.2f,%.2f],\"alive\":%s,\"consent\":true,\"pressed\":%s,\"target_slot\":%d}",binding,slot,seq,f->x/100.,f->y/100.,f->z/100.,f->alive?"true":"false",f->pressed?"true":"false",f->target);int code=http("/v1/native/frame",req,out,sizeof(out));if(code==200){char*p=strstr(out,"\r\n\r\n");if(p)status(p+4);}return code;}
static void*worker(void*unused){(void)unused;const char*home=getenv("HOME");if(!home||strlen(home)>850)return 0;snprintf(config,sizeof(config),"%s/Documents/GTAV/rp38.conf",home);snprintf(logpath,sizeof(logpath),"%s/Documents/Logs/run.log",home);snprintf(statuspath,sizeof(statuspath),"%s/Documents/GTAV/rp38-status.json",home);snprintf(tmppath,sizeof(tmppath),"%s/Documents/GTAV/rp38-status.tmp",home);
 while(!load_config())sleep(2);status("{\"state\":\"connecting\"}");while(access(config,0)==0&&!hello())sleep(2);if(access(config,0))return 0;
 FILE*f=0;while(access(config,0)==0&&!(f=fopen(logpath,"r")))sleep(1);if(!f)return 0;fseek(f,0,2);status("{\"state\":\"waiting_frame\"}");Frame frame={0};char line[2048];int len=0,overflow=0,active=0,dirty=0;long long last=ms(),fresh=last;unsigned last_game=0;
 while(access(config,0)==0){long long t=ms();if(t-last>4000||(active&&t-fresh>5000)){status("{\"state\":\"stale\",\"restart_required\":true}");break;}last=t;int ch,count=0,stop=0;while((ch=fgetc(f))!=-1){if(++count>65536){stop=1;break;}if(ch=='\n'){if(!overflow){line[len]=0;int r=parse_line(&frame,line);if(r==1){if(frame.slot!=slot||(active&&frame.ms<last_game)){stop=1;break;}active=1;last_game=frame.ms;dirty=1;fresh=t;}else if(r==-1&&active){stop=1;break;}}len=overflow=0;}else if(len<(int)sizeof(line)-1)line[len++]=(char)ch;else overflow=1;}
 clearerr(f);if(stop){status("{\"state\":\"session_changed\",\"restart_required\":true}");break;}if(dirty&&frame.valid){if((frame.custom&128)&&!frame.pressed&&t-fresh<1000){sleep(1);continue;}int code=publish(&frame);frame.pressed=0;dirty=0;if(code!=200){status("{\"state\":\"disconnected\",\"restart_required\":true}");break;}}sleep(1);}
 fclose(f);if(access(config,0)!=0)status("{\"state\":\"disabled\"}");return 0;}
#if defined(__APPLE__) && !defined(RP_HOST_TEST)
__attribute__((constructor))static void start(void){pthread_t t;if(!pthread_create(&t,0,worker,0))pthread_detach(t);}
#else
int main(void){worker(0);return 0;}
#endif
