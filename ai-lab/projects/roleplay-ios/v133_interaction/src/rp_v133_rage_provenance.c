#include "rp_v133_rage_provenance.h"
#include <limits.h>
#include <string.h>
static void clear_observations(rp_rage_observer *o) {
    o->session_id=0; o->last_now_ms=0; o->candidate_count=0;
    o->active=false; o->quarantined=false;
    memset(o->candidates,0,sizeof o->candidates);
}
void rp_rage_observer_init(rp_rage_observer *o) {
    if(o)memset(o,0,sizeof *o);
}
bool rp_rage_scope_begin(rp_rage_observer *o,uint64_t sid) {
    if(!o) return false;
    /* A renewal attempt ends the previous scope even when the new one
     * cannot be admitted. Never keep old candidates live on this failure. */
    clear_observations(o);
    if(o->generation==UINT64_MAX) return false;
    ++o->generation; /* local owner minted, NOT wire-controlled */
    if(!sid) return false;
    o->session_id=sid; o->active=true;
    return true;
}
void rp_rage_scope_invalidate(rp_rage_observer *o) {
    if(!o)return;
    clear_observations(o);
    if(o->generation!=UINT64_MAX)++o->generation;
}
static rp_rage_observation_status quarantine(rp_rage_observer *o) {
    o->quarantined=true;
    memset(o->candidates,0,sizeof o->candidates);
    o->candidate_count=0;
    return RP_RAGE_QUARANTINED;
}
rp_rage_observation_status rp_rage_observe(rp_rage_observer *o,
                                    const rp_rage_sample *s,uint64_t now) {
    if(!o || !s || !o->active || o->quarantined)
        return RP_RAGE_REJECTED;
    if(!now || (o->last_now_ms && now<o->last_now_ms))
        return quarantine(o); /* monotonic clock rolled back */
    /* No packet-owned field, local SendBuffer path, or stale generation can
     * ever promote a candidate. Even a passing result is UNAUTHENTICATED. */
    if(s->origin!=RP_RAGE_ORIGIN_REMOTE_ON_NET_EVENT ||
       !s->session_id || s->session_id!=o->session_id ||
       !s->generation || s->generation!=o->generation ||
       !s->peer_id || !s->netplayer_valid || !s->session_member ||
       s->local_player || s->netplayer_slot>=RP_RAGE_OBSERVER_MAX_PEERS ||
       !s->event_connection_id || s->event_connection_id>INT32_MAX ||
       s->session_connection_id<0 || s->session_endpoint_id<0 ||
       s->event_connection_id!=s->netplayer_connection_id ||
       s->event_connection_id!=(uint32_t)s->session_connection_id ||
       !s->observed_at_ms || s->observed_at_ms>now ||
       now-s->observed_at_ms>RP_RAGE_OBSERVER_MAX_AGE_MS)
        return RP_RAGE_REJECTED;
    for(unsigned i=0;i<o->candidate_count;i++) {
        rp_rage_candidate *p=&o->candidates[i];
        if(p->peer_id==s->peer_id) {
            if(p->connection_id!=s->event_connection_id ||
               p->endpoint_id!=s->session_endpoint_id ||
               p->slot!=s->netplayer_slot)
                return quarantine(o); /* remap without lifecycle invalidation */
            if(p->observations!=UINT32_MAX)++p->observations;
            p->last_seen_ms=now;
            o->last_now_ms=now;
            return RP_RAGE_CANDIDATE_ONLY;
        }
        if(p->connection_id==s->event_connection_id ||
           p->endpoint_id==s->session_endpoint_id ||
           p->slot==s->netplayer_slot)
            return quarantine(o); /* two peer IDs alias one resource */
    }
    if(o->candidate_count>=RP_RAGE_OBSERVER_MAX_PEERS)
        return quarantine(o);
    rp_rage_candidate *p=&o->candidates[o->candidate_count++];
    p->peer_id=s->peer_id;
    p->connection_id=s->event_connection_id;
    p->endpoint_id=s->session_endpoint_id;
    p->slot=s->netplayer_slot;
    p->last_seen_ms=now;
    p->observations=1;
    o->last_now_ms=now;
    return RP_RAGE_CANDIDATE_ONLY;
}
