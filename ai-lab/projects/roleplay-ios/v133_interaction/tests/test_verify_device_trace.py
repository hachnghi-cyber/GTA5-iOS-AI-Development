"""Synthetic fixture tests, NOT evidence from a GTA V iPhone."""
import importlib.util
import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_device_trace", ROOT / "tools" / "verify_device_trace.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def frame(session=222, receiver=202, epoch=7, nonce=11, kind=1):
    return struct.pack(mod.WIRE_FMT, b"PRP3", 1, kind, 0, session, receiver, epoch, nonce).hex()


def fixture(direction, device_id, player_id, peer_id, wire=None, **changes):
    row = dict(schema=mod.SCHEMA, device_id=device_id, direction=direction,
               build_uuid=mod.EXPECTED_UUID, source="engine-authenticated",
               authenticated=True, on_game_thread=True, session_id=222,
               session_epoch=7, local_player_id=player_id, remote_player_id=peer_id,
               monotonic_ms=100, wire_hex=wire or frame())
    row.update(changes)
    return row


def lines(*rows):
    return "\n".join(json.dumps(row) for row in rows)


class DeviceTraceTests(unittest.TestCase):
    def setUp(self):
        self.tx = fixture("tx", "synthetic-iPhone-A", 101, 202)
        self.rx = fixture("rx", "synthetic-iPhone-B", 202, 101)

    def test_matching_logs_are_not_authentication(self):
        r = mod.verify(lines(self.tx), lines(self.rx))
        self.assertTrue(r["trace_consistent"])
        self.assertEqual(r["matching_pairs"], 1)
        self.assertFalse(r["transport_provenance_cryptographically_attested"])
        self.assertFalse(r["safe_to_enable_cuff_or_escort"])

    def test_forged_sender_metadata(self):
        bad = fixture("rx", "synthetic-iPhone-B", 202, 303)
        r = mod.verify(lines(self.tx), lines(bad))
        self.assertFalse(r["trace_consistent"])
        self.assertEqual(r["unmatched_rx"], 1)

    def test_provenance_claim_required_but_not_proven(self):
        for changes in (dict(authenticated=False), dict(on_game_thread=False),
                        dict(source="payload-self-report")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                mod.verify(lines(self.tx),
                           lines(fixture("rx", "synthetic-iPhone-B", 202, 101, **changes)))

    def test_wrong_build_and_session(self):
        for changes in (dict(build_uuid="not-v13.3"), dict(session_id=9),
                        dict(session_epoch=8), dict(remote_player_id=0)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                mod.verify(lines(self.tx),
                           lines(fixture("rx", "synthetic-iPhone-B", 202, 101, **changes)))

    def test_packet_malformed_or_different_nonce_kind_target(self):
        for wire in (frame(nonce=12), frame(kind=2), frame(receiver=203),
                     "00"*40, frame()[:-2], frame() + "00"):
            row = fixture("rx", "synthetic-iPhone-B", 202, 101, wire=wire)
            with self.subTest(wire=wire):
                try:
                    self.assertFalse(mod.verify(lines(self.tx), lines(row))["trace_consistent"])
                except ValueError:
                    pass

    def test_duplicate_nonce_rejected(self):
        with self.assertRaises(ValueError):
            mod.verify(lines(self.tx, self.tx), lines(self.rx))

    def test_mixed_or_identical_device_ids(self):
        with self.assertRaises(ValueError):
            mod.verify(lines(self.tx, fixture("tx", "synthetic-iPhone-C", 101, 202)),
                       lines(self.rx))
        with self.assertRaises(ValueError):
            mod.verify(lines(self.tx),
                       lines(fixture("rx", "synthetic-iPhone-A", 202, 101)))

    def test_out_of_order_nonce_rejected(self):
        a = fixture("tx", "synthetic-iPhone-A", 101, 202,
                    wire=frame(nonce=19), monotonic_ms=200)
        b = fixture("tx", "synthetic-iPhone-A", 101, 202,
                    wire=frame(nonce=18), monotonic_ms=201)
        with self.assertRaises(ValueError):
            mod.verify(lines(a, b), lines(self.rx))

    def test_clocks_are_device_local(self):
        row = fixture("rx", "synthetic-iPhone-B", 202, 101, monotonic_ms=5)
        self.assertTrue(mod.verify(lines(self.tx), lines(row))["trace_consistent"])

    def test_local_clock_regression_rejected(self):
        another = fixture("tx", "synthetic-iPhone-A", 101, 202,
                          wire=frame(nonce=12), monotonic_ms=99)
        with self.assertRaises(ValueError):
            mod.verify(lines(self.tx, another), lines(self.rx))

    def test_self_interaction_rejected(self):
        with self.assertRaises(ValueError):
            mod.verify(lines(fixture("tx", "synthetic-iPhone-A", 101, 101)),
                       lines(self.rx))

    def test_bool_not_an_id(self):
        with self.assertRaises(ValueError):
            mod.verify(lines(fixture("tx", "synthetic-iPhone-A", 101, 202, session_id=True)),
                       lines(self.rx))

    def test_fixture_only_needs_explicit_switch(self):
        tx = dict(self.tx, fixture_only=True)
        rx = dict(self.rx, fixture_only=True)
        with self.assertRaises(ValueError):
            mod.verify(lines(tx), lines(rx))
        output = mod.verify(lines(tx), lines(rx), allow_synthetic=True)
        self.assertTrue(output["synthetic_demo"])
        self.assertFalse(output["safe_to_enable_cuff_or_escort"])

    def test_empty_log(self):
        with self.assertRaises(ValueError):
            mod.verify("", lines(self.rx))


if __name__ == "__main__":
    unittest.main()
