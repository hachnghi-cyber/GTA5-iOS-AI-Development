#!/usr/bin/env python3
"""Fail-closed byte integrity check of the exact Phase12 E0/E1/E3 UNSIGNED IPA.
Not a signing, device, callback, or RAGE gameplay assertion.
"""
import argparse,hashlib,json,plistlib,stat,sys,zipfile
from pathlib import Path

IPA_SHA256="7ae987a7770610ae42024095861096f8eca45ec39db1a89c223e9d6f2c0c26d7"
GTA_SHA256="f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc"
SHV_SHA256="a86451f766925adf9fa8dfedd8cfa92f9895bd68fda16b3795e6f747fef2196d"
PLUGIN="Payload/GTAV.app/Frameworks/RBPProbe.shv.dylib"
GTA="Payload/GTAV.app/GTA5"
SHV="Payload/GTAV.app/Frameworks/ScriptHookV.dylib"
PLIST="Payload/GTAV.app/Info.plist"
DIGESTS={0:"0aa55cbd9bb47b76755b621c329bea08222255ff86ff99f6bd60274ccd52a9b4",
         1:"2347b74f776afdf9cbd970263c56f4d49781a6c23b1a147bd8229dc80fb946cc",
         3:"781adc210d395f0a0c681e8bed2662db70ae269fb3c3c5e619f51513fce86cf3"}
class Rejected(ValueError):pass

def sha256_stream(f):
    h=hashlib.sha256()
    for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def index_ipa(z,extra_allowed=False):
    found={};total=0
    for info in z.infolist():
        name=info.filename
        if not name or name in found:raise Rejected("duplicate/empty ZIP entry")
        if not name.startswith("Payload/") or "\\" in name or name.startswith("/"):
            raise Rejected("entry escapes Payload namespace")
        if any(x in ("",".","..") for x in name.rstrip("/").split("/")):
            raise Rejected("path traversal/invalid component")
        typ=(info.external_attr>>16)&0o170000
        if typ not in (0,stat.S_IFDIR,stat.S_IFREG):
            raise Rejected("symlink or nonregular archive entry")
        if info.file_size>150*1024*1024:raise Rejected("oversized entry")
        total+=info.file_size
        if total>300*1024*1024:raise Rejected("oversized expansion")
        found[name]=info
    if not extra_allowed and PLUGIN in found:raise Rejected("original IPA already has probe")
    return found

def check_archive_pair(a,b,*,plugin_sha256):
    x=index_ipa(a);y=index_ipa(b,extra_allowed=True)
    if set(y)-set(x)!={PLUGIN} or set(x)-set(y):
        raise Rejected("wrong set of ZIP entries: exactly one new probe required")
    if y[PLUGIN].is_dir():raise Rejected("probe must be a file")
    with b.open(PLUGIN) as f:
        if sha256_stream(f)!=plugin_sha256:raise Rejected("wrong stage plugin hash")
    for name,meta in x.items():
        if meta.is_dir()!=y[name].is_dir() or meta.file_size!=y[name].file_size:
            raise Rejected("original entry metadata/content size mismatch: "+name)
        if not meta.is_dir():
            with a.open(name) as o,b.open(name) as n:
                if sha256_stream(o)!=sha256_stream(n):
                    raise Rejected("original file changed: "+name)
    return len(x)

def verify(original,diagnostic,stage,*,verify_original_hash=True):
    if stage not in DIGESTS:raise Rejected("unsupported stage")
    if not original.is_file() or not diagnostic.is_file():raise Rejected("IPA missing")
    if original.resolve()==diagnostic.resolve():raise Rejected("same original and diagnostic")
    if verify_original_hash:
        with original.open("rb") as f:
            if sha256_stream(f)!=IPA_SHA256:raise Rejected("original IPA SHA256 mismatch")
    with zipfile.ZipFile(original) as a,zipfile.ZipFile(diagnostic) as b:
        count=check_archive_pair(a,b,plugin_sha256=DIGESTS[stage])
        with a.open(PLIST) as f:meta=plistlib.load(f)
        if meta.get("CFBundleIdentifier")!="com.macport.gtav" or meta.get("CFBundleExecutable")!="GTA5":
            raise Rejected("bundle ID / executable mismatch")
        if meta.get("MinimumOSVersion")!="16.3":raise Rejected("wrong iOS target")
        with a.open(GTA) as f:
            if sha256_stream(f)!=GTA_SHA256:raise Rejected("GTA5 mismatch")
        with a.open(SHV) as f:
            if sha256_stream(f)!=SHV_SHA256:raise Rejected("ScriptHookV mismatch")
        return {"status":"EXACT_UNSIGNED_DIAGNOSTIC_IPA_MATCH","stage":stage,
          "original_entries_byte_identical":count,"extra_entries":1,
          "module_sha256":DIGESTS[stage],"bundle_id":"com.macport.gtav",
          "unsigned_requires_resigning":True,"device_verified":False,
          "roleplay_gameplay_verified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original",type=Path,required=True)
    p.add_argument("--diagnostic",type=Path,required=True)
    p.add_argument("--stage",type=int,choices=(0,1,3),required=True)
    p.add_argument("--json-out",type=Path)
    a=p.parse_args()
    try:out=verify(a.original,a.diagnostic,a.stage);rc=0
    except (Rejected,zipfile.BadZipFile,KeyError,OSError,plistlib.InvalidFileException) as e:
        out={"status":"REJECTED","reason":str(e)};rc=2
    result=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.json_out:a.json_out.write_text(result)
    print(result,end="")
    return rc
if __name__=="__main__":sys.exit(main())
