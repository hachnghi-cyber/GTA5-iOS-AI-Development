"""Package the private account panel with the exact unsigned R85 patrol release."""
import argparse
from copy import copy
import os
from pathlib import Path
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v133_interaction' / 'ios'))
from patch_exact_v133_probe import BRIDGE_PATH, MH_DYLIB, add_panel_dependency, digest, header_info

R85_SHA = '1aa536cf66306aa0885354a5792f0df9597b30048c777a316a050283f088bc1b'
RP53_PATH = 'Payload/GTAV.app/Frameworks/libRP53.dylib'
RP53_SHA = '0175335532a17e4f10c5203cc6795a0a19129d50db758dde12501ef57421c994'
PANEL_SHA = '851288bfc70c6a485ba43be6ad06ad50ad9c70a6a34dbb2d0ff203dfee688d0d'
PANEL_LOAD = b'@loader_path/PoliceRPV133Probe.dylib'


def package(ipa, panel_path, output):
    if output.exists():
        raise FileExistsError('Choose a new IPA output file.')
    panel = panel_path.read_bytes()
    if digest(panel) != PANEL_SHA or header_info(panel)['type'] != MH_DYLIB:
        raise ValueError('Unexpected private panel build.')
    # Hash and copy from the same open archive.
    with ipa.open('rb') as source:
        if digest(source.read()) != R85_SHA:
            raise ValueError('Expected the verified unsigned R85 patrol IPA.')
        source.seek(0)
        with zipfile.ZipFile(source) as original:
            names = original.namelist()
            if len(set(names)) != 62 or len(names) != 62 or BRIDGE_PATH in names:
                raise ValueError('Unexpected R85 archive layout.')
            rp53 = original.read(RP53_PATH)
            info = header_info(rp53)
            if digest(rp53) != RP53_SHA or info['type'] != MH_DYLIB:
                raise ValueError('Unexpected project RP53 library.')
            linked, details = add_panel_dependency(rp53, info, PANEL_LOAD)
            past_command = info['end'] + details['load_command_size']
            if linked[:16] != rp53[:16] or linked[24:info['end']] != rp53[24:info['end']] or linked[past_command:] != rp53[past_command:]:
                raise ValueError('Library content changed after the new load command.')

            # Use a sibling temporary file so only a checked, complete archive can become the output.
            with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
                stage = Path(tmp) / 'candidate.ipa'
                with zipfile.ZipFile(stage, 'x') as archive:
                    archive.comment = original.comment
                    for member in original.infolist():
                        content = linked if member.filename == RP53_PATH else original.read(member)
                        archive.writestr(copy(member), content)
                    entry = zipfile.ZipInfo(BRIDGE_PATH)
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.external_attr = 0o100755 << 16
                    archive.writestr(entry, panel)
                with zipfile.ZipFile(stage) as candidate:
                    if candidate.namelist() != names + [BRIDGE_PATH] or candidate.read(BRIDGE_PATH) != panel:
                        raise ValueError('Packaged panel or archive layout mismatch.')
                    for name in names:
                        expected = linked if name == RP53_PATH else original.read(name)
                        if candidate.read(name) != expected:
                            raise ValueError('R85 archive member failed readback: ' + name)
                os.link(stage, output)  # Same volume, atomic, refuses an existing destination.
    return details


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipa', required=True, type=Path)
    parser.add_argument('--panel', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    package(args.ipa, args.panel, args.out)
    print('Verified unsigned R85 private-panel IPA:', args.out)
