#include "prp_mailbox.h"
#include <string.h>

/* Never spin forever on the network callback thread. */
static int grab(PRP_Inbox *q) {
    for (unsigned n=0; n<32u; ++n)
        if (!atomic_flag_test_and_set_explicit(&q->gate,memory_order_acquire))
            return 1;
    return 0;
}
static void drop(PRP_Inbox *q) {
    atomic_fetch_add_explicit(&q->dropped,1u,memory_order_relaxed);
}
static void unlock(PRP_Inbox *q) {
    atomic_flag_clear_explicit(&q->gate,memory_order_release);
}
void prp_inbox_init(PRP_Inbox *q) {
    if (!q)return;
    /* New instance, not allowed concurrently with any reader/writer. */
    memset(q,0,sizeof(*q));
    atomic_flag_clear_explicit(&q->gate,memory_order_release);
    atomic_init(&q->dropped,0u);
}
int prp_inbox_push(PRP_Inbox *q, uint64_t session, uint64_t sender,
                   uint8_t authenticated, const uint8_t *buf, size_t len) {
    if (!q)return 0;
    if (!session || !sender || authenticated!=1 || !buf || len!=PRP_WIRE_SIZE) {
        drop(q);return 0;
    }
    if (!grab(q)){drop(q);return 0;}
    if (q->count>=PRP_INBOX_CAPACITY) {
        unlock(q);drop(q);return 0;
    }
    PRP_Inbound *e=&q->items[q->tail];
    e->trusted_session_id=session;
    e->trusted_sender_id=sender;
    e->authenticated_delivery=authenticated;
    memcpy(e->packet,buf,PRP_WIRE_SIZE);
    q->tail=(q->tail+1u)%PRP_INBOX_CAPACITY;
    q->count++;
    unlock(q);
    return 1;
}
int prp_inbox_pop(PRP_Inbox *q, PRP_Inbound *out) {
    if (!q || !out || !grab(q))return 0;
    if (!q->count){unlock(q);return 0;}
    *out=q->items[q->head];
    q->head=(q->head+1u)%PRP_INBOX_CAPACITY;
    q->count--;
    unlock(q);
    return 1;
}
void prp_inbox_clear(PRP_Inbox *q) {
    if (!q)return;
    /* Game thread may wait briefly; producer's critical section is memcpy(56). */
    while (atomic_flag_test_and_set_explicit(&q->gate,memory_order_acquire)){}
    q->head=q->tail=q->count=0;
    unlock(q);
}
unsigned prp_inbox_dropped(PRP_Inbox *q) {
    return q?atomic_load_explicit(&q->dropped,memory_order_relaxed):0u;
}
