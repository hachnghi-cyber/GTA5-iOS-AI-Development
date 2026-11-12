#!/usr/bin/env python3
"""Compare ZIP inventories of two IPA files (size/CRC only, not cryptographic diff)."""
import argparse
import json
import zipfile
from pathlib import Path

def compare(before, after):
    def inventory(path):
        with zipfile.ZipFile(path) as z:
            return {i.filename: (i.file_size, i.CRC) for i in z.infolist() if not i.is_dir()}
    old, new = inventory(before), inventory(after)
    return {"before": str(before), "after": str(after),
            "method": "zip-filename-size-crc32",
            "added_files": sorted(new.keys() - old.keys()),
            "removed_files": sorted(old.keys() - new.keys()),
            "modified_files": sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--output")
    a = p.parse_args()
    text = json.dumps(compare(a.before, a.after), indent=2, ensure_ascii=False) + "\n"
    if a.output:
        path = Path(a.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf8")
    print(text)

if __name__ == "__main__":
    main()
