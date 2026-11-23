#!/usr/bin/env python3
"""Tests for R6 Story translation default ON, toggle, R4/R5 migrations."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "build" / "nvp_install_r5_cli"
NAME = "Việt hoá Cốt truyện"

def synth(path):
    names = [
      "common/data/ui/fontmap.xml",
      "x64/data/cdimages/scaleform_frontend.rpf/font_lib_editor.gfx",
      "x64/data/cdimages/scaleform_frontend.rpf/font_lib_sc.gfx",
      "x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.gfx",
      "x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.ytd"
    ]
    names.extend(f"x64/data/lang/american.rpf/file{i:03d}.gxt2" for i in range(608))
    names.extend(f"x64/data/lang/american_REL.rpf/file{i:03d}.gxt2" for i in range(608))
    assert len(names) == 1221
    offsets = []; contents = []
    start = 0
    for name in names:
        content = b"sample" + name.encode()
        offsets.append([name, start, len(content)])
        contents.append(content)
        start += len(content)
    idx = json.dumps(offsets, separators=(",", ":")).encode()
    path.write_bytes(b"NOVAPAK1" + struct.pack("<Q", len(idx)) + idx + b"".join(contents))
    return dict(zip(names, contents))

def call(pack, docs, success=True):
    result = subprocess.run([str(CLI), str(pack), str(docs)], capture_output=True, text=True)
    assert (result.returncode == 0) == success, (result.stdout, result.stderr)
    return result

with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    pack = base / "pack.nvp"
    data = synth(pack)
    docs = base / "Documents"
    docs.mkdir()
    mods = docs / "Mods"
    disabled = mods / (NAME + ".off")
    enabled = mods / NAME
    call(pack, docs)
    assert enabled.is_dir() and not disabled.exists()
    assert all((enabled / name).read_bytes() == b for name, b in data.items())
    diag = docs / "PGVI_Status.log"
    assert "result=0" in diag.read_text()
    assert "mod_on=1" in diag.read_text()
    assert (docs / ".pg_story_vietnamese_r5_seeded").is_file()
    call(pack, docs)  # Idempotent
    enabled.rename(disabled)  # Native Mods switch OFF
    call(pack, docs)
    assert disabled.is_dir() and not enabled.exists()  # Keep user OFF
    disabled.rename(enabled)  # User enables again
    call(pack, docs)
    assert enabled.is_dir() and not disabled.exists()
    shutil.rmtree(enabled)  # Remove mod
    call(pack, docs)
    assert not disabled.exists() and not enabled.exists(), "Removed mod was reinstalled"

with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    pack = base / "pack.nvp"
    data = synth(pack)
    docs = base / "Documents"
    docs.mkdir()
    mods = docs / "Mods"
    for name, payload in data.items():
        out = mods / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(payload)
    (docs / ".mugoat_story_v200_installed").write_bytes(b"PGVI-V200-ACCENTED-R3\n")
    call(pack, docs)
    assert (mods / NAME).is_dir()
    assert all(not (mods / name).exists() for name in data)
    assert not (docs / ".mugoat_story_v200_installed").exists()
    call(pack, docs)
    assert (mods / NAME).is_dir()

# Upgrade R5 with existing default-OFF folder. R6 should turn ON once, then preserve OFF.
with tempfile.TemporaryDirectory() as temporary:
    base=Path(temporary)
    pack=base/"pack.nvp"
    files=synth(pack)
    docs=base/"Documents"
    docs.mkdir()
    old=docs/"Mods"/(NAME+".off")
    for name, contents in files.items():
        dest=old/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(contents)
    (docs/".pg_story_vietnamese_r5_seeded").write_bytes(b"PGVI-V200-STORY-R5\n")
    # Exercise the /var-like symbolic-link prefix via a linked Documents path.
    alias=base/"linked-documents"
    alias.symlink_to(docs,target_is_directory=True)
    call(pack,alias)
    on=docs/"Mods"/NAME
    assert on.is_dir() and not old.exists()
    assert (docs/".pg_story_vietnamese_r6_activated").is_file()
    on.rename(old)
    call(pack,alias)
    assert old.is_dir() and not on.exists(), "User preference not preserved"

print("PASS: R6 default ON, native toggle, keep user OFF, removal and R4/R5 migration")
