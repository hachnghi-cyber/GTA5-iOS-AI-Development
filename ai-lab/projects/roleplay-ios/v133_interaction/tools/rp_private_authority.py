"""Opaque ABI for the existing C Police authority; no GTA pointers or hooks."""
import ctypes as C
from pathlib import Path

U64 = C.c_uint64
U8 = C.c_uint8
FIELDS = ('id', 'role', 'consent', 'on_duty', 'custody', 'custodian',
          'vehicle_id', 'seat', 'jail_until_ms', 'last_nonce')


class NativeAuthority:
    def __init__(self, library, session, epoch, *, observation_provider=None):
        self.lib = C.CDLL(str(Path(library).resolve()))
        signatures = {
            'abi': (C.c_uint32, []),
            'create': (C.c_void_p, [U64, U64]),
            'destroy': (None, [C.c_void_p]),
            'admit': (C.c_int, [C.c_void_p, U64, C.c_uint32]),
            'leave': (C.c_int, [C.c_void_p, U64]),
            'tick': (C.c_int, [C.c_void_p, U64]),
            'snapshot': (C.c_int, [C.c_void_p, U64, C.POINTER(U64), C.c_size_t]),
            'dispatch': (C.c_int, [C.c_void_p, U64, U64, C.POINTER(U8), C.c_size_t,
                                  C.POINTER(U64), C.c_size_t, C.POINTER(U8), C.c_size_t]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.lib, 'rp_server_' + name)
            function.restype, function.argtypes = result, args
        if self.lib.rp_server_abi() != 1:
            raise ValueError('unsupported authority ABI')
        self.handle = self.lib.rp_server_create(session, epoch)
        if not self.handle:
            raise ValueError('invalid authority scope')
        self.session, self.epoch = session, epoch
        # Only a trusted, in-process source may supply facts. CLI leaves this None.
        # Tests explicitly use synthetic observations; no client field can set it.
        self.observation_provider = observation_provider

    def close(self):
        if self.handle:
            self.lib.rp_server_destroy(self.handle)
            self.handle = None

    def admit(self, identity, role):
        return bool(self.lib.rp_server_admit(self.handle, identity, role))

    def leave(self, identity):
        return bool(self.lib.rp_server_leave(self.handle, identity))

    def tick(self, now):
        return bool(self.lib.rp_server_tick(self.handle, now))

    def snapshot(self, identity):
        result = (U64 * 10)()
        if not self.lib.rp_server_snapshot(self.handle, identity, result, 10):
            return None
        return tuple(result)

    def dispatch(self, sender, now, wire):
        if len(wire) != 40:
            return None
        facts = None
        if self.observation_provider:
            values = self.observation_provider(sender, now, wire)
            if values is not None:
                if len(values) != 7 or any(type(v) is not int or not 0 <= v < 2**64 for v in values):
                    raise ValueError('invalid trusted observation')
                facts = (U64 * 7)(*values)
        request, ack = (U8 * 40).from_buffer_copy(wire), (U8 * 40)()
        if not self.lib.rp_server_dispatch(self.handle, sender, now, request, 40,
                                           facts, 7 if facts is not None else 0, ack, 40):
            return None
        return bytes(ack)
