#!/usr/bin/env python3
"""Read-only exact-build v13.3 ScriptHookV ARM64 ABI audit.

Supply locally owned IPA or extracted dylib. Never upload game assets to CI.
This verifies static instructions ONLY, not ScriptHook runtime behavior.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

TARGET_MEMBER = "Payload/GTAV.app/Frameworks/ScriptHookV.dylib"
EXPECTED_SHA256 = "a86451f766925adf9fa8dfedd8cfa92f9895bd68fda16b3795e6f747fef2196d"
EXPECTED_UUID = "f768b7b5ad7539f483d38e49234325b5"
EXPECTED_WORDS = {
    0x4DAC: 0xD63F0100,  # blr x8: DllMain(handle,1,NULL)
    0x56B0: 0xF9477688,  # ldr x8, [x20,#0xee8]
    0x56B4: 0xB40002E8,  # cbz x8: NULL scheduler context
    0x570C: 0x9400096B,  # bl _sh_swap
    0x59D0: 0x7100FD1F,  # cmp w8,#0x3f: register cap
    0x59D4: 0x5400014C,  # b.gt: register full
    0x78F34: 0xD63F0020,  # blr x1: callback
    0x78F44: 0x52800048,  # mov w8,#2: terminal status
    0x78F58: 0x97FE3B58,  # bl _sh_swap: callback returned
}

class ABIVerificationError(ValueError):
    pass

def uuid_from_macho(data: bytes) -> str:
    if len(data) < 32:
        raise ABIVerificationError("MACHO_TRUNCATED")
    magic, cpu, _, filetype, ncmds, sizeofcmds, _, _ = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or filetype != 6:
        raise ABIVerificationError("NOT_ARM64_MACHO_DYLIB")
    if not 1 <= ncmds <= 1024 or not 24 <= sizeofcmds <= 1024 * 1024 or 32 + sizeofcmds > len(data):
        raise ABIVerificationError("BAD_LOAD_COMMAND_BOUNDS")
    offset, found = 32, []
    for _ in range(ncmds):
        if offset + 8 > 32 + sizeofcmds:
            raise ABIVerificationError("TRUNCATED_LOAD_COMMAND")
        cmd, size = struct.unpack_from("<II", data, offset)
        if size < 8 or size % 8 or offset + size > 32 + sizeofcmds:
            raise ABIVerificationError("BAD_LOAD_COMMAND")
        if cmd == 0x1B:
            if size != 24:
                raise ABIVerificationError("BAD_UUID_COMMAND")
            found.append(data[offset + 8:offset + 24].hex())
        offset += size
    if len(found) != 1:
        raise ABIVerificationError("UUID_NOT_UNIQUE")
    return found[0]

def audit(data: bytes, *, expected_hash: str = EXPECTED_SHA256) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_hash:
        raise ABIVerificationError("SHA256_MISMATCH")
    uuid = uuid_from_macho(data)
    if uuid != EXPECTED_UUID:
        raise ABIVerificationError("MACHO_UUID_MISMATCH")
    for offset, word in EXPECTED_WORDS.items():
        if len(data) < offset + 4 or struct.unpack_from("<I", data, offset)[0] != word:
            raise ABIVerificationError(f"ARM64_WORD_MISMATCH_0x{offset:x}")
    return {
        "status": "STATIC_ABI_CONTRACT_MATCH",
        "sha256": digest,
        "macho_uuid": "F768B7B5-AD75-39F4-83D3-8E49234325B5",
        "inspected_arm64_words": len(EXPECTED_WORDS),
        "proves_device_callback": False,
        "proves_script_hook_online": False,
        "proves_native_gameplay": False,
    }

def load_input(path: Path) -> bytes:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            info = z.getinfo(TARGET_MEMBER)
            if info.file_size > 32 * 1024 * 1024:
                raise ABIVerificationError("TOO_LARGE")
            return z.read(info)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ABIVerificationError("TOO_LARGE")
    return path.read_bytes()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try:
        result = audit(load_input(args.input))
        status = 0
    except (OSError, KeyError, zipfile.BadZipFile, ABIVerificationError) as exc:
        result = {"status": "REJECTED", "reason": str(exc)}
        status = 1
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return status

if __name__ == "__main__":
    sys.exit(main())
