#ifndef GTA_V_IOS_PRP_MAILBOX_H
#define GTA_V_IOS_PRP_MAILBOX_H
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
#include "../P2P/prp_p2p.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Bounded, allocation-free network-thread -> GTA game-thread mailbox.
 * Producer MUST obtain source + auth + session from authenticated engine metadata.
 * Never fill these fields from an untrusted mod packet. */
#define PRP_INBOX_CAPACITY 64u
#define PRP_INBOX_FRAME_BUDGET 32u
typedef struct {
    uint64_t trusted_session_id;
    uint64_t trusted_sender_id;
    uint8_t authenticated_delivery;
    uint8_t packet[PRP_WIRE_SIZE];
} PRP_Inbound;
typedef struct {
    atomic_flag gate;
    atomic_uint dropped;
    uint32_t head, tail, count;
    PRP_Inbound items[PRP_INBOX_CAPACITY];
} PRP_Inbox;
void prp_inbox_init(PRP_Inbox *q);
/* Does not block networking threads; drops on contention/full queue. */
int prp_inbox_push(PRP_Inbox *q, uint64_t session, uint64_t sender,
                   uint8_t authenticated, const uint8_t *buf, size_t len);
int prp_inbox_pop(PRP_Inbox *q, PRP_Inbound *out);
/* Called ONLY on game thread on disconnect/host migration; clears pending packets. */
void prp_inbox_clear(PRP_Inbox *q);
unsigned prp_inbox_dropped(PRP_Inbox *q);
#ifdef __cplusplus
}
#endif
#endif
