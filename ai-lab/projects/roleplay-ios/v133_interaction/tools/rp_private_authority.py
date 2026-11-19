"""Opaque ABI for the existing C Police authority; no GTA pointers or hooks."""
import ctypes as C
from dataclasses import dataclass
from pathlib import Path

U64 = C.c_uint64
U8 = C.c_uint8
FIELDS = ('id', 'role', 'consent', 'on_duty', 'custody', 'custodian',
          'vehicle_id', 'seat', 'jail_until_ms', 'last_nonce')
DUTY_MAX_AGE_MS = 250


@dataclass(frozen=True)
class DutySubject:
    principal: int
    session: int
    epoch: int
    admission: int


@dataclass(frozen=True)
class DutyObservation:
    subject: DutySubject
    observed_at_ms: int
    on_shift: bool


class NativeAuthority:
    def __init__(self, library, session, epoch, *, observation_provider=None, duty_provider=None):
        self.lib = C.CDLL(str(Path(library).resolve()))
        self.lib.rp_server_abi.restype, self.lib.rp_server_abi.argtypes = C.c_uint32, []
        if self.lib.rp_server_abi() != 2:
            raise ValueError('unsupported authority ABI; rebuild the host library')
        signatures = {
            'create': (C.c_void_p, [U64, U64]),
            'destroy': (None, [C.c_void_p]),
            'admit': (C.c_int, [C.c_void_p, U64, C.c_uint32]),
            'leave': (C.c_int, [C.c_void_p, U64]),
            'revoke_duty': (C.c_int, [C.c_void_p, U64]),
            'tick': (C.c_int, [C.c_void_p, U64]),
            'snapshot': (C.c_int, [C.c_void_p, U64, C.POINTER(U64), C.c_size_t]),
            'dispatch': (C.c_int, [C.c_void_p, U64, U64, C.POINTER(U8), C.c_size_t,
                                  C.POINTER(U64), C.c_size_t, C.POINTER(U8), C.c_size_t]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.lib, 'rp_server_' + name)
            function.restype, function.argtypes = result, args
        self.handle = self.lib.rp_server_create(session, epoch)
        if not self.handle:
            raise ValueError('invalid authority scope')
        self.session, self.epoch = session, epoch
        # Only a trusted, in-process source may supply facts. CLI leaves this None.
        # Tests explicitly use synthetic observations; no client field can set it.
        self.observation_provider = observation_provider
        # A trusted provider must bind its original game observation to the
        # subject and retain the original observation time. It runs in this
        # owner process on the same monotonic clock, never on the RP wire.
        self.duty_provider = duty_provider
        self._admissions = {}
        self._last_duty = {}
        self._admission_generation = 0

    def close(self):
        if self.handle:
            self.lib.rp_server_destroy(self.handle)
            self.handle = None

    def admit(self, identity, role):
        if not self.lib.rp_server_admit(self.handle, identity, role):
            return False
        self._admission_generation += 1
        self._admissions[identity] = DutySubject(identity, self.session, self.epoch, self._admission_generation)
        return True

    def leave(self, identity):
        if not self.lib.rp_server_leave(self.handle, identity):
            return False
        self._admissions.pop(identity, None)
        self._last_duty.pop(identity, None)
        return True

    def _current_duty(self, identity, now):
        subject = self._admissions.get(identity)
        if not subject or self.duty_provider is None:
            return False
        try:
            sample = self.duty_provider(subject, now)
        except Exception:
            return False  # Source unavailable. Fail closed without logging its contents.
        if (type(sample) is not DutyObservation or sample.subject != subject or
                type(sample.on_shift) is not bool or type(sample.observed_at_ms) is not int or
                not 0 <= sample.observed_at_ms <= now or now - sample.observed_at_ms > DUTY_MAX_AGE_MS):
            return False
        last = self._last_duty.get(identity)
        if last and (sample.observed_at_ms < last.observed_at_ms or
                     (sample.observed_at_ms == last.observed_at_ms and not last.on_shift)):
            return False
        self._last_duty[identity] = sample
        return sample.on_shift

    def _revoke_if_on_duty(self, identity):
        member = self.snapshot(identity)
        if member is not None and member[3]:
            self.lib.rp_server_revoke_duty(self.handle, identity)

    def tick(self, now):
        if not self.lib.rp_server_tick(self.handle, now):
            return False
        for identity in self._admissions:
            member = self.snapshot(identity)
            if member is not None and member[3] and not self._current_duty(identity, now):
                self.lib.rp_server_revoke_duty(self.handle, identity)
        return True

    def snapshot(self, identity):
        result = (U64 * 10)()
        if not self.lib.rp_server_snapshot(self.handle, identity, result, 10):
            return None
        return tuple(result)

    def dispatch(self, sender, now, wire):
        if len(wire) != 40:
            return None
        on_shift = self._current_duty(sender, now)
        if not on_shift:
            self._revoke_if_on_duty(sender)
        facts = None
        if self.observation_provider:
            values = self.observation_provider(sender, now, wire)
            if values is not None:
                if len(values) != 7 or any(type(v) is not int or not 0 <= v < 2**64 for v in values):
                    raise ValueError('invalid trusted observation')
                facts = (U64 * 7)(*values)
                if not on_shift:
                    facts[4] &= ~2
        request, ack = (U8 * 40).from_buffer_copy(wire), (U8 * 40)()
        if not self.lib.rp_server_dispatch(self.handle, sender, now, request, 40,
                                           facts, 7 if facts is not None else 0, ack, 40):
            return None
        return bytes(ack)
