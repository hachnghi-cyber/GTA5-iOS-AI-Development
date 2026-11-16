"""Fixture-only Keychain/profile identity binding; no actual Apple certificate."""
import hashlib,sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from resolve_signing_identity import resolve,IdentityError
from check_development_profile import check,ProfileError
SHA1="A"*40
SHA2="B"*40
LABEL1="Apple Development: Test (ABCDE12345)"
LABEL2="Apple Development: Tester (ABCDE12345)"
SECURITY='  1) '+SHA1+' "'+LABEL1+'"\n  2) '+SHA2+' "'+LABEL2+'"\n     2 valid identities found\n'
def fixture():
    team="ABCDE12345";app=team+".com.macport.gtav"
    e={"application-identifier":app,"com.apple.developer.team-identifier":team,"get-task-allow":True}
    der=b"fixture DER bytes, NOT actual X509 certificate"
    p={"TeamIdentifier":[team],"Entitlements":dict(e),
       "DeveloperCertificates":[der],
       "ExpirationDate":datetime.now(timezone.utc)+timedelta(days=5),
       "ProvisionedDevices":["dummy-udid"]}
    return p,e,hashlib.sha1(der).hexdigest()
class IdentitySelection(unittest.TestCase):
    def test_exact_name(self):self.assertEqual(resolve(SECURITY,LABEL1),SHA1)
    def test_exact_fingerprint(self):self.assertEqual(resolve(SECURITY,SHA2),SHA2)
    def test_missing(self):
        with self.assertRaises(IdentityError):resolve(SECURITY,"Apple Development: Unknown")
    def test_duplicate_name(self):
        with self.assertRaises(IdentityError):resolve(SECURITY+'  3) '+("C"*40)+' "'+LABEL1+'"',LABEL1)
    def test_no_partial_labels(self):
        with self.assertRaises(IdentityError):resolve(SECURITY,"Apple Development: Test")
    def test_distribution(self):
        with self.assertRaises(IdentityError):resolve(SECURITY,"Apple Distribution: Test")
    def test_empty_keychain(self):
        with self.assertRaises(IdentityError):resolve("0 valid identities found",SHA1)
    def test_sha1_must_not_select_distribution_identity(self):
        item=SECURITY+'  3) '+("C"*40)+' "Apple Distribution: Test (ABCDE12345)"\n'
        with self.assertRaisesRegex(IdentityError,"NOT an Apple Development"):
            resolve(item,"C"*40)
    def test_invalid_selector(self):
        with self.assertRaises(IdentityError):resolve(SECURITY," "+LABEL1)
class ProfileCertificate(unittest.TestCase):
    def test_allowed_der_sha1(self):
        p,e,sha=fixture()
        x=check(p,e,signing_certificate_sha1=sha,device_udid="dummy-udid")
        self.assertTrue(x["certificate_matches_profile_verified"])
        self.assertFalse(x["signed_application_or_install_verified"])
    def test_wrong_cert(self):
        p,e,_=fixture()
        with self.assertRaisesRegex(ProfileError,"NOT authorized"):check(p,e,signing_certificate_sha1=SHA1)
    def test_no_developer_cert(self):
        p,e,sha=fixture();p.pop("DeveloperCertificates")
        with self.assertRaises(ProfileError):check(p,e,signing_certificate_sha1=sha)
    def test_no_cert_entries(self):
        p,e,sha=fixture();p["DeveloperCertificates"]=[]
        with self.assertRaises(ProfileError):check(p,e,signing_certificate_sha1=sha)
    def test_malformed_der_entry(self):
        p,e,sha=fixture();p["DeveloperCertificates"]=["bad"]
        with self.assertRaises(ProfileError):check(p,e,signing_certificate_sha1=sha)
    def test_invalid_fingerprint(self):
        p,e,_=fixture()
        with self.assertRaises(ProfileError):check(p,e,signing_certificate_sha1="ABC")
    def test_sha_case_insensitive(self):
        p,e,sha=fixture()
        self.assertTrue(check(p,e,signing_certificate_sha1=sha.lower())["certificate_matches_profile_verified"])
    def test_wrong_device_even_with_cert(self):
        p,e,sha=fixture()
        with self.assertRaises(ProfileError):check(p,e,device_udid="other",signing_certificate_sha1=sha)
if __name__=="__main__":unittest.main()
