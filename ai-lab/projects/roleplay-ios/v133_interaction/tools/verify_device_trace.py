#!/usr/bin/env python3
"""Read-only PRP3 two-device trace correlation for GTA V iOS v13.3.

A matching log DOES NOT authenticate its origin. Never enable RP gameplay based
only on synthetic logs or caller-supplied 'authenticated' metadata.
"""
import argparse
import json
import struct
from collections import Counter
from pathlib import Path

EXPECTED_UUID = "EB122C35-96F4-307F-91C3-A2255DD9C685"
SCHEMA = "prp3-device-trace-v1"
WIRE_FMT = "<4sBBHQQQQ"
WIRE_LEN = struct.calcsize(WIRE_FMT)
REQUIRED = {
    "schema", "device_id", "direction", "build_uuid", "source",
    "authenticated", "on_game_thread", "session_id", "session_epoch",
    "local_player_id", "remote_player_id", "monotonic_ms", "wire_hex"
}


def positive_int(value):
    return type(value) is int and 0 < value < (1 << 64)


def parse_frame(value):
    if not isinstance(value, str) or len(value) != WIRE_LEN * 2:
        raise ValueError("wire_hex must be exactly 80 hex characters")
    try:
        data = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("invalid wire_hex") from exc
    if len(data) != WIRE_LEN:
        raise ValueError("invalid wire size")
    magic, version, kind, reserved, session, receiver, epoch, nonce = struct.unpack(WIRE_FMT, data)
    if magic != b"PRP3" or version != 1 or reserved != 0 or kind not in (1, 2):
        raise ValueError("invalid magic/version/kind/reserved")
    if not all(positive_int(x) for x in (session, receiver, epoch, nonce)):
        raise ValueError("invalid session/receiver/epoch/nonce")
    return {"data": data, "session": session, "receiver": receiver,
            "epoch": epoch, "nonce": nonce, "kind": kind}


def parse_record(record, direction, allow_synthetic=False):
    if not isinstance(record, dict) or not REQUIRED.issubset(record):
        raise ValueError("missing fields")
    if record["schema"] != SCHEMA or record["direction"] != direction:
        raise ValueError("schema/direction mismatch")
    if record.get("fixture_only") is True and not allow_synthetic:
        raise ValueError("synthetic fixture refused without --allow-synthetic-demo")
    if not isinstance(record["device_id"], str) or not record["device_id"].strip():
        raise ValueError("device_id missing")
    if record["build_uuid"] != EXPECTED_UUID:
        raise ValueError("v13.3 build UUID mismatch")
    # A reported boolean is not an engine-authenticated proof.
    if (record["source"] != "engine-authenticated"
            or record["authenticated"] is not True
            or record["on_game_thread"] is not True):
        raise ValueError("claimed provenance missing")
    keys = ("session_id", "session_epoch", "local_player_id", "remote_player_id")
    if not all(positive_int(record[k]) for k in keys):
        raise ValueError("bad session/player IDs")
    if record["local_player_id"] == record["remote_player_id"]:
        raise ValueError("self-interaction")
    timestamp = record["monotonic_ms"]
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError("bad monotonic_ms")
    frame = parse_frame(record["wire_hex"])
    if frame["session"] != record["session_id"] or frame["epoch"] != record["session_epoch"]:
        raise ValueError("packet and transport metadata mismatch")
    target = record["remote_player_id"] if direction == "tx" else record["local_player_id"]
    if frame["receiver"] != target:
        raise ValueError("packet target mismatch")
    return {"record": record, "frame": frame}


def parse_jsonl(source, direction, allow_synthetic=False):
    rows = []
    for line_number, line in enumerate(source.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(parse_record(json.loads(line), direction, allow_synthetic))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{direction} line {line_number}: {exc}") from exc
    if not rows:
        raise ValueError(f"empty {direction} log")
    if len({row["record"]["device_id"] for row in rows}) != 1:
        raise ValueError(f"mixed devices in {direction} log")
    last_nonce = {}
    stamps = []
    for row in rows:
        record = row["record"]
        key = (record["session_id"], record["session_epoch"],
               record["local_player_id"], record["remote_player_id"])
        nonce = row["frame"]["nonce"]
        if nonce <= last_nonce.get(key, 0):
            raise ValueError(f"{direction} nonce replay/out-of-order")
        last_nonce[key] = nonce
        stamps.append(record["monotonic_ms"])
    # Timestamps are comparable within one device ONLY.
    if any(b < a for a, b in zip(stamps, stamps[1:])):
        raise ValueError(f"{direction} local monotonic clock regressed")
    return rows


def verify(tx_text, rx_text, min_pairs=1, allow_synthetic=False):
    tx = parse_jsonl(tx_text, "tx", allow_synthetic)
    rx = parse_jsonl(rx_text, "rx", allow_synthetic)
    if tx[0]["record"]["device_id"] == rx[0]["record"]["device_id"]:
        raise ValueError("logs must be from different devices")
    # Equality verifies wire + metadata consistency, NOT authenticity.
    def tx_key(row):
        r = row["record"]
        return (row["frame"]["data"], r["local_player_id"], r["remote_player_id"])
    def rx_key(row):
        r = row["record"]
        return (row["frame"]["data"], r["remote_player_id"], r["local_player_id"])
    sent, received = Counter(map(tx_key, tx)), Counter(map(rx_key, rx))
    matches = sum((sent & received).values())
    missing_tx = sum((sent - received).values())
    missing_rx = sum((received - sent).values())
    duplicate_tx = sum(x - 1 for x in sent.values() if x > 1)
    duplicate_rx = sum(x - 1 for x in received.values() if x > 1)
    return {
        "status": "OFFLINE_TRACE_CORRELATION_ONLY",
        "trace_consistent": matches >= min_pairs and not (
            missing_tx or missing_rx or duplicate_tx or duplicate_rx),
        "synthetic_demo": any(x["record"].get("fixture_only") is True for x in tx + rx),
        "matching_pairs": matches, "unmatched_tx": missing_tx,
        "unmatched_rx": missing_rx, "duplicate_tx": duplicate_tx,
        "duplicate_rx": duplicate_rx, "build_uuid": EXPECTED_UUID,
        "transport_provenance_cryptographically_attested": False,
        "on_device_execution_verified_by_this_tool": False,
        "safe_to_enable_cuff_or_escort": False,
        "caution": "JSON fields are untrusted claims. A matched trace cannot prove engine callback origin or playable GTA RP."
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tx", type=Path, required=True)
    ap.add_argument("--rx", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--min-pairs", type=int, default=1)
    ap.add_argument("--allow-synthetic-demo", action="store_true")
    args = ap.parse_args()
    if args.min_pairs < 1:
        ap.error("min-pairs must be positive")
    try:
        result = verify(args.tx.read_text(encoding="utf-8"),
                        args.rx.read_text(encoding="utf-8"),
                        args.min_pairs, args.allow_synthetic_demo)
    except (OSError, ValueError) as exc:
        result = {"status": "INVALID_TRACE", "trace_consistent": False,
                  "error": str(exc), "safe_to_enable_cuff_or_escort": False}
    result_text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result_text, encoding="utf-8")
    print(result_text, end="")
    return 0 if result.get("trace_consistent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
