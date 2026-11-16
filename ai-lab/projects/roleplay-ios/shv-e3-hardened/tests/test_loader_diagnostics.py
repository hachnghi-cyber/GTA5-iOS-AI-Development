import unittest
from tools.evaluate_loader_logs import analyze_loader

class LoaderDiagnostics(unittest.TestCase):
    def setUp(self):
        self.run='[RBP_PROBE] RUN_BEGIN phase=4 stage=0 platform=iphoneos-target\n'
        self.base=self.run+'[RBP_PROBE] DLLMAIN_ATTACH stage=0\n'

    def test_disabled_takes_priority(self):
        r=analyze_loader('[shv] off by setting: no plugins, no tick',self.base)
        self.assertEqual(r['classification'],'SHV_DISABLED_BY_SETTING')

    def test_dlopen_failure(self):
        p='[shv] couldn\'t load plugin RBPProbe.shv.dylib: code signature invalid'
        self.assertEqual(analyze_loader(p,'')['classification'],'DYLD_OR_LOADER_PLUGIN_LOAD_FAILED')

    def test_loaded_but_no_dllmain(self):
        p='[shv] loaded plugin RBPProbe.shv.dylib (0 scripts)'
        self.assertEqual(analyze_loader(p,'')['classification'],'PLUGIN_LOADED_BUT_DLLMAIN_NOT_OBSERVED')

    def test_register_without_callback_is_not_E0(self):
        p='[shv] loaded plugin RBPProbe.shv.dylib (1 scripts)'
        log=self.base+'SCRIPT_HOOK_UUID_MATCH=1\nSCRIPT_REGISTER_ATTEMPTED\n'
        self.assertEqual(analyze_loader(p,log)['classification'],'SCRIPT_REGISTRATION_ATTEMPTED_NO_CALLBACK')

    def test_callback_and_tick(self):
        p='[shv] loaded plugin RBPProbe.shv.dylib (1 scripts)'
        log=self.base+'SCRIPT_HOOK_UUID_MATCH=1\nSCRIPT_REGISTER_ATTEMPTED\nSCRIPT_CALLBACK_ENTER stage=0\nSCRIPT_TICK tick=1\n'
        r=analyze_loader(p,log)
        self.assertEqual(r['classification'],'E0_LOG_PREREQUISITES_OBSERVED')
        self.assertTrue(r['not_proof_of_iphone_or_gameplay'])

    def test_latest_phase4_run_only(self):
        p='[shv] loaded plugin RBPProbe.shv.dylib (1 scripts)'
        old=self.base+'SCRIPT_HOOK_UUID_MATCH=1\nSCRIPT_REGISTER_ATTEMPTED\nSCRIPT_CALLBACK_ENTER stage=0\nSCRIPT_TICK tick=1\n'
        new=self.run
        self.assertNotEqual(analyze_loader(p,old+new)['classification'],'E0_LOG_PREREQUISITES_OBSERVED')

    def test_old_disabled_not_override_later_loaded_plugin(self):
        p='[shv] off by setting: no plugins, no tick\n[shv] loaded plugin RBPProbe.shv.dylib (1 scripts)\n'
        r=analyze_loader(p,self.base+'SCRIPT_HOOK_UUID_MATCH=1\nSCRIPT_REGISTER_ATTEMPTED\nSCRIPT_CALLBACK_ENTER stage=0\nSCRIPT_TICK tick=1\n')
        self.assertEqual(r['classification'],'E0_LOG_PREREQUISITES_OBSERVED')

    def test_old_load_error_not_override_new_success(self):
        p="[shv] couldn't load plugin RBPProbe.shv.dylib: old\n[shv] loaded plugin RBPProbe.shv.dylib (1 scripts)\n"
        self.assertFalse(analyze_loader(p,self.run)['checks']['plugin_load_failed_log'])
