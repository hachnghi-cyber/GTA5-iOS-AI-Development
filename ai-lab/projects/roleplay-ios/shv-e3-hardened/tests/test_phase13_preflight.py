"""Synthetic security regressions; no proprietary IPA or signing secret in CI."""
import hashlib,io,stat,sys,unittest,warnings,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import verify_existing_probe_ipa as ipa
import check_development_profile as signing

def pack(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w") as z:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",UserWarning)
            for name,data in entries:z.writestr(name,data)
    out.seek(0)
    return out

class ArchivePreflight(unittest.TestCase):
    def setUp(self):
        self.base=[("Payload/",""),("Payload/GTAV.app/GTA5",b"BINARY"),
                   ("Payload/GTAV.app/Info.plist",b"PLIST")]
        self.mod=b"host-only dummy"
        self.hash=hashlib.sha256(self.mod).hexdigest()
    def check(self,entries=None):
        entries=self.base+[(ipa.PLUGIN,self.mod)] if entries is None else entries
        with zipfile.ZipFile(pack(self.base)) as a,zipfile.ZipFile(pack(entries)) as b:
            return ipa.check_archive_pair(a,b,plugin_sha256=self.hash)
    def test_exact_one_new_plugin(self):self.assertEqual(self.check(),3)
    def test_missing_plugin(self):
        with self.assertRaises(ipa.Rejected):self.check(self.base)
    def test_unexpected_extra_file(self):
        with self.assertRaises(ipa.Rejected):
            self.check(self.base+[(ipa.PLUGIN,self.mod),("Payload/GTAV.app/extra.dylib",b"x")])
    def test_modified_GTA5_same_length(self):
        with self.assertRaisesRegex(ipa.Rejected,"original file changed"):
            self.check([("Payload/",""),("Payload/GTAV.app/GTA5",b"INJECT"),
                        ("Payload/GTAV.app/Info.plist",b"PLIST"),(ipa.PLUGIN,self.mod)])
    def test_wrong_plugin_sha(self):
        with self.assertRaisesRegex(ipa.Rejected,"wrong stage plugin"):
            self.check(self.base+[(ipa.PLUGIN,b"other stage")])
    def test_zip_traversal(self):
        with self.assertRaises(ipa.Rejected):
            self.check(self.base+[(ipa.PLUGIN,self.mod),("Payload/../escape",b"evil")])
    def test_duplicate_zip_member(self):
        with self.assertRaises(ipa.Rejected):
            self.check(self.base+[("Payload/GTAV.app/GTA5",b"BINARY"),(ipa.PLUGIN,self.mod)])
    def test_symlink_zip_member(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            info=zipfile.ZipInfo("Payload/GTAV.app/symlink")
            info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(info,b"target")
        out.seek(0)
        with zipfile.ZipFile(out) as z:
            with self.assertRaises(ipa.Rejected):ipa.index_ipa(z)
    def test_original_already_has_plugin(self):
        with zipfile.ZipFile(pack(self.base+[(ipa.PLUGIN,self.mod)])) as z:
            with self.assertRaises(ipa.Rejected):ipa.index_ipa(z)

class AppleProfilePreflight(unittest.TestCase):
    def setUp(self):
        self.team="ABCDE12345"
        app=self.team+".com.macport.gtav"
        self.e={"application-identifier":app,"com.apple.developer.team-identifier":self.team,
                "get-task-allow":True,"keychain-access-groups":[app]}
        self.p={"TeamIdentifier":[self.team],"Entitlements":dict(self.e),
                "ExpirationDate":datetime.now(timezone.utc)+timedelta(days=31),
                "ProvisionedDevices":["test-device"]}
    def check(self):
        return signing.check(self.p,self.e,device_udid="test-device")
    def test_valid_fixture_not_install_claim(self):
        result=self.check()
        self.assertEqual(result["status"],"PROFILE_ENTITLEMENTS_CONSISTENT")
        self.assertFalse(result["signed_application_or_install_verified"])
    def test_wildcard_profile_rejected(self):
        self.p["Entitlements"]["application-identifier"]=self.team+".*"
        with self.assertRaises(signing.ProfileError):self.check()
    def test_expired_profile_rejected(self):
        self.p["ExpirationDate"]=datetime.now(timezone.utc)-timedelta(days=1)
        with self.assertRaises(signing.ProfileError):self.check()
    def test_unregistered_device_rejected(self):
        with self.assertRaises(signing.ProfileError):
            signing.check(self.p,self.e,device_udid="other")
    def test_distribution_profile_rejected(self):
        self.p["Entitlements"]["get-task-allow"]=False
        with self.assertRaises(signing.ProfileError):self.check()
    def test_wrong_bundle_rejected(self):
        self.e["application-identifier"]=self.team+".unrelated"
        with self.assertRaises(signing.ProfileError):self.check()
    def test_extra_entitlement_rejected(self):
        self.e["aps-environment"]="production"
        with self.assertRaises(signing.ProfileError):self.check()
    def test_debug_entitlement_disabled_rejected(self):
        self.e["get-task-allow"]=False
        with self.assertRaises(signing.ProfileError):self.check()
    def test_wrong_team_rejected(self):
        self.p["TeamIdentifier"]=["1234567890"]
        with self.assertRaises(signing.ProfileError):self.check()

if __name__=="__main__":unittest.main()
