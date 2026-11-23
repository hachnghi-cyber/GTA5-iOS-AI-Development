#!/usr/bin/env python3
"""Read-only preflight for Story Mode NOVAPAK1 translation packs; never prints content."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

MAGIC=b'NOVAPAK1'
FONTS=frozenset({
  'common/data/ui/fontmap.xml',
  'x64/data/cdimages/scaleform_frontend.rpf/font_lib_editor.gfx',
  'x64/data/cdimages/scaleform_frontend.rpf/font_lib_sc.gfx',
  'x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.gfx',
  'x64/data/cdimages/scaleform_platform_pc.rpf/font_lib_efigs_pc.ytd',
})
LANG=('x64/data/lang/american.rpf/','x64/data/lang/american_REL.rpf/')

def check(ok,msg):
    if not ok: raise ValueError(msg)

def path_kind(path):
    check(isinstance(path,str) and path and all(c.isascii() and (c.isalnum() or c in '/._-') for c in path),'invalid path characters')
    check(not path.startswith('/') and not path.endswith('/') and '//' not in path and '..' not in path.split('/'),'unsafe path')
    if path in FONTS: return 'font'
    for prefix in LANG:
        if path.startswith(prefix) and path.endswith('.gxt2') and '/' not in path[len(prefix):]:
            return prefix[:-1]
    raise ValueError('non-Story-mode resource: '+path)

def gxt2(data,name):
    check(len(data)>=16 and data[:4]==b'2TXG',name+': invalid GXT2 header')
    (n,)=struct.unpack_from('<I',data,4)
    end=8+8*n
    first=end+8
    check(first<=len(data) and data[end:end+4]==b'2TXG',name+': invalid table')
    (claimed,)=struct.unpack_from('<I',data,end+4)
    check(claimed==len(data),name+': wrong GXT2 length')
    for i in range(n):
        (_,pos)=struct.unpack_from('<II',data,8+8*i)
        check(first<=pos<len(data),name+': offset overflow')
        stop=data.find(b'\0',pos)
        check(stop>=0,name+': missing null terminator')
        try: data[pos:stop].decode('utf-8')
        except UnicodeDecodeError as exc: raise ValueError(name+': invalid UTF-8') from exc
    return n

def inspect(path,require_expected=False):
    raw=Path(path).read_bytes()
    check(16<len(raw)<=64*1024*1024 and raw[:8]==MAGIC,'wrong NOVAPAK1 header or size')
    (idx_size,)=struct.unpack_from('<Q',raw,8)
    check(0<idx_size<=4*1024*1024 and 16+idx_size<len(raw),'bad index length')
    try: entries=json.loads(raw[16:16+idx_size].decode('utf-8'))
    except (ValueError,UnicodeError) as exc: raise ValueError('bad JSON index') from exc
    check(isinstance(entries,list) and 0<len(entries)<=4096,'bad entry count')
    begin=16+idx_size
    next_pos=0
    seen=set()
    counts=Counter()
    texts=0
    for entry in entries:
        check(isinstance(entry,list) and len(entry)==3,'invalid entry')
        name,offset,size=entry
        check(type(offset)==int and type(size)==int and offset==next_pos and size>=0 and begin+offset+size<=len(raw),'invalid offset/size')
        kind=path_kind(name)
        check(name.lower() not in seen,'duplicate entry')
        seen.add(name.lower())
        body=raw[begin+offset:begin+offset+size]
        if kind=='font':
            if name.endswith('.xml'):
                # Rockstar fontmap has non-standard comment syntax; do not use strict XML parser.
                check(b'<font_lib>' in body and b'</font_lib>' in body,'missing font library markers')
            if name.endswith('.gfx'): check(body[:4]==b'GFX\x08','invalid GFX header')
            if name.endswith('.ytd'): check(body[:4]==b'RSC7','invalid YTD texture header')
        else: texts+=gxt2(body,name)
        next_pos+=size
        counts[kind]+=1
    check(begin+next_pos==len(raw),'extra payload bytes')
    if require_expected:
        check(dict(counts)=={'font':5,'x64/data/lang/american.rpf':608,'x64/data/lang/american_REL.rpf':608},'wrong Story-mode resource count')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'pack_bytes':len(raw),
      'entries':len(entries),'gxt2_files':len(entries)-counts['font'],
      'font_files':counts['font'],'text_entries':texts,
      'distribution':dict(counts),'status':'structural_validation_passed',
      'device_tested':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pack',type=Path)
    p.add_argument('--require-mugoat-layout',action='store_true')
    p.add_argument('--json',action='store_true')
    args=p.parse_args()
    result=inspect(args.pack,args.require_mugoat_layout)
    print(json.dumps(result,indent=2,ensure_ascii=False) if args.json else result)
