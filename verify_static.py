#!/usr/bin/env python3
"""Non-runtime checks against supplied 11.2 IPA; does not modify the IPA."""

import hashlib
import struct
import zipfile
from pathlib import Path

from inject_ipa import (
    GAME_EXE, INSTALL_NAME, add_load_command, commands, get_dylib_names,
    earliest_section_offset, read_macho_header,
)

ROOT = Path(__file__).resolve().parent.parent
IPA = ROOT / "upload" / "GTAV-v11.2(2).ipa"
LIB = "Payload/GTAV.app/Frameworks/libgtacompat.dylib"
COMPAT_SEND_KEY = 0x14EA90
PROLOGUE = bytes.fromhex("ff 43 02 d1 f4 4f 07 a9 fd 7b 08 a9 fd 03 02 91")


def test_inject_header_only():
    with zipfile.ZipFile(IPA) as z:
        exe = z.read(GAME_EXE)
    patched = add_load_command(exe)
    original_cmds = list(commands(exe))
    new_cmds = list(commands(patched))
    assert len(new_cmds) == len(original_cmds) + 1
    assert new_cmds[:-1] == original_cmds
    assert INSTALL_NAME in get_dylib_names(patched)
    assert read_macho_header(patched)[1] == read_macho_header(exe)[1] + 1
    assert len(patched) == len(exe)
    begin = 32 + read_macho_header(exe)[2]
    end = 32 + read_macho_header(patched)[2]
    assert patched[:16] == exe[:16]
    assert patched[24:begin] == exe[24:begin]
    assert patched[end:] == exe[end:]
    assert end < earliest_section_offset(exe)
    print("PASS: Mach-O load command inserted entirely into verified header slack")


def test_custom_key_fingerprint():
    with zipfile.ZipFile(IPA) as z:
        lib = z.read(LIB)
    assert lib[COMPAT_SEND_KEY:COMPAT_SEND_KEY + 16] == PROLOGUE
    assert len(lib) == 2_825_664
    assert hashlib.sha256(lib).hexdigest() == (
        "a506499088aed93b842b2ebf3894eec2b41b5355db0d7e70b95bfe5345aac563"
    )
    print("PASS: exact 11.2(2) native key bridge fingerprint")


def main():
    test_inject_header_only()
    test_custom_key_fingerprint()
    print("STATIC CHECKS PASS — NOT A DEVICE/CRASH TEST")


if __name__ == "__main__":
    main()
