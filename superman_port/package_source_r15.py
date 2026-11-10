"""Produce a reproducible source-only Superman FX R15 Actions upload.

No original TamedMods .asi/.wav/ini and no precompiled iOS binary are bundled.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "out" / "SupermanFX-R15-Flight-Animations-ARM64-Source.zip"
SOURCES = [
    ".github/workflows/build-superman-fx-r15.yml",
    "superman_port/SupermanR6.cpp",
    "superman_port/SupermanAudio.mm",
    "superman_port/shv_api.hpp",
    "superman_port/build_ios.sh",
    "superman_port/libScriptHookV.tbd",
    "superman_port/test_host.cpp",
    "superman_port/test_Superman.ini",
    "superman_port/package_fx_r15.py",
    "superman_port/package_source_r15.py",
    "superman_port/R15-README.md",
]


def main() -> None:
    if ARCHIVE.exists():
        raise FileExistsError(f"Keeping prior artifact intact: {ARCHIVE}")
    if len(set(SOURCES)) != len(SOURCES):
        raise ValueError("Duplicate source entry")
    for name in SOURCES:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError(f"Unsafe source path: {name}")
        if not (ROOT / name).is_file():
            raise FileNotFoundError(ROOT / name)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zip_file:
        for name in SOURCES:
            zip_file.write(ROOT / name, arcname=name)
    with zipfile.ZipFile(ARCHIVE) as zip_file:
        assert zip_file.testzip() is None, "Source ZIP CRC failed"
        assert zip_file.namelist() == SOURCES, "Source ZIP contents changed"
        assert not any(name.endswith((".asi", ".wav", ".ipa", ".dylib"))
                       for name in zip_file.namelist())
    report = {
        "package": ARCHIVE.name,
        "sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "sources": SOURCES,
        "archive_crc": "PASS",
        "contains_arm64_plugin": False,
        "build_requires_macos_xcode": True,
        "gameplay_tested_on_iphone": False,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
