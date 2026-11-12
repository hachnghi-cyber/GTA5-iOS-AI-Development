#!/usr/bin/env python3
"""Generate SHA256 manifest of v0.8 source files (excluding manifest itself)."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
files={}
for p in root.rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(root).as_posix()
    if rel=='MANIFEST_SHA256_V08.json' or rel.endswith('.pyc'):continue
    files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
(root/'MANIFEST_SHA256_V08.json').write_text(json.dumps({
    'version':'0.8','status':'SOURCE ONLY, NO IPA, NO iOS DYNAMIC LIBRARY',
    'v12_original_GTA5_sha256':'d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b',
    'files':files
},indent=2,ensure_ascii=False)+'\n')
print(f'Manifest: {len(files)} files')
