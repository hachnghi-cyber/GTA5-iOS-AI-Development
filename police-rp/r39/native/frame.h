#ifndef FRAME_H
#define FRAME_H
typedef struct { unsigned ms,mask,custom; int slot,alive,x,y,z,target,dist,valid,pressed; } Frame;
int parse_line(Frame *f,const char *line);
#endif
