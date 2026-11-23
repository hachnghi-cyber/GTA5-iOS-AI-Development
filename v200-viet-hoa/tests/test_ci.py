#!/usr/bin/env python3
"""Self-contained CI tests using synthetic, non-copyrighted data."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
from inject_ipa import DYLIB_LOAD, macho_info, patch_macho_load


def invoke(cli, pack, mods, successful):
    result = subprocess.run([str(cli), str(pack), str(mods)], text=True, capture_output=True)
    assert (result.returncode == 0) == successful, (result.stdout, result.stderr)
    return result.stdout


def importer_checks(cli, root):
    files = [("x64/data/lang/american.rpf/demo.gxt2", b"HELLO"),
             ("common/data/ui/fontmap.xml", b"<font/>")]
    offset = 0
    index = []
    for path, contents in files:
        index.append([path, offset, len(contents)])
        offset += len(contents)
    payload = b"".join(content for _, content in files)
    encoded = json.dumps(index, separators=(",", ":")).encode()
    good = b"NOVAPAK1" + struct.pack("<Q", len(encoded)) + encoded + payload
    pack = root / "pack.nvp"
    pack.write_bytes(good)
    mods = root / "Documents" / "Mods"
    assert "changed=1" in invoke(cli, pack, mods, True)
    assert "changed=0" in invoke(cli, pack, mods, True)
    for path, content in files:
        assert (mods / path).read_bytes() == content
    damaged = root / "damaged.nvp"
    damaged.write_bytes(b"BADPAK!!" + good[8:])
    invoke(cli, damaged, mods, False)
    damaged.write_bytes(good[:-1])
    invoke(cli, damaged, mods, False)
    malformed = encoded.replace(b"x64/", b"../a", 1)
    if len(malformed) == len(encoded):
        damaged.write_bytes(b"NOVAPAK1" + struct.pack("<Q", len(malformed)) + malformed + payload)
        invoke(cli, damaged, root / "unsafe" / "Mods", False)
    assert (mods / files[0][0]).read_bytes() == files[0][1]
    (mods / files[0][0]).write_bytes(b"tampered")
    invoke(cli, pack, mods, False)
    conflict = root / "other" / "Mods"
    target = conflict / files[0][0]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")
    invoke(cli, pack, conflict, False)
    assert target.read_bytes() == b"existing"


def macho_checks():
    blob = bytearray(8192)
    struct.pack_into("<IiiIIIII", blob, 0, 0xFEEDFACF, 0x0100000C, 0, 2, 1, 152, 0, 0)
    struct.pack_into("<II", blob, 32, 0x19, 152)
    struct.pack_into("<I", blob, 32 + 64, 1)
    sect = 32 + 72
    struct.pack_into("<Q", blob, sect + 40, 64)
    struct.pack_into("<I", blob, sect + 48, 4096)
    old = bytes(blob)
    modified, before, after = patch_macho_load(old)
    assert len(modified) == len(old)
    assert modified[4096:] == old[4096:]
    assert before["ncmds"] == 1 and after["ncmds"] == 2
    assert DYLIB_LOAD in macho_info(modified)["libraries"]
    try:
        patch_macho_load(modified)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate dylib unexpectedly allowed")


if __name__ == "__main__":
    executable = PROJECT / "build" / "nvp_install_cli"
    assert executable.is_file(), "Compile native installer CLI first"
    with tempfile.TemporaryDirectory() as folder:
        importer_checks(executable, Path(folder))
    macho_checks()
    print("PASS: synthetic NVP extraction, repeat install, tamper/collision rejection, Mach-O patch")
