#!/usr/bin/env python3
"""Experimental, offline ARM64 binary injection for the specifically hashed GTAV iOS V10.2 IPA.
Each hook checks the original bytes, branch displacements, free code cave, file mappings,
and archive structure. It never modifies the source IPA in place.
No claim of runtime validation or signing is made.
"""
import hashlib, json, re, struct, subprocess, sys, zipfile, copy
from pathlib import Path

ROOT=Path('/mnt/data')
INPUT=ROOT/'GTA-V10.2-An-Nut-Livestream(2).ipa'
OUTPUT=ROOT/'GTA-V10.3-Camera-FOV-THU-NGHIEM-UNSIGNED.ipa'
REPORT=ROOT/'GTA-V10.3-Camera-Patch-Report.json'
SRC_C=ROOT/'libgtacompat-original.dylib'
SRC_G=ROOT/'GTA5-original'
EXPECTED_IPA_SHA='7e1b3f39623047c97e9a7b5fa643ef9d2c6f009f916f3d7c595eabf87b905373'
UI_CODE_OFF=0x1a9800
UI_VA=UI_CODE_OFF
GAME_CODE_OFF=0x25f9980
GAME_VA=0x100000000+GAME_CODE_OFF
STATE_VA=0x103ba2000

def sha(data): return hashlib.sha256(data).hexdigest()
def u32(data,o): return struct.unpack_from('<I',data,o)[0]
def put32(data,o,v): struct.pack_into('<I',data,o,v&0xffffffff)
def sign26(x): return x-(1<<26) if x&(1<<25) else x

def branch_word(old,src,dst):
    assert src%4==0 and dst%4==0
    assert old>>26 in (0b000101,0b100101), f'not B/BL @ {src:#x}: {old:#x}'
    assert (dst-src)%4==0
    delta=(dst-src)//4
    assert -(1<<25)<=delta<(1<<25),f'branch outside +-128MB: {src:#x} to {dst:#x}'
    return old&0xfc000000 | (delta&0x3ffffff)

def make_b(src,dst):return branch_word(0x14000000,src,dst)

def adrp_patch(old,src,dst):
    assert (old&0x9f000000)==0x90000000, f'not adrp:{old:#x}'
    delta=(dst>>12)-(src>>12)
    assert -(1<<20)<=delta<(1<<20)
    return (old&~((3<<29)|(0x7ffff<<5)))|((delta&3)<<29)|(((delta>>2)&0x7ffff)<<5)

def add_pageoff_patch(old,dst):
    assert (old&0xffc00000)==0x91000000, f'not add x,x,#imm: {old:#x}'
    return (old&~(0xfff<<10))|((dst&0xfff)<<10)

def get_relocs(obj):
    p=subprocess.run(['llvm-objdump','--macho','--reloc',str(obj)],capture_output=True,text=True,check=True)
    result=[]
    for line in p.stdout.splitlines():
        m=re.match(r'^([0-9a-f]{8})\s+(?:True|False)\s+long\s+True\s+(BR26|PAGOF12|PAGE21)\s+False\s+(_\w+)',line.strip())
        if m: result.append((int(m.group(1),16),m.group(2),m.group(3)))
    return result

def patch_code_bin(binfile,obj,base,targets):
    data=bytearray(binfile.read_bytes());relocs=get_relocs(obj)
    assert len(relocs)>0
    for off,kind,name in relocs:
        assert name in targets, (kind,name)
        old=u32(data,off); target=targets[name];src=base+off
        if kind=='BR26':new=branch_word(old,src,target)
        elif kind=='PAGE21':new=adrp_patch(old,src,target)
        elif kind=='PAGOF12':new=add_pageoff_patch(old,target)
        else: raise ValueError(kind)
        put32(data,off,new)
    return data,relocs

def get_sym_offset(obj,symbol):
    p=subprocess.run(['llvm-objdump','--macho','--syms',str(obj)],capture_output=True,text=True,check=True)
    m=re.search(r'(?m)^([0-9a-f]{16})\s+g\s+F\s+__TEXT,__text\s+'+re.escape(symbol)+r'$',p.stdout)
    assert m,symbol
    return int(m.group(1),16)

