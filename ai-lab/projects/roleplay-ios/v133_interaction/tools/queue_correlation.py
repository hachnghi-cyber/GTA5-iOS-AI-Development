"""Bounded read-only queue correlation candidate; NEVER a proof source.

All inputs are already-observed debugger register values, not app-controlled
wire data. Neither event address equality nor traversal order authenticates a
RAGE sender. Caller must not expose this as an authorization API.
"""
from dataclasses import dataclass

MAX_PENDING = 48
MANAGER_QUEUE_OFFSET = 0x238  # exact-build static fact, not universal ABI

@dataclass
class Entry:
    index: int
    delivered: bool = False

class QueueCorrelation:
    def __init__(self, limit=MAX_PENDING):
        if type(limit) is not int or not 1 <= limit <= MAX_PENDING:
            raise ValueError('limit must be 1..MAX_PENDING')
        self.limit=limit
        self.pending={}
        self.serial=0
        self.rejections=0
        self.matches=0
        self.saturated=False
        self.disabled=False

    def reset(self):
        self.pending.clear()
        self.serial=0
        self.rejections=0
        self.matches=0
        self.saturated=False
        self.disabled=False

    @staticmethod
    def _ptr(v):
        return type(v) is int and 0 < v < (1 << 48) and v % 8 == 0

    def observe_unpacked(self, queue_ptr, event_ptr):
        # Address-only link and call-site pins confirmed separately.
        if self.disabled:
            return 'DISABLED'
        if not self._ptr(queue_ptr) or not self._ptr(event_ptr):
            self.rejections += 1
            return 'REJECT_REGISTER'
        k=(queue_ptr,event_ptr)
        if k in self.pending:
            # Pointer reuse / reenqueue before fully consumed => ambiguity.
            del self.pending[k]
            self.rejections+=1
            return 'AMBIGUOUS_REENQUEUE'
        if len(self.pending)>=self.limit:
            self.pending.clear()
            self.saturated=True
            self.disabled=True  # fail-closed until explicit reset, never silently recover
            self.rejections+=1
            return 'SATURATED_LOST_EVIDENCE'
        self.serial+=1
        self.pending[k]=Entry(self.serial)
        return 'QUEUED_CANDIDATE'

    def observe_next(self,queue_ptr,event_ptr):
        if self.disabled:
            return 'DISABLED'
        if not self._ptr(queue_ptr) or not self._ptr(event_ptr):
            self.rejections+=1
            return 'REJECT_REGISTER'
        k=(queue_ptr,event_ptr)
        v=self.pending.get(k)
        if v is None:
            return 'UNMATCHED_NEXT'
        if v.delivered:
            del self.pending[k]
            self.rejections+=1
            return 'AMBIGUOUS_REPEAT_NEXT'
        v.delivered=True
        return 'NEXT_CANDIDATE'

    def observe_on_event(self,manager_ptr,event_ptr):
        # Must refer to the manager owning the connection's captured queue.
        if self.disabled:
            return 'DISABLED'
        if not self._ptr(manager_ptr) or not self._ptr(event_ptr):
            self.rejections+=1
            return 'REJECT_REGISTER'
        q=manager_ptr+MANAGER_QUEUE_OFFSET
        if q >= (1<<48):
            self.rejections+=1
            return 'REJECT_REGISTER'
        k=(q,event_ptr)
        v=self.pending.pop(k,None)
        if v is None:
            return 'UNMATCHED_ON_EVENT'
        if not v.delivered:
            self.rejections+=1
            return 'MISSING_NEXT_EVENT'
        self.matches+=1
        # No packet credential, peer ownership, auth result or generation.
        return 'QUEUE_OBJECT_LINK_CANDIDATE_ONLY'

    def summary(self):
        return {
            'matches':self.matches,
            'rejections':self.rejections,
            'pending':len(self.pending),
            'saturated':self.saturated,
            'same_packet_verified':False,
            'sender_authenticated':False,
            'allow_rp_action':False,
        }
