"""Guarded GTA V v13.3 (exact user-provided build) experimental IPA packer.

NO iOS signing is performed. Only use your own authorized input IPA. A compiled, real arm64 PoliceRPV133Probe.dylib
must be supplied; this deliberately refuses to generate a broken placeholder.
"""
import argparse
import hashlib
import plistlib
import struct
import zipfile
from pathlib import Path


IPA_SHA256 = '7a5e23358e4a72a03322fe016ea08adde1ee6189b0c66f86e656a48649057b89'
# Independently audited 3u export. Main executable SHA/UUID are unchanged.
# No wildcard or --force override: every archive variant is explicitly reviewed.
ADDITIONAL_IPA_SHA256S = frozenset({
    '7ae987a7770610ae42024095861096f8eca45ec39db1a89c223e9d6f2c0c26d7',
})
GTA5_SHA256 = 'f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc'
GTA5_PATH = 'Payload/GTAV.app/GTA5'
PLIST_PATH = 'Payload/GTAV.app/Info.plist'
BRIDGE_PATH = 'Payload/GTAV.app/Frameworks/PoliceRPV133Probe.dylib'
LOAD_PATH = b'@executable_path/Frameworks/PoliceRPV133Probe.dylib'
MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
MH_EXECUTE = 2
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
    if end > len(binary) or ncmds > 4096:
        raise ValueError('Load command table outside binary')
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
            if cmdsize < 24:
                raise ValueError('Short LC_LOAD_DYLIB')
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


def patch_gta5(original):
    if digest(original) != GTA5_SHA256:
        raise ValueError('GTA5 SHA-256 differs from exact v13.3 input')
    info = header_info(original)
    if info['type'] != MH_EXECUTE:
        raise ValueError('Target is not an executable')
    return add_panel_dependency(original, info, LOAD_PATH)


def add_panel_dependency(original, info, load_path):
    if load_path in info['dylibs']:
        raise ValueError('Probe dependency already exists')
    size = (24 + len(load_path) + 1 + 7) & ~7
    if info['slack'] < size:
        raise ValueError('Insufficient header padding; refusing to shift code')
    if any(original[info['end']:info['end'] + size]):
        raise ValueError('Load-command padding is not empty')

    dylib_command = struct.pack('<IIIIII', LC_LOAD_DYLIB, size, 24, 0, 0, 0)
    dylib_command += load_path + b'\x00'
    dylib_command += b'\x00' * (size - len(dylib_command))

    patched = bytearray(original)
    struct.pack_into('<I', patched, 16, info['ncmds'] + 1)
    struct.pack_into('<I', patched, 20, info['size'] + size)
    patched[info['end']:info['end'] + size] = dylib_command
    result = bytes(patched)
    updated = header_info(result)
    if len(result) != len(original) or updated['dylibs'] != info['dylibs'] + [load_path]:
        raise AssertionError('Post-patch Mach-O validation failed')
    if updated['ncmds'] != info['ncmds'] + 1:
        raise AssertionError('Unexpected number of commands')
    return result, {'load_command_size': size, 'original_slack': info['slack'],
                    'remaining_slack': updated['slack']}


def check_bridge(binary):
    info = header_info(binary)
    if info['type'] != MH_DYLIB:
        raise ValueError('Probe is not an arm64 Mach-O dylib')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ipa', required=True, type=Path)
    ap.add_argument('--bridge', type=Path, help='Real arm64 dylib built on macOS')
    ap.add_argument('--out', type=Path, help='New unsigned test IPA path')
    ap.add_argument('--enable-file-sharing', action='store_true',
                    help='Expose Documents/PoliceRP-v13.3-Phase8.txt in iOS Files app')
    ap.add_argument('--enable-tls-probe', action='store_true',
                    help='Add the iOS local network purpose string for a private TLS diagnostic')
    opts = ap.parse_args()
    if (opts.bridge is None) != (opts.out is None):
        ap.error('--bridge and --out must be given together, or neither for inspect-only')

    if digest(opts.ipa.read_bytes()) not in {IPA_SHA256, *ADDITIONAL_IPA_SHA256S}:
        raise ValueError('IPA hash mismatch; refused to patch a different build')
    with zipfile.ZipFile(opts.ipa) as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        if source.testzip() is not None:
            raise ValueError('Damaged original IPA')
        if GTA5_PATH not in source.namelist():
            raise ValueError('Missing GTA5 executable')
        if PLIST_PATH not in source.namelist():
            raise ValueError('Missing app Info.plist')
        if BRIDGE_PATH in source.namelist():
            raise ValueError('Probe already packaged')
        patched, details = patch_gta5(source.read(GTA5_PATH))
        print('Exact IPA and GTA5 executable hashes: OK')
        print('Load-command patch in memory:', details)
        if opts.bridge is None:
            print('INSPECT ONLY. Nothing was written.')
            return

        bridge_bytes = opts.bridge.read_bytes()
        check_bridge(bridge_bytes)
        if opts.out.exists():
            raise FileExistsError('Output already exists; refusing to overwrite')
        plist_bytes = source.read(PLIST_PATH)
        if opts.enable_file_sharing or opts.enable_tls_probe:
            plist = plistlib.loads(plist_bytes)
            if not isinstance(plist, dict):
                raise ValueError('App Info.plist is not a dictionary')
            if opts.enable_file_sharing:
                plist['UIFileSharingEnabled'] = True
                plist['LSSupportsOpeningDocumentsInPlace'] = True
            if opts.enable_tls_probe:
                plist.setdefault('NSLocalNetworkUsageDescription',
                                 'Connect to your paired computer on the local network for the RP diagnostic.')
            fmt = (plistlib.FMT_BINARY if plist_bytes.startswith(b'bplist00')
                   else plistlib.FMT_XML)
            plist_bytes = plistlib.dumps(plist, fmt=fmt, sort_keys=False)
        with zipfile.ZipFile(opts.out, mode='x') as result:
            for item in source.infolist():
                result.writestr(item, patched if item.filename == GTA5_PATH
                                else plist_bytes if item.filename == PLIST_PATH
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
        if verify.read(GTA5_PATH) != patched:
            raise ValueError('Patched GTA5 bytes changed during packaging')
        if verify.read(PLIST_PATH) != plist_bytes:
            raise ValueError('Info.plist bytes changed during packaging')
    print('Unsigned experimental IPA created:', opts.out)
    print('NOT INSTALLABLE UNTIL ALL MACH-O CODE SIGNATURES ARE RENEWED.')


if __name__ == '__main__':
    main()