def change_bytes(buf,off,expected,new,reason,changes):
    assert buf[off:off+len(new)]==expected, f'wrong hook original for {reason} at {off:#x}: {buf[off:off+len(new)].hex()} != {expected.hex()}'
    buf[off:off+len(new)]=new
    changes.append(dict(offset=hex(off),reason=reason,original=expected.hex(),patched=new.hex()))

def copy_to_cave(buf,off,code,label,changes):
    assert off%4==0 and len(code)%4==0
    assert all(b==0 for b in buf[off:off+len(code)]), f'code cave not empty: {label}'
    buf[off:off+len(code)]=code
    changes.append(dict(offset=hex(off),size=len(code),reason=label))

def main():
    assert sha(INPUT.read_bytes())==EXPECTED_IPA_SHA,'input IPA hash mismatch; refusing to patch foreign build'
    with zipfile.ZipFile(INPUT) as z:
        assert z.testzip() is None
        files=z.namelist()
        game_names=[n for n in files if n.endswith('/GTA5')]; assert len(game_names)==1,game_names
        compat_names=[n for n in files if n.endswith('/libgtacompat.dylib')]; assert len(compat_names)==1,compat_names
        game_name=game_names[0];compat_name=compat_names[0]
        original_g=z.read(game_name);original_c=z.read(compat_name)
        assert sha(original_g)==sha(SRC_G.read_bytes()) and sha(original_c)==sha(SRC_C.read_bytes()),'original extracted binaries mismatch'
        g=bytearray(original_g);c=bytearray(original_c)
        assert len(g)>GAME_CODE_OFF+0x400 and len(c)>UI_CODE_OFF+0x400
        # Existing branch in libgtacompat cave at 0x1a95e8: BL existing objc addObject message stub.
        orig_bl=u32(c,0x1a95e8)
        assert orig_bl>>26==0b100101
        objc_add=0x1a95e8+sign26(orig_bl&0x3ffffff)*4
        assert 0x1000<objc_add<0x190000,hex(objc_add)
        print('existing ObjC addObject call target',hex(objc_add))

        ui_targets=dict(_ROWFROM=0x1de54,_OBJCADD=objc_add,_UI_RESUME=0x1a95f0)
        ui,ui_relocs=patch_code_bin(ROOT/'gtav_ui_camera_patch.bin',ROOT/'gtav_ui_camera_patch.o',UI_VA,ui_targets)
        ui_changes=[];game_changes=[]
        copy_to_cave(c,UI_CODE_OFF,ui,'UI ARM64 handler with 4 new Trainer toggles',ui_changes)
        change_bytes(c,0x1a95ec,bytes.fromhex('f60741f8'),struct.pack('<I',make_b(0x1a95ec,UI_VA)),'Trainer Players row-injection hook; displaced ldr in new code',ui_changes)

        game_symbols={
            '_CAM_STATE':STATE_VA,
            '_PLAYER_PED_ID':0x100d4ee04,
            '_IS_PED_IN_ANY_VEHICLE':0x100d11388,
            '_CAM_GET':0x100c08938,
            '_IS_GAMEPLAY_CAM_RENDERING':0x100c090a0,
            '_CAM_SET':0x100c08940,
            '_GAME_TICK_RESUME':0x10003d258,
            '_FOV_FP_RESUME':0x100377b10,
            '_FOV_FOLLOW_RESUME':0x1003a9d9c,
        }
        game_code,game_relocs=patch_code_bin(ROOT/'gtav_game_camera_patch.bin',ROOT/'gtav_game_camera_patch.o',GAME_VA,game_symbols)
        copy_to_cave(g,GAME_CODE_OFF,game_code,'game camera handler: PlayerPed, Vehicle, Cam Mode and FOV',game_changes)
        tick=GAME_VA+get_sym_offset(ROOT/'gtav_game_camera_patch.o','_game_camera_tick')
        fp=GAME_VA+get_sym_offset(ROOT/'gtav_game_camera_patch.o','_first_person_fov_hook')
        follow=GAME_VA+get_sym_offset(ROOT/'gtav_game_camera_patch.o','_follow_vehicle_fov_hook')
        change_bytes(g,0x3d254,bytes.fromhex('f60300aa'),struct.pack('<I',make_b(0x10003d254,tick)),'game thread: consume new camera toggles',game_changes)
        change_bytes(g,0x377b0c,bytes.fromhex('08c005bd'),struct.pack('<I',make_b(0x100377b0c,fp)),'first-person shooter FOV output hook',game_changes)
        change_bytes(g,0x3a9d98,bytes.fromhex('fd7b46a9'),struct.pack('<I',make_b(0x1003a9d98,follow)),'follow-vehicle camera FOV output hook',game_changes)
        assert g[:0x3d254]==original_g[:0x3d254], 'unexpected game alteration before hook'
        assert c[:0x1a95ec]==original_c[:0x1a95ec], 'unexpected compat alteration before hook'
        # Header/type, mapped RW state region verified via known segment region and _bss extent.
        assert 0x103ba0688<=STATE_VA<0x103ba4000
        # All patch sites in executable __TEXT VM mapped file, and built image unchanged in size.
        assert len(g)==len(original_g) and len(c)==len(original_c)
        assert g[:4]==b'\xcf\xfa\xed\xfe' and c[:4]==b'\xcf\xfa\xed\xfe'
        # Repackage preserving ordering and zip entry metadata, excluding old invalid signatures.
        removed=[]
        with zipfile.ZipFile(OUTPUT,'w') as dst:
            for zi in z.infolist():
                if '/_CodeSignature/' in zi.filename or zi.filename.endswith('/CodeResources'):
                    removed.append(zi.filename);continue
                blob=g if zi.filename==game_name else c if zi.filename==compat_name else z.read(zi.filename)
                dst.writestr(copy.copy(zi),blob)
        # Verify every archived entry relative to original for unchanged files
        with zipfile.ZipFile(OUTPUT) as znew:
            assert znew.testzip() is None
            for name in znew.namelist():
                a=z.read(name);b=znew.read(name)
                if name not in (game_name,compat_name): assert a==b,name
            assert znew.read(game_name)==g and znew.read(compat_name)==c
        report={
            'status':'EXPERIMENTAL_BINARY_PATCH_UNSIGNED_NOT_IPHONE_TESTED',
            'source':str(INPUT),'source_sha256':EXPECTED_IPA_SHA,'output':str(OUTPUT),'output_sha256':sha(OUTPUT.read_bytes()),
            'features':{'trainer':'first-person vehicle ON/OFF and 60,75,90 FOV independent toggles',
             'state':'auto off at next launch; high bits excluded from existing 0..24 persistence loop',
             'first_person':'game tick runs player vehicle test; save previous view; use mode=4; restore mode on leave/disable',
             'fov':'hooks camFirstPersonShooterCamera::UpdateBlendedAnimatedFov and camFollowVehicleCamera::ComputeDesiredFov',
             'fov_selection':'90 wins over 75 wins over 60; turn all off for default'},
            'cave_ui':hex(UI_VA),'cave_game':hex(GAME_VA),'bss_state_vmaddr':hex(STATE_VA),
            'ui_relocations':[{'offset':hex(o),'kind':k,'target':n} for o,k,n in ui_relocs],
            'game_relocations':[{'offset':hex(o),'kind':k,'target':n} for o,k,n in game_relocs],
            'ui_changes':ui_changes,'game_changes':game_changes,
            'original_game_sha256':sha(original_g),'game_patched_sha256':sha(g),
            'original_compat_sha256':sha(original_c),'compat_patched_sha256':sha(c),
            'signature_entries_removed':removed,
            'limitations':['Never run in iPhone; first-person camera FOV behavior must be validated in-game.',
                           'May be unstable with Freecam, cutscenes, and online contexts; save game data and test on disposable install.',
                           'All code signatures invalidated; IPA requires proper signing before install.',
                           'Independent FOV choices are nonexclusive switches; if multiple ON, higher FOV wins.',
                           'Not ready for general public release.'],
        }
        REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False))
        print('OK',OUTPUT,OUTPUT.stat().st_size,sha(OUTPUT.read_bytes()));print('UI offsets:',ui_changes);print('GAME offsets:',game_changes)

if __name__=='__main__':main()
