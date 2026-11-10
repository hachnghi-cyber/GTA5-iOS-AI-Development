"""Read the Mach-O symbol table and imported frameworks without macOS tools."""
from pathlib import Path
import argparse
import struct


def inspect(path: Path, needle: str, show_sections: bool = False):
    raw = path.read_bytes()
    if struct.unpack_from('<I', raw)[0] != 0xFEEDFACF:
        raise ValueError(f'{path}: not a Mach-O arm64 64-bit image')
    ncmds = struct.unpack_from('<I', raw, 16)[0]
    offset = 32
    symbol_table = None
    libraries = []
    sections = []
    for _ in range(ncmds):
        cmd, length = struct.unpack_from('<II', raw, offset)
        if cmd == 2:
            symbol_table = struct.unpack_from('<IIII', raw, offset + 8)
        if cmd == 25:
            segment_name, vmaddr, vmsize, fileoff, filesize, _, _, nsects, _ = struct.unpack_from('<16sQQQQIIII', raw, offset + 8)
            for j in range(nsects):
                p = offset + 72 + j * 80
                sectname, segname, addr, size, sectoff, _, _, _, flags, _, _, _ = struct.unpack_from('<16s16sQQIIIIIIII', raw, p)
                sections.append((sectname.rstrip(b'\0').decode(), addr, size, sectoff, flags))
        if cmd & 0x7FFFFFFF in (0xC, 0x18, 0x1F, 0x23):
            relative = struct.unpack_from('<I', raw, offset + 8)[0]
            pos = offset + relative
            libraries.append(raw[pos:raw.index(b'\0', pos)].decode(errors='replace'))
        offset += length
    assert symbol_table, 'LC_SYMTAB not found'
    symoff, nsyms, stroff, _ = symbol_table
    public = []
    imports = []
    for i in range(nsyms):
        ix, type_, sect, _, va = struct.unpack_from('<IBBHQ', raw, symoff + i * 16)
        name = raw[stroff + ix:raw.index(b'\0', stroff + ix)].decode(errors='replace')
        if not name or needle.lower() not in name.lower():
            continue
        if (type_ & 0x0E) == 0 and va == 0:
            imports.append(name)
        elif type_ & 1:
            public.append((va, name))
    print(f'Image: {path} ({len(raw)} bytes, {nsyms} symbols)')
    print('Linked libraries:')
    for name in libraries:
        print(' ', name)
    if show_sections:
        print('Sections:')
        for name, addr, size, sectoff, flags in sections:
            print(f'  {name:20s} vmaddr={addr:08x} size={size:08x} fileoff={sectoff:08x} flags={flags:08x}')
    print(f'Public symbols matching {needle!r}:')
    for va, name in public:
        print(f'  {va:016x} {name}')
    print(f'Imported symbols matching {needle!r}:')
    for name in imports:
        print(' ', name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    parser.add_argument('--filter', default='')
    parser.add_argument('--sections', action='store_true')
    args = parser.parse_args()
    inspect(args.path, args.filter, args.sections)
