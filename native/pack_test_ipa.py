"""Guarded GTA V v11 (exact user-provided build) experimental IPA packer.

NO iOS signing is performed. A compiled, real arm64 GojoTouchBridge.dylib
must be supplied; this deliberately refuses to generate a broken placeholder.
"""
import argparse
import hashlib
import struct
import zipfile
from pathlib import Path


IPA_SHA256 = '232e2f380ef8eaeb60e7930844c5f1a79f05624f7ddd74672031a20985a71301'
COMPAT_SHA256 = '5d18bad7664cc282543098006eff2b2f5274a11ff37c1667e5eab0d8a47c3c43'
COMPAT_PATH = 'Payload/GTAV.app/Frameworks/libgtacompat.dylib'
BRIDGE_PATH = 'Payload/GTAV.app/Frameworks/GojoTouchBridge.dylib'
LOAD_PATH = b'@rpath/GojoTouchBridge.dylib'
MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
MH_DYLIB = 6
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0xC


def digest(data):
    return hashlib.sha256(data).hexdigest()


def header_info(binary):
    if len(binary) < 32:
        raise ValueError('Short Mach-O header')
    magic, cpu, _, filetype, ncmds, size, _, _ = struct.unpack_from('<IiiIIIII', binary)
    if magic != MH_MAGIC_64 or cpu != CPU_TYPE_ARM64:
        raise ValueError('Expected a Mach-O arm64 binary')
    end = 32 + size
    off = 32
    first_section = len(binary)
    existing = []
    for _ in range(ncmds):
        if off + 8 > end:
            raise ValueError('Truncated load commands')
        cmd, cmdsize = struct.unpack_from('<II', binary, off)
        if cmdsize < 8 or off + cmdsize > end:
            raise ValueError('Bad load command size')
        if cmd == LC_SEGMENT_64:
            if cmdsize < 72:
                raise ValueError('Bad LC_SEGMENT_64')
            nsects = struct.unpack_from('<I', binary, off + 64)[0]
            if cmdsize < 72 + nsects * 80:
                raise ValueError('Bad section table')
            for j in range(nsects):
                section_offset = struct.unpack_from('<I', binary, off + 72 + j * 80 + 48)[0]
                if section_offset:
                    first_section = min(first_section, section_offset)
        if cmd == LC_LOAD_DYLIB:
            name_offset = struct.unpack_from('<I', binary, off + 8)[0]
            if 24 <= name_offset < cmdsize:
                name = binary[off + name_offset:off + cmdsize].split(b'\x00')[0]
                existing.append(name)
        off += cmdsize
    if off != end:
        raise ValueError('Header size does not match parsed commands')
    return {'type': filetype, 'ncmds': ncmds, 'size': size, 'end': end,
            'first_section': first_section, 'slack': first_section - end,
            'dylibs': existing}


def patch_compat(original):
    if digest(original) != COMPAT_SHA256:
        raise ValueError('libgtacompat hash differs from exact v11 input')
    info = header_info(original)
    if info['type'] != MH_DYLIB:
        raise ValueError('Target is not a dylib')
    if LOAD_PATH in info['dylibs']:
        raise ValueError('Bridge dependency already exists')
    size = (24 + len(LOAD_PATH) + 1 + 7) & ~7
    if info['slack'] < size:
        raise ValueError('Insufficient header padding; refusing to shift code')
    if any(original[info['end']:info['end'] + size]):
        raise ValueError('Load-command padding is not empty')

    dylib_command = struct.pack('<IIIIII', LC_LOAD_DYLIB, size, 24, 0, 0, 0)
    dylib_command += LOAD_PATH + b'\x00'
    dylib_command += b'\x00' * (size - len(dylib_command))

    patched = bytearray(original)
    struct.pack_into('<I', patched, 16, info['ncmds'] + 1)
    struct.pack_into('<I', patched, 20, info['size'] + size)
    patched[info['end']:info['end'] + size] = dylib_command
    result = bytes(patched)
    updated = header_info(result)
    if len(result) != len(original) or LOAD_PATH not in updated['dylibs']:
        raise AssertionError('Post-patch Mach-O validation failed')
    if updated['ncmds'] != info['ncmds'] + 1:
        raise AssertionError('Unexpected number of commands')
    return result, {'load_command_size': size, 'original_slack': info['slack'],
                    'remaining_slack': updated['slack']}


def check_bridge(binary):
    info = header_info(binary)
    if info['type'] != MH_DYLIB:
        raise ValueError('Bridge is not a Mach-O dylib')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ipa', required=True, type=Path)
    ap.add_argument('--bridge', type=Path, help='Real arm64 dylib built on macOS')
    ap.add_argument('--out', type=Path, help='New unsigned test IPA path')
    opts = ap.parse_args()
    if (opts.bridge is None) != (opts.out is None):
        ap.error('--bridge and --out must be given together, or neither for inspect-only')

    if digest(opts.ipa.read_bytes()) != IPA_SHA256:
        raise ValueError('IPA hash mismatch; refused to patch a different build')
    with zipfile.ZipFile(opts.ipa) as source:
        if source.testzip() is not None:
            raise ValueError('Damaged original IPA')
        if COMPAT_PATH not in source.namelist():
            raise ValueError('Missing compat dylib')
        if BRIDGE_PATH in source.namelist():
            raise ValueError('Bridge already packaged')
        patched, details = patch_compat(source.read(COMPAT_PATH))
        print('Exact IPA and compat hashes: OK')
        print('Load-command patch in memory:', details)
        if opts.bridge is None:
            print('INSPECT ONLY. Nothing was written.')
            return

        bridge_bytes = opts.bridge.read_bytes()
        check_bridge(bridge_bytes)
        if opts.out.exists():
            raise FileExistsError('Output already exists; refusing to overwrite')
        with zipfile.ZipFile(opts.out, mode='x') as result:
            for item in source.infolist():
                result.writestr(item, patched if item.filename == COMPAT_PATH
                                else source.read(item.filename))
            entry = zipfile.ZipInfo(BRIDGE_PATH)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100755 << 16
            result.writestr(entry, bridge_bytes)

    with zipfile.ZipFile(opts.out) as verify:
        if verify.testzip() is not None:
            raise ValueError('Patched ZIP CRC check failed')
        if verify.read(BRIDGE_PATH) != bridge_bytes:
            raise ValueError('Bridge bytes changed during packaging')
        if verify.read(COMPAT_PATH) != patched:
            raise ValueError('Patched compat bytes changed during packaging')
    print('Unsigned experimental IPA created:', opts.out)
    print('NOT INSTALLABLE UNTIL ALL MACH-O CODE SIGNATURES ARE RENEWED.')


if __name__ == '__main__':
    main()
