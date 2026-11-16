#!/usr/bin/env python3
"""Read-only exact-v13.3 ScriptHookV loader contract verification.

Fingerprint-only: no RAGE hooks, offsets reused between builds or runtime claims.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
from verify_shv_abi import EXPECTED_SHA256, ABIVerificationError, audit, load_input

LOADER_WORDS = {
    0x4C34: 0xB40003E0, # cbz x0 -> enabled if off-flag file absent
    0x4D14: 0xF1002C1F, # cmp x0, #0xb: plugin suffix length gate
    0x4D70: 0x528000C1, # mov w1, #6: dlopen flags
    0x4D94: 0x6B18013F, # cmp w9,w24: script count before/after dlopen
    0x4DA4: 0x52800021, # mov w1,#1: DllMain attach
    0x4DB4: 0x4B180128, # sub w8,w9,w24: script registrations delta
    0x4DC4: 0x97FFFD2B, # bl _ph_note: stock 'loaded plugin' message
}
LOADER_STRINGS = (
    b'posthook/scripthook-off',
    b'.shv.dylib',
    b'DllMain',
    b'[shv] loaded plugin %s (%d scripts)',
    b"[shv] couldn't load plugin %s: %s",
    b'Script Hook is OFF (zero cost)',
)

def verify_loader_bytes(data: bytes, expected_hash: str = EXPECTED_SHA256) -> dict:
    source = audit(data, expected_hash=expected_hash)
    for off, word in LOADER_WORDS.items():
        if len(data) < off + 4 or struct.unpack_from('<I', data, off)[0] != word:
            raise ABIVerificationError(f'LOADER_OPCODE_MISMATCH_0x{off:x}')
    for item in LOADER_STRINGS:
        if item not in data:
            raise ABIVerificationError('LOADER_LITERAL_MISSING_'+item[:16].hex())
    return {
        'status': 'STATIC_LOADER_CONTRACT_MATCH',
        'sha256': source['sha256'],
        'uuid': source['macho_uuid'],
        'guarded_opcode_count': source['inspected_arm64_words'] + len(LOADER_WORDS),
        'loader_log_contract': 'script delta printed only after load/registration branch',
        'device_loaded': False,
        'script_callback_on_iphone': False,
        'trusted_network_sender': False,
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('source', type=Path, help='local owned v13.3 IPA or ScriptHookV.dylib')
    args=ap.parse_args()
    try:
        result=verify_loader_bytes(load_input(args.source))
        code=0
    except (KeyError,OSError,ABIVerificationError) as exc:
        result={'status':'REJECTED','reason':str(exc)}
        code=1
    print(json.dumps(result, indent=2, sort_keys=True))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
