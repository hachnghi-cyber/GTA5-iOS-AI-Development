#!/usr/bin/env python3
"""Independent static verification. It cannot prove runtime compatibility on iPhone."""
import struct,zipfile,hashlib,json
from pathlib import Path
D=Path('/mnt/data')
a=D/'GTA-V10.2-An-Nut-Livestream(2).ipa'
b=D/'GTA-V10.3-Camera-FOV-THU-NGHIEM-UNSIGNED.ipa'
r=json.loads((D/'GTA-V10.3-Camera-Patch-Report.json').read_text())

def segments(data):
 assert struct.unpack_from('<I',data)[0]==0xfeedfacf
 n=struct.unpack_from('<I',data,16)[0]; off=32;res=[]
 for _ in range(n):
  cmd,sz=struct.unpack_from('<II',data,off);assert sz>=8 and off+sz<=len(data)
  if cmd==0x19:
   name,vmaddr,vmsize,fileoff,filesize,maxprot,initprot,nsects,flags=struct.unpack_from('<16sQQQQIIII',data,off+8)
   sec=[]
   for j in range(nsects):
    k=off+72+j*80
    secname,segname,svm,ssz,fo,align,ro,nr,flags,s1,s2,s3=struct.unpack_from('<16s16sQQIIIIIIII',data,k)
    sec.append((secname.split(b'\0')[0].decode(),svm,ssz))
   res.append((name.split(b'\0')[0].decode(),vmaddr,vmsize,fileoff,filesize,initprot,sec))
  off+=sz
 return res

def h(s):return hashlib.sha256(s).hexdigest()
def word(buf,o):return struct.unpack_from('<I',buf,o)[0]
def signed26(x):return x-(1<<26) if x&(1<<25) else x
def brtarget(buf,o,base):
 w=word(buf,o)
 assert w>>26 in [5,37]
 return base+o+4*signed26(w&0x3ffffff)
def adrpvalue(w,addr):
 immlo=(w>>29)&3;immhi=(w>>5)&0x7ffff;imm=(immhi<<2)|immlo
 if imm & (1<<20):imm-=1<<21
 return (addr&~0xfff)+(imm<<12)

with zipfile.ZipFile(a) as za,zipfile.ZipFile(b) as zb:
 assert za.testzip() is None and zb.testzip() is None
 orig=dict((x,za.read(x)) for x in za.namelist())
 new=dict((x,zb.read(x)) for x in zb.namelist())
 assert set(orig)-set(new)==set(r['signature_entries_removed'])
 changed=[name for name in new if orig[name]!=new[name]]
 assert sorted(changed)==sorted(['Payload/GTAV.app/GTA5','Payload/GTAV.app/Frameworks/libgtacompat.dylib'])
 g=new['Payload/GTAV.app/GTA5'];c=new['Payload/GTAV.app/Frameworks/libgtacompat.dylib']
 gs=segments(g);cs=segments(c)
 print('Original and patched Mach-O executable segments:')
 for label,segs,addr in [('GAME',gs,0x1025f9980),('COMPAT',cs,0x1a9800)]:
  hit=[s for s in segs if s[1]<=addr<s[1]+s[2]]
  assert len(hit)==1 and hit[0][5]&4,('not executable code cave',label,hit)
  print(label,'code cave',hex(addr),'mapped in',hit[0][0],'prot',hit[0][5])
 data=[x for x in gs if x[0]=='__DATA']
 assert len(data)==1 and data[0][1]<=0x103ba2000<data[0][1]+data[0][2]
 for name,sa,ssz in data[0][6]:assert not(sa<=0x103ba2000<sa+ssz),('state collides with section',name)
 print('Writable zero-fill state address is inside __DATA, outside sections')
 assert c[0x1a9800:0x1a9804]==orig['Payload/GTAV.app/Frameworks/libgtacompat.dylib'][0x1a95ec:0x1a95f0]
 checkpoints=[('UI jump',c,0x1a95ec,0,0x1a9800),('Trainer tick',g,0x3d254,0x100000000,0x1025f9980),('first-person FOV',g,0x377b0c,0x100000000,0x1025f9980+0xd0),('vehicle FOV',g,0x3a9d98,0x100000000,0x1025f9980+0x100)]
 # symbol addresses from object are source of truth
 import subprocess,re
 dump=subprocess.run(['llvm-objdump','--macho','--syms',str(D/'gtav_game_camera_patch.o')],capture_output=True,text=True,check=True).stdout
 syms={m.group(2):int(m.group(1),16) for m in re.finditer(r'(?m)^([0-9a-f]{16})\s+g\s+F\s+__TEXT,__text\s+(\w+)$',dump)}
 expected={'_game_camera_tick':0x3d254,'_first_person_fov_hook':0x377b0c,'_follow_vehicle_fov_hook':0x3a9d98}
 for n,at in expected.items():
  assert brtarget(g,at,0x100000000)==0x1025f9980+syms[n],n
 assert brtarget(c,0x1a95ec,0)==0x1a9800
 print('All 4 original ARM64 hook redirects resolve to expected injected functions')
 # Resolve linked ARM64 branches and ADRP/ADD external references, compare reloc data.
 targets={'_CAM_STATE':0x103ba2000,'_PLAYER_PED_ID':0x100d4ee04,'_IS_PED_IN_ANY_VEHICLE':0x100d11388,'_IS_GAMEPLAY_CAM_RENDERING':0x100c090a0,'_CAM_GET':0x100c08938,'_CAM_SET':0x100c08940,'_GAME_TICK_RESUME':0x10003d258,'_FOV_FP_RESUME':0x100377b10,'_FOV_FOLLOW_RESUME':0x1003a9d9c}
 for reldata in r['game_relocations']:
  addr=0x1025f9980+int(reldata['offset'],16)
  ins=word(g,addr-0x100000000);target=targets[reldata['target']];kind=reldata['kind']
  if kind=='BR26':assert brtarget(g,addr-0x100000000,0x100000000)==target,reldata
  elif kind=='PAGE21':assert adrpvalue(ins,addr)==(target&~0xfff),reldata
  else:assert ((ins>>10)&0xfff)==(target&0xfff),reldata
 # UI external relocations
 unitarget={'_ROWFROM':0x1de54,'_OBJCADD':0x1401e0,'_UI_RESUME':0x1a95f0}
 for rel in r['ui_relocations']:
  addr=0x1a9800+int(rel['offset'],16)
  assert brtarget(c,addr,0)==unitarget[rel['target']]
 print('All',len(r['game_relocations'])+len(r['ui_relocations']),'linked ARM64 relocations resolve correctly')
 # Global diff coverage: only expected patches, no incidental edits
 def diff_spans(before,after):
  ranges=[];on=None
  for i,(x,y) in enumerate(zip(before,after)):
   if x!=y and on is None:on=i
   elif x==y and on is not None:ranges.append((on,i));on=None
  if on is not None:ranges.append((on,len(before)))
  return ranges
 for name,patched,records in [('game',g,r['game_changes']),('compat',c,r['ui_changes'])]:
  before=orig['Payload/GTAV.app/GTA5' if name=='game' else 'Payload/GTAV.app/Frameworks/libgtacompat.dylib']
  changes=diff_spans(before,patched)
  allowed=[(int(d['offset'],16),int(d['offset'],16)+(d.get('size',4))) for d in records]
  assert all(any(start<=s<=e<=stop for start,stop in allowed) for s,e in changes), (name,changes[:10])
  print(name,'byte-change clusters',len(changes),'only within expected patches')
print('PASS: ZIP CRC, unchanged app resources, Mach-O images, branches, relocations, state, diff boundaries')
