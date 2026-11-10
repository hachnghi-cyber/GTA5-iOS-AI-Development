"""Replace only the Superman ScriptHook plugin in an R11 GTA V iOS IPA.

Usage:
    python3 superman_port/package_fx_r15.py OLD-R11.ipa NEW-SupermanR6.shv.dylib [OUT-R15.ipa]

This does NOT recompile the plugin. Build it on macOS with build_ios.sh or the
provided workflow. Resulting IPA requires app-level signing before installation.
"""
from __future__ import annotations

import hashlib
import json
import plistlib
import struct
import sys
import zipfile
from pathlib import Path

ENTRY = "Payload/GTAV.app/Frameworks/SupermanR6.shv.dylib"
EXPECTED_OLD_PLUGIN = "3e818823c4af85be898885cab240de13081d40a05c611f3e167ec54e407de3fd"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exports_dllmain(data: bytes) -> bool:
    if len(data) < 32 or data[:4] != bytes.fromhex("cffaedfe"):
        return False
    if struct.unpack_from("<I", data, 4)[0] != 0x0100000C:
        return False
    ncmds = struct.unpack_from("<I", data, 16)[0]
    if ncmds > 300:
        return False
    offset = 32
    for _ in range(ncmds):
        if offset + 8 > len(data):
            return False
        cmd, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > len(data):
            return False
        if cmd == 2 and size >= 24:
            symoff, nsyms, stroff, strsize = struct.unpack_from("<IIII", data, offset + 8)
            if stroff + strsize > len(data) or symoff + nsyms * 16 > len(data):
                return False
            strings = data[stroff:stroff + strsize]
            for i in range(nsyms):
                stridx, typ, _, _, address = struct.unpack_from("<IBBHQ", data, symoff + 16*i)
                if stridx < len(strings) and strings[stridx:].split(b"\0", 1)[0] == b"_DllMain":
                    return bool(typ & 1 and address)
        offset += size
    return False


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: package_fx_r15.py OLD-R11.ipa NEW-SupermanR6.shv.dylib [OUT-R15.ipa]")
    original = Path(sys.argv[1]).resolve()
    plugin_file = Path(sys.argv[2]).resolve()
    output = (Path(sys.argv[3]) if len(sys.argv) == 4
              else original.with_name("GTAV-v11.4-SupermanFX-R15-Flight-TEST.ipa")).resolve()
    if output == original or output == plugin_file:
        raise ValueError("Refusing to overwrite input files")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    plugin = plugin_file.read_bytes()
    if not exports_dllmain(plugin):
        raise ValueError("New plugin must be arm64 Mach-O exporting _DllMain")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(original) as source:
        if source.testzip() is not None:
            raise ValueError("Original IPA is damaged")
        if ENTRY not in source.namelist():
            raise ValueError("Original IPA lacks Superman plugin; requires R11")
        old = source.read(ENTRY)
        if sha(old) != EXPECTED_OLD_PLUGIN:
            raise ValueError("Wrong base: expected the verified R11 Superman plugin")
        if sha(old) == sha(plugin):
            raise ValueError("Plugin is identical to R11, no new version compiled")
        entries = source.infolist()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
            for entry in entries:
                target.writestr(entry, plugin if entry.filename == ENTRY else source.read(entry.filename))
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(output) as result:
        if result.testzip() is not None:
            raise ValueError("Output IPA failed CRC check")
        if result.namelist() != source.namelist():
            raise ValueError("IPA file ordering changed")
        changed = [name for name in result.namelist() if result.read(name) != source.read(name)]
        if changed != [ENTRY]:
            raise ValueError(f"Unexpected changed files: {changed!r}")
        info = plistlib.loads(result.read("Payload/GTAV.app/Info.plist"))
        app = "Payload/GTAV.app/" + info["CFBundleExecutable"]
        if app not in result.namelist():
            raise ValueError("Main executable missing")
        sound_count = len([n for n in result.namelist()
                           if n.startswith("Payload/GTAV.app/Frameworks/Superman_SFX/") and n.endswith(".wav")])
        if sound_count != 19:
            raise ValueError("R11 expected all 19 sound assets")
    report = {
        "revision": "R15 smooth takeoff retry, grounded slam animation, landing and hand charge visuals -- EXPERIMENTAL",
        "new_ipa": str(output),
        "sha256": sha(output.read_bytes()),
        "plugin_sha256": sha(plugin),
        "changed_entries": changed,
        "preserved_19_wavs": True,
        "archive_crc": "PASS",
        "requires_apple_resign": True,
        "requires_real_iphone_test": True,
    }
    report_file = output.with_suffix(".validation.json")
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
