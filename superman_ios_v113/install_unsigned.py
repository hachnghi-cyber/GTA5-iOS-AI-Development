#!/usr/bin/env python3
"""Opt-in GTA V iOS 11.3 Superman ARM64 IPA integrator.

Static checks only. The result's previous Apple signature is INVALIDATED and
the whole IPA must be re-signed by the user. No IPA is overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile


GAME = "Payload/GTAV.app/GTA5"
COMPAT = "Payload/GTAV.app/Frameworks/libgtacompat.dylib"
PLUGIN = "Payload/GTAV.app/Frameworks/libSupermanIOS.dylib"
CONFIG = "Payload/GTAV.app/Frameworks/Superman_iOS.json"
SFX_DIR = "Payload/GTAV.app/Frameworks/Superman_SFX/"
SDK_ROOT = Path(__file__).resolve().parent
EXPECTED_COMPAT_SHA = "992148cae5866e20768b1e054075cbc7b9480731ffc3996a4a6f69d61177cb64"
ALLOWED_GAME_SHA = {
    "606aa87f9c22b40f167ae2bdf00ddf451b957801efb27169e38fa7af5c673aeb": "stock-v11.3",
    "0533fb5fd4c85c1741b6d42651ec64c196ba93834a6bdf7148cd1ca523776e6d": "v11.3-with-CustomTouch",
}
MAGIC_64 = 0xFEEDFACF
CPU_ARM64 = 0x0100000C
MH_DYLIB = 6
MH_EXECUTE = 2
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0xC
DYLIB_NAME = b"@executable_path/Frameworks/libSupermanIOS.dylib\x00"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def macho_header(data: bytes) -> tuple[int, list[tuple[int, int, int]], int]:
    if len(data) < 32:
        raise ValueError("Truncated Mach-O")
    magic, cpu, _, filetype, ncmds, commands_size, _, _ = struct.unpack_from("<8I", data)
    if magic != MAGIC_64 or cpu != CPU_ARM64 or ncmds > 2000:
        raise ValueError("File is not an expected arm64 Mach-O")
    command_end = 32 + commands_size
    if command_end > len(data):
        raise ValueError("Truncated load commands")
    position = 32
    commands = []
    for _ in range(ncmds):
        if position + 8 > command_end:
            raise ValueError("Malformed load command")
        command, length = struct.unpack_from("<II", data, position)
        if length < 8 or length % 8 or position + length > command_end:
            raise ValueError("Malformed load command length")
        commands.append((command, position, length))
        position += length
    if position != command_end:
        raise ValueError("Mach-O header has unexpected padding inside commands")
    return filetype, commands, command_end


def patch_game(original: bytes) -> bytes:
    version = ALLOWED_GAME_SHA.get(sha256(original))
    if not version:
        raise ValueError("GTA5 SHA256 not recognized: use the verified v11.3 base or CustomTouch IPA")
    filetype, commands, end = macho_header(original)
    if filetype != MH_EXECUTE:
        raise ValueError("GTA5 is not MH_EXECUTE")
    first_section = len(original)
    for command, offset, length in commands:
        if command in {0xC, 0xD, 0x18, 0x1F, 0x23} and length >= 24:
            name_offset = struct.unpack_from("<I", original, offset + 8)[0]
            if 24 <= name_offset < length:
                name = original[offset + name_offset:offset + length].split(b"\x00", 1)[0]
                if b"libSupermanIOS.dylib" in name:
                    raise ValueError("Superman is already linked in this IPA")
        if command == LC_SEGMENT_64:
            if length < 72:
                raise ValueError("Invalid LC_SEGMENT_64")
            number_of_sections = struct.unpack_from("<I", original, offset + 64)[0]
            if length < 72 + 80 * number_of_sections:
                raise ValueError("Invalid Mach-O section table")
            for i in range(number_of_sections):
                section_offset = offset + 72 + 80 * i
                payload_size = struct.unpack_from("<Q", original, section_offset + 40)[0]
                payload_offset = struct.unpack_from("<I", original, section_offset + 48)[0]
                if payload_size and payload_offset:
                    first_section = min(first_section, payload_offset)

    command_length = (24 + len(DYLIB_NAME) + 7) & ~7
    if end + command_length > first_section:
        raise ValueError("Insufficient safe Mach-O load-command header space")
    if any(original[end:end + command_length]):
        raise ValueError("Mach-O load-command padding contains data, refusing to patch")
    command = struct.pack("<6I", LC_LOAD_DYLIB, command_length, 24, 0, 0x10000, 0x10000)
    command += DYLIB_NAME + bytes(command_length - len(command) - len(DYLIB_NAME))
    modified = bytearray(original)
    struct.pack_into("<I", modified, 16, len(commands) + 1)
    struct.pack_into("<I", modified, 20, end + command_length - 32)
    modified[end:end + command_length] = command
    patched = bytes(modified)
    _, new_commands, _ = macho_header(patched)
    if len(new_commands) != len(commands) + 1 or new_commands[-1][0] != LC_LOAD_DYLIB:
        raise ValueError("Mach-O patch verification failed")
    return patched


def safe_archive_members(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("Duplicate IPA entries")
    for name in names:
        if not name.startswith("Payload/") or ".." in Path(name).parts or name.startswith("/"):
            raise ValueError(f"Unexpected IPA entry: {name}")
    return names


def create_unsigned(ipa: Path, dylib: Path, output: Path, sfx_zip: Path | None = None) -> dict:
    if output.exists() or output in {ipa, dylib}:
        raise ValueError("Output must be a new, nonexistent file")
    binary = dylib.read_bytes()
    plugin_type, commands, _ = macho_header(binary)
    if (plugin_type != MH_DYLIB or len(binary) < 10_000 or
            not any(cmd == LC_SEGMENT_64 for cmd, _, _ in commands) or
            not any(cmd == 0x1D for cmd, _, _ in commands) or
            b"SupermanIOS.v113.positions" not in binary):
        raise ValueError("Not the expected Superman iOS ARM64 dylib")
    config = (SDK_ROOT / "Superman_iOS.json").read_bytes()
    json.loads(config)
    additions = {PLUGIN: binary, CONFIG: config}
    allowed_sounds = {"takeoff.wav", "heat_vision.wav", "thunder_clap.wav", "ground_pound.wav"}
    if sfx_zip is not None:
        with zipfile.ZipFile(sfx_zip) as original_sounds:
            for sound in sorted(allowed_sounds):
                entry = "Superman_RELEASE/Superman_SFX/" + sound
                info = original_sounds.getinfo(entry)
                if info.file_size > 3_000_000:
                    raise ValueError(f"Unusually large audio asset: {entry}")
                additions[SFX_DIR + sound] = original_sounds.read(entry)
    else:
        for item in sorted((SDK_ROOT / "Superman_SFX").glob("*.wav")):
            if item.name in allowed_sounds:
                additions[SFX_DIR + item.name] = item.read_bytes()

    input_sha = sha256(ipa.read_bytes())
    with zipfile.ZipFile(ipa) as original:
        members = safe_archive_members(original)
        if GAME not in members or COMPAT not in members:
            raise ValueError("Unexpected GTA V iOS app structure")
        if any(name in members for name in additions):
            raise ValueError("Superman plugin or asset already present; refusing overwrite")
        if sha256(original.read(COMPAT)) != EXPECTED_COMPAT_SHA:
            raise ValueError("libgtacompat mismatch, refusing modification")
        source_exe = original.read(GAME)
        label = ALLOWED_GAME_SHA[sha256(source_exe)]
        new_exe = patch_game(source_exe)

        with tempfile.TemporaryDirectory(prefix="smios-ipa-") as temp_dir:
            staged = Path(temp_dir) / "candidate.ipa"
            with zipfile.ZipFile(staged, "w", allowZip64=True) as out:
                out.comment = original.comment
                for info in original.infolist():
                    contents = new_exe if info.filename == GAME else original.read(info.filename)
                    out.writestr(info, contents)
                for name, contents in additions.items():
                    info = zipfile.ZipInfo(name, date_time=(2026, 11, 10, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = ((0o100755 if name == PLUGIN else 0o100644) << 16)
                    out.writestr(info, contents)

            with zipfile.ZipFile(staged) as verified:
                if verified.testzip() is not None:
                    raise ValueError("Output ZIP failed integrity check")
                if set(verified.namelist()) != set(members) | set(additions):
                    raise ValueError("IPA member list unexpectedly changed")
                for name in members:
                    if name != GAME and verified.read(name) != original.read(name):
                        raise ValueError(f"Unrelated IPA file changed: {name}")
                if verified.read(GAME) != new_exe:
                    raise ValueError("GTA5 load-command change differs from expected")
                for name, contents in additions.items():
                    if verified.read(name) != contents:
                        raise ValueError(f"Plugin or asset differs after repack: {name}")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as target, staged.open("rb") as source:
                shutil.copyfileobj(source, target, 1 << 20)

    report = {
        "input": ipa.name,
        "input_sha256": input_sha,
        "input_variant": label,
        "output": output.name,
        "output_sha256": sha256(output.read_bytes()),
        "modified_entries": [GAME],
        "added_entries": sorted(additions),
        "existing_entries_preserved": len(members) - 1,
        "sound_files": len(additions) - 2,
        "device_tested": False,
        "signing": "UNSIGNED: entire app must be validly re-signed before installation",
    }
    output.with_suffix(".report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--dylib", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sfx-zip", type=Path, help="Original TamedMods Superman ZIP for personal-use WAV assets")
    args = parser.parse_args()
    print(json.dumps(create_unsigned(args.ipa.resolve(), args.dylib.resolve(), args.output.resolve(), args.sfx_zip.resolve() if args.sfx_zip else None), indent=2, ensure_ascii=False))
