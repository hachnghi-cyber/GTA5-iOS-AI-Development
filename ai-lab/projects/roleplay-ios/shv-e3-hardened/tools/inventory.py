"""Static evidence collector for user-supplied iOS IPA (no IPA modifications)."""
import argparse, hashlib, json, os, plistlib, re, subprocess, zipfile

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def cmd(*args):
    p=subprocess.run(args,capture_output=True,text=True,check=False)
    return p.stdout if p.returncode==0 else ''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('ipa');ap.add_argument('--out',default='evidence/inventory.json');a=ap.parse_args()
    work=os.path.dirname(os.path.realpath(a.out));os.makedirs(work,exist_ok=True)
    bundle=os.path.join(work,'extracted','Payload','GTAV.app')
    with zipfile.ZipFile(a.ipa) as z:
        good=z.testzip()
        if good:raise ValueError('corrupt ZIP member: '+good)
        z.extractall(os.path.join(work,'extracted'))
        names=z.namelist()
    info=plistlib.load(open(os.path.join(bundle,'Info.plist'),'rb'))
    binaries=[]
    executable=os.path.join(bundle,info['CFBundleExecutable'])
    for path in [executable]+sorted(os.path.join(bundle,'Frameworks',x) for x in os.listdir(os.path.join(bundle,'Frameworks')) if x.endswith('.dylib')):
        head=cmd('llvm-objdump','--macho','--private-headers',path)
        exports=cmd('llvm-objdump','--macho','--exports-trie',path)
        deps=cmd('llvm-objdump','--macho','--dylibs-used',path)
        sym=cmd('llvm-objdump','--syms',path)
        obj=cmd('llvm-objdump','--macho','--objc-meta-data',path)
        chained=cmd('llvm-objdump','--macho','--chained-fixups',path)
        uu=re.search(r'uuid ([A-F0-9-]{36})',head)
        cpu=re.search(r'MH_MAGIC_64\s+(ARM\S*)\s+(\w+)',head)
        entry={'path':os.path.relpath(path,bundle),'bytes':os.path.getsize(path),'sha256':sha(path),
               'uuid':uu.group(1) if uu else None,
               'cpu':cpu.group(1) if cpu else 'UNPARSED',
               'deps':[line.strip().split(' (')[0] for line in deps.splitlines()[1:] if ' (' in line],
               'export_count':len(re.findall(r'^0x[0-9a-fA-F]+\s',exports,re.M)),
               'symbol_table_entry_count':len(re.findall(r'^[0-9a-fA-F]{16}\s',sym,re.M)),
               'cpp_rtti_zti_symbol_count':len(re.findall(r'^.*__ZTI[^\n]*$',sym,re.M)),
               'dyld_chained_imports_count':int(re.search(r'imports_count\s*=\s*(\d+)',chained).group(1)) if re.search(r'imports_count\s*=\s*(\d+)',chained) else None,
               'dyld_import_symbols_sample':re.findall(r'name_offset\s*=\s*\d+\s+\(([^)]+)\)',chained)[:40],
               'objc_meta_chars':len(obj),
               'interesting_exports':re.findall(r'^0x[0-9a-fA-F]+\s+([^\n]*(?:native|script|Online|online|p2p|MMP_|_script)[^\n]*)',exports,re.I|re.M)[:250]}
        binaries.append(entry)
    out={'source_ipa':os.path.basename(a.ipa),'ipa_sha256':sha(a.ipa),'zip_member_count':len(names),
         'bundle_id':info.get('CFBundleIdentifier'),'bundle_version':info.get('CFBundleShortVersionString'),
         'build_date':info.get('MacportBuildDate'),'minimum_ios':info.get('MinimumOSVersion'),
         'bonjour_services':info.get('NSBonjourServices'),'binaries':binaries}
    with open(a.out,'w') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({'ipa_sha256':out['ipa_sha256'],'member_count':len(names),'binaries':len(binaries),'uuid':binaries[0]['uuid']},indent=2))

if __name__=='__main__': main()
