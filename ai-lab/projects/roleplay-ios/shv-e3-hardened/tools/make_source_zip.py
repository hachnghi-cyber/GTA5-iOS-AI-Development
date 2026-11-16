#!/usr/bin/env python3
"""Package only test sources and public-domain diagnostic evidence; never original IPA bytes."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib, json, re, sys
root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root.parent/'OPERATION_RAGE_BREAKTHROUGH_v13.3_RESEARCH_SOURCE.zip'
keep_dirs=['src','tests','include','ios','tools','references']
keep_globs=['*.md','*VALIDATION.json','evidence/*.log','evidence/*.json','evidence/*.csv','evidence/*.txt','evidence/disasm/*.txt','build/*_ios_arm64.o','build/*_ios_arm64_v2.o','build/*-arm64.o']
paths=set()
for d in keep_dirs:
    for p in (root/d).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':paths.add(p)
for g in keep_globs:
    for p in root.glob(g):
        if p.is_file():paths.add(p)
paths={p for p in paths if p.name!='SHA256SUMS.txt'}
files=sorted(paths,key=lambda p:p.relative_to(root).as_posix())
sums=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n' for p in files)
(root/'SHA256SUMS.txt').write_text(sums)
files.append(root/'SHA256SUMS.txt')
with ZipFile(output,'w',ZIP_DEFLATED,compresslevel=8) as z:
    for p in files:
        z.write(p,'OPERATION_RAGE_BREAKTHROUGH_v13.3/'+p.relative_to(root).as_posix())
with ZipFile(output) as z:
    assert z.testzip() is None
    names=z.namelist()
    assert not any(('/extracted/' in x or '/work/' in x or x.endswith('.ipa') or x.endswith('/GTA5')) for x in names)
    print(json.dumps({'artifact':str(output),'size_bytes':output.stat().st_size,
        'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'zip_entries':len(names),'zip_crc':'PASS','includes_original_ipa':False},indent=2))
