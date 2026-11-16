from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from evaluate_e0_pair import compare

STAMP=str(int(datetime(2026,11,16,15,50,0,tzinfo=timezone.utc).timestamp()*1000))
PROBE=f'''[RBP_E0] RUN_BEGIN VERSION=1 pid=123 timestamp_ms={STAMP}
[RBP_E0] DLLMAIN_ATTACH
[RBP_E0] SCRIPT_HOOK_UUID_MATCH=1
[RBP_E0] SCRIPT_REGISTER_ATTEMPTED=1 (void API)
[RBP_E0] CALLBACK_ENTER
[RBP_E0] SCRIPT_TICK=1
[RBP_E0] SCRIPT_TICK=30
[RBP_E0] SCRIPT_TICK=120
[RBP_E0] SCRIPT_CALLBACK_COMPLETE=1
'''
POSTHOOK='22:50:01 [shv] loaded plugin RBPProbeE0.shv.dylib (1 scripts)\n'
class PairedDeviceGate(unittest.TestCase):
    def status(self,p=PROBE,s=POSTHOOK,offset=420):
        return compare(p,s,offset)['status']
    def test_full_text_consistency_not_hardware_proof(self):
        r=compare(PROBE,POSTHOOK,420)
        self.assertEqual(r['status'],'STOCK_AND_E0_LOGS_CONSISTENT_NOT_DEVICE_PROOF')
        self.assertFalse(r['device_verified'])
        self.assertTrue(r['stock_registration'])
    def test_no_timezone(self):
        self.assertEqual(self.status(offset=None),'LOG_CONSISTENT_UNCORRELATED_TIME')
    def test_shv_off(self):
        self.assertEqual(self.status(s=POSTHOOK+'Script Hook is OFF (zero cost)'),'SHV_DISABLED')
    def test_dlopen_failure(self):
        self.assertEqual(self.status(s=POSTHOOK+"[shv] couldn't load plugin RBPProbeE0.shv.dylib: bad signature"),'PLUGIN_DLOPEN_FAILURE')
    def test_zero_registered(self):
        self.assertEqual(self.status(s=POSTHOOK.replace('(1 scripts)','(0 scripts)')),'REGISTRATION_DELTA_NOT_ONE')
    def test_duplicate_stock(self):
        self.assertEqual(self.status(s=POSTHOOK+POSTHOOK),'AMBIGUOUS_STOCK_LOAD_ENTRIES')
    def test_other_plugin(self):
        self.assertEqual(self.status(s='22:50:01 [shv] loaded plugin Menyoo.shv.dylib (1 scripts)\n'),'STOCK_LOADER_ENTRY_MISSING')
    def test_probe_missing(self):
        self.assertEqual(self.status(p=''),'STOCK_REGISTERED_BUT_E0_CALLBACK_UNVERIFIED')
    def test_only_attempt(self):
        self.assertEqual(self.status(p=PROBE.split('[RBP_E0] CALLBACK_ENTER')[0]),'STOCK_REGISTERED_BUT_E0_CALLBACK_UNVERIFIED')
    def test_stale_success(self):
        self.assertEqual(self.status(p=PROBE+f'[RBP_E0] RUN_BEGIN VERSION=1 pid=99 timestamp_ms={STAMP}\n'),'STOCK_REGISTERED_BUT_E0_CALLBACK_UNVERIFIED')
    def test_bad_timezone(self):
        self.assertEqual(self.status(offset=0),'TIME_MISMATCH')
    def test_bad_clock(self):
        self.assertEqual(self.status(s=POSTHOOK.replace('22:50:01','22:52:00')),'TIME_MISMATCH')
    def test_missing_time(self):
        self.assertEqual(self.status(s=POSTHOOK.replace('22:50:01 ','')),'STOCK_LOG_TIME_UNAVAILABLE')
    def test_invalid_clock(self):
        self.assertEqual(self.status(s=POSTHOOK.replace('22:50:01','25:50:01')),'INVALID_STOCK_LOG_CLOCK')
    def test_midnight_rollover(self):
        ts=str(int(datetime(2026,11,16,16,59,59,tzinfo=timezone.utc).timestamp()*1000))
        self.assertEqual(self.status(p=PROBE.replace(STAMP,ts),s=POSTHOOK.replace('22:50:01','00:00:00')),'STOCK_AND_E0_LOGS_CONSISTENT_NOT_DEVICE_PROOF')
    def test_wrong_name(self):
        self.assertEqual(self.status(s=POSTHOOK.replace('RBPProbeE0.shv.dylib','RBPProbeE0.shv.dylib.backup')),'STOCK_LOADER_ENTRY_MISSING')
    def test_probe_error(self):
        self.assertEqual(self.status(p=PROBE+'[RBP_E0] SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED\n'),'STOCK_REGISTERED_BUT_E0_CALLBACK_UNVERIFIED')
