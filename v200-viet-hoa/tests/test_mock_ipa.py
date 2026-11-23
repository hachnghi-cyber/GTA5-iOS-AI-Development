"""Copyright-free end-to-end assembly tests with synthetic IPA and Mach-O.

Static structural smoke test; does not execute on iOS or sign an IPA.
"""
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import sys
import tempfile
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
import inject_ipa as injector


def thin_macho(mach_type, dylib_id=False):
    data = bytearray(8192)
    if dylib_id:
        name = injector.DYLIB_LOAD.encode() + b"\x00"
        command_size = (24 + len(name) + 7) & ~7
        struct.pack_into("<IiiIIIII", data, 0, 0xFEEDFACF, 0x0100000C, 0, mach_type, 1, command_size, 0, 0)
        struct.pack_into("<IIIIII", data, 32, 0xD, command_size, 24, 2, 0, 0)
        data[56:56 + len(name)] = name
    else:
        struct.pack_into("<IiiIIIII", data, 0, 0xFEEDFACF, 0x0100000C, 0, mach_type, 1, 152, 0, 0)
        struct.pack_into("<II", data, 32, 0x19, 152)
        struct.pack_into("<I", data, 32 + 64, 1)
        struct.pack_into("<Q", data, 32 + 72 + 40, 64)
        struct.pack_into("<I", data, 32 + 72 + 48, 4096)
    return bytes(data)


def expect_reject(fn):
    try:
        fn()
    except (ValueError, AssertionError):
        return
    raise AssertionError("Unexpectedly accepted invalid input")


def test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        app = "Payload/MockGame.app/"
        plist = plistlib.dumps({"CFBundleExecutable": "MockExecutable",
                                 "CFBundleIdentifier": "io.github.playgta5ios.app"})
        executable = thin_macho(2)
        ipa = root / "base.ipa"
        with zipfile.ZipFile(ipa, "w") as z:
            z.writestr(app + "Info.plist", plist)
            z.writestr(app + "MockExecutable", executable)
            z.writestr(app + "SomeUserFile.txt", "original-preserved")
            z.writestr(app + "_CodeSignature/CodeResources", b"obsolete")
        base_hash = hashlib.sha256(ipa.read_bytes()).hexdigest()
        injector.BASE_SHA256 = base_hash
        dylib = root / injector.DYLIB_NAME
        dylib.write_bytes(thin_macho(6, True))
        pack = root / "VietnameseAccented.nvp"
        index = json.dumps([["x64/demo.gxt2", 0, 4]], separators=(",", ":")).encode()
        pack.write_bytes(b"NOVAPAK1" + struct.pack("<Q", len(index)) + index + b"TEST")
        injector.NVP_SHA256 = hashlib.sha256(pack.read_bytes()).hexdigest()
        output = root / "output-unsigned.ipa"
        injector.make_ipa(ipa, dylib, pack, output)
        assert hashlib.sha256(ipa.read_bytes()).hexdigest() == base_hash
        with zipfile.ZipFile(output) as z:
            assert z.testzip() is None
            files = z.namelist()
            assert app + "Frameworks/" + injector.DYLIB_NAME in files
            assert app + "VietnameseAccented.nvp" in files
            assert app + "_CodeSignature/CodeResources" not in files
            assert z.read(app + "SomeUserFile.txt") == b"original-preserved"
            assert z.read(app + "VietnameseAccented.nvp") == pack.read_bytes()
            result = z.read(app + "MockExecutable")
            assert result[4096:] == executable[4096:]
            assert injector.DYLIB_LOAD in injector.macho_info(result)["libraries"]
        expect_reject(lambda: injector.make_ipa(output, dylib, pack, root / "double.ipa"))
        assert not (root / "double.ipa").exists()
        with open(pack, "ab") as out:
            out.write(b"X")
        expect_reject(lambda: injector.make_ipa(ipa, dylib, pack, root / "wrong-nvp.ipa"))
        assert not (root / "wrong-nvp.ipa").exists()
        expect_reject(lambda: injector.patch_macho_load(result))
        assert not (root / "output-unsigned.ipa.building").exists()
        print("PASS: mock IPA assembly, archive preservation, duplicate/tampered input rejection")


if __name__ == "__main__":
    test()
