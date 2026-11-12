#include "prp_mailbox.h"
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {PRP_Inbox *q; unsigned accepted;} Producer;
static void *produce(void *ptr){
  Producer *p=ptr;uint8_t data[PRP_WIRE_SIZE]={0};memcpy(data,"PRP6",4);
  for(unsigned i=0;i<5000;i++)
    p->accepted+=(unsigned)prp_inbox_push(p->q,99,(uint64_t)i+1u,1,data,sizeof(data));
  return NULL;
}
int main(void){
  PRP_Inbox q;prp_inbox_init(&q);
  uint8_t data[PRP_WIRE_SIZE]={0};memcpy(data,"PRP6",4);
  assert(!prp_inbox_push(&q,0,1,1,data,sizeof(data)));
  assert(!prp_inbox_push(&q,99,1,0,data,sizeof(data)));
  assert(!prp_inbox_push(&q,99,1,1,data,55));
  for(unsigned i=0;i<PRP_INBOX_CAPACITY;i++)
    assert(prp_inbox_push(&q,99,i+1u,1,data,sizeof(data)));
  assert(!prp_inbox_push(&q,99,88,1,data,sizeof(data)));
  for(unsigned i=0;i<PRP_INBOX_CAPACITY;i++){
    PRP_Inbound m;assert(prp_inbox_pop(&q,&m));
    assert(m.trusted_sender_id==i+1u&&m.trusted_session_id==99);
    assert(m.authenticated_delivery==1);
  }
  PRP_Inbound empty;assert(!prp_inbox_pop(&q,&empty));
  Producer a={&q,0},b={&q,0};pthread_t ta,tb;
  assert(!pthread_create(&ta,NULL,produce,&a));
  assert(!pthread_create(&tb,NULL,produce,&b));
  assert(!pthread_join(ta,NULL));assert(!pthread_join(tb,NULL));
  unsigned accepted=a.accepted+b.accepted;
  assert(accepted<=PRP_INBOX_CAPACITY);
  unsigned drained=0;PRP_Inbound msg;
  while(prp_inbox_pop(&q,&msg)){
    assert(msg.trusted_session_id==99&&msg.authenticated_delivery);
    drained++;
  }
  assert(drained==accepted);
  assert(prp_inbox_push(&q,100,10,1,data,sizeof(data)));
  prp_inbox_clear(&q);
  assert(!prp_inbox_pop(&q,&empty));
  printf("PoliceRP v0.8 mailbox OK (two concurrent producers, accepted=%u, dropped=%u)\n",
    accepted,prp_inbox_dropped(&q));
  return 0;
}
