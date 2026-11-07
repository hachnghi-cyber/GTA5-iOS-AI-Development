"""Read-only regression checks for the exact user-provided v11 compat dylib."""
import argparse
import zipfile
from pack_test_ipa import COMPAT_PATH, LOAD_PATH, header_info, patch_compat


def test(ipa_path):
    with zipfile.ZipFile(ipa_path) as package:
        original = package.read(COMPAT_PATH)
    before = header_info(original)
    patched, result = patch_compat(original)
    after = header_info(patched)
    diffs = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    assert len(original) == len(patched)
    assert diffs
    assert all(i in range(16, 24) or
               i in range(before['end'], before['end'] + result['load_command_size'])
               for i in diffs)
    assert after['ncmds'] == before['ncmds'] + 1
    assert LOAD_PATH in after['dylibs']
    assert patched[before['first_section']:] == original[before['first_section']:]

    bad = bytearray(original)
    bad[50000] ^= 1
    try:
        patch_compat(bytes(bad))
    except ValueError:
        pass
    else:
        raise AssertionError('Missing SHA-256 guard on modified input')
    print('Mach-O header tests passed: only header padding changed; __text intact')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ipa')
    test(parser.parse_args().ipa)
