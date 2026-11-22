#ifndef RP14_SESSION_H
#define RP14_SESSION_H
#include "roster.h"
typedef struct { uint64_t root,primary,id; } SSession;
typedef struct { RTracker roster; SSession session; int active; uint64_t room_epoch; } STracker;
int rp14_session(const RReader*, SSession*);
int rp14_session_roster(const RReader*, SSession*, RSnapshot*, int*);
void rp14_session_track(STracker*, const SSession*, const RSnapshot*, int);
#endif
