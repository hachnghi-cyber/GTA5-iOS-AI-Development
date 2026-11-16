#include "rbp_handoff.h"
/* Freestanding byte copy to permit ARM64 Mach-O object compile without iPhoneOS SDK. */
static void copy_event(rbp_diag_event *dst, const rbp_diag_event *src) {
    const unsigned char *a=(const unsigned char*)src;
    unsigned char *b=(unsigned char*)dst;
    for (unsigned i=0;i<sizeof(*dst);++i) b[i]=a[i];
}
void rbp_handoff_init(rbp_handoff *h) {
    if(!h) return;
    rbp_diag_event zero = {0};
    copy_event(&h->item, &zero);
    atomic_init(&h->state, RBP_EMPTY);
}
int rbp_handoff_push(rbp_handoff *h, const rbp_diag_event *event) {
    if(!h || !event || event->type != 1 || event->sequence == 0) return -1;
    unsigned empty = RBP_EMPTY;
    if(!atomic_compare_exchange_strong_explicit(&h->state,&empty,RBP_WRITING,
            memory_order_acquire,memory_order_relaxed)) return 0;
    copy_event(&h->item,event);
    atomic_store_explicit(&h->state,RBP_READY,memory_order_release);
    return 1;
}
int rbp_handoff_pop_on_game_thread(rbp_handoff *h, rbp_diag_event *output) {
    if(!h || !output) return -1;
    unsigned ready=RBP_READY;
    if(!atomic_compare_exchange_strong_explicit(&h->state,&ready,RBP_READING,
            memory_order_acquire,memory_order_relaxed)) return 0;
    copy_event(output,&h->item);
    atomic_store_explicit(&h->state,RBP_EMPTY,memory_order_release);
    return 1;
}
