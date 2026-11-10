"""Finish the R10 experimental IPA after a macOS runner builds the FX plugin.

Usage:
    python3 superman_port/package_fx_r10.py /path/to/SupermanR6.shv.dylib

Only replaces the previously installed Superman plugin. Every other R10 entry
(including the 19 WAVs and hold-to-cast fix) stays byte-identical. App-level
Apple signing must be performed on the resulting IPA before installation.
"""
from __future__ import annotations

import hashlib
import json
import plistlib
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "out/GTAV-v11.4-CustomKeys-HoldFix-R10-TEST.ipa"
OUTPUT = ROOT / "out/GTAV-v11.4-SupermanFX-Hold-R11-TEST.ipa"
ENTRY = "Payload/GTAV.app/Frameworks/SupermanR6.shv.dylib"
EXPECTED_SHA = "88fe0bdceb68d5174c6bc5a9b4fd96ab743267f6772fbee5c5b451550fc1213a"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exported(macho: bytes, name: bytes) -> bool:
    assert macho[:4] == bytes.fromhex("cffaedfe")
    assert struct.unpack_from("<I", macho, 4)[0] == 0x0100000C, "Not ARM64"
    ncmds = struct.unpack_from("<I", macho, 16)[0]
    current = 32
    for _ in range(ncmds):
        command, size = struct.unpack_from("<II", macho, current)
        if command == 2:
            symoff, nsyms, stroff, strsize = struct.unpack_from("<IIII", macho, current + 8)
            strings = macho[stroff:stroff + strsize]
            for pos in range(nsyms):
                stridx, typ, _, _, addr = struct.unpack_from('<IBBHQ', macho, symoff + 16 * pos)
                if 0 <= stridx < len(strings) and strings[stridx:].split(b'\0', 1)[0] == name:
                    return bool(typ & 1 and addr)
        current += size
    return False


def main() -> None:
    assert len(sys.argv) == 2, "Supply the freshly built SupermanR6.shv.dylib"
    plugin = Path(sys.argv[1]).read_bytes()
    assert exported(plugin, b'_DllMain'), "Not a valid iOS ScriptHookV plugin"
    assert sha(INPUT.read_bytes()) == EXPECTED_SHA, "Unexpected base R10 IPA"
    with zipfile.ZipFile(INPUT) as old:
        assert ENTRY in old.namelist()
        assert sha(plugin) != sha(old.read(ENTRY)), "This appears to be the original R8 plugin"
        names = old.namelist()
        with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
            for info in old.infolist():
                dst.writestr(info, plugin if info.filename == ENTRY else old.read(info.filename))
    with zipfile.ZipFile(INPUT) as old, zipfile.ZipFile(OUTPUT) as dst:
        assert dst.testzip() is None
        assert dst.namelist() == names
        changed = [n for n in names if old.read(n) != dst.read(n)]
        assert changed == [ENTRY], changed
        plist = plistlib.loads(dst.read('Payload/GTAV.app/Info.plist'))
        assert 'Payload/GTAV.app/' + plist['CFBundleExecutable'] in names
        assert len([n for n in names if n.startswith('Payload/GTAV.app/Frameworks/Superman_SFX/')]) == 19
    report = {
        "revision": "R11 experimental FX + hold-to-cast",
        "output_sha256": sha(OUTPUT.read_bytes()),
        "plugin_sha256": sha(plugin),
        "changed_files": [ENTRY],
        "everything_else_unchanged": True,
        "zip_crc": "PASS",
        "device_fx_test": "REQUIRED",
        "ios_resign_required": True,
    }
    (ROOT / 'out/R11-FX-Validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
