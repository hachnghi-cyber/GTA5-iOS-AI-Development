import unittest
from tools.evaluate_device_logs import assess
class DeviceLogEvaluate(unittest.TestCase):
    def setUp(self):
        self.base='''[RBP_PROBE] RUN_BEGIN phase=4 stage=3 platform=iphoneos-target
[RBP_PROBE] DLLMAIN_ATTACH stage=3
[RBP_PROBE] SCRIPT_HOOK_UUID_MATCH=1
[RBP_PROBE] SCRIPT_REGISTER_ATTEMPTED
[RBP_PROBE] SCRIPT_CALLBACK_ENTER stage=3
[RBP_PROBE] SCRIPT_TICK tick=1
[RBP_PROBE] LOCAL_E1_GAME_ACTION_INVOKED=1
'''
    def test_host_mock_rejected(self):
        x=assess(0,self.base.replace('stage=3','stage=0').replace('platform=iphoneos-target','platform=host-mock'))
        self.assertFalse(x['all_log_preconditions_met'])
    def test_stale_run_rejected(self):
        good=self.base.replace('stage=3','stage=0')
        self.assertFalse(assess(0,good+'[RBP_PROBE] RUN_BEGIN phase=4 stage=0 platform=iphoneos-target')['all_log_preconditions_met'])
    def test_ack_without_game_action_not_pass(self):
        a=self.base+'[RBP_NET] PACKET_TRANSMITTED seq=1 attempt=1\n[RBP_NET] ACK_VERIFIED seq=1 (not a gameplay ACK)\n'
        b=self.base+'[RBP_NET] PACKET_ACCEPTED seq=1 ack_sent=1\n'
        x=assess(3,b,a,True)
        self.assertFalse(x['all_log_preconditions_met'])
    def test_all_log_without_video_not_full_e3(self):
        a=self.base+'[RBP_NET] PACKET_TRANSMITTED seq=1 attempt=1\n[RBP_NET] ACK_VERIFIED seq=1 (not a gameplay ACK)\n'
        b=self.base+'[RBP_NET] PACKET_ACCEPTED seq=1 ack_sent=1\n[RBP_PROBE] REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1 tick=18 thread=0xaabb\n'
        x=assess(3,b,a)
        self.assertTrue(x['all_log_preconditions_met'])
        self.assertEqual(x['evidence_level'],'DEVICE_LOG_ONLY')

    def test_mismatched_sequences_not_accepted(self):
        a=self.base+'[RBP_NET] PACKET_TRANSMITTED seq=1 attempt=1\n[RBP_NET] ACK_VERIFIED seq=1 (not a gameplay ACK)\n'
        b=self.base+'[RBP_NET] PACKET_ACCEPTED seq=2 ack_sent=1\n[RBP_PROBE] REMOTE_E3_GAME_ACTION_INVOKED=1 seq=2 tick=18 thread=0xaabb\n'
        x=assess(3,b,a,True)
        self.assertFalse(x['all_log_preconditions_met'])
        self.assertFalse(x['observations']['same_sequence_correlated_A_B'])

    def test_exact_sequence_not_substring(self):
        a=self.base+'[RBP_NET] PACKET_TRANSMITTED seq=10 attempt=1\n[RBP_NET] ACK_VERIFIED seq=10 (not a gameplay ACK)\n'
        b=self.base+'[RBP_NET] PACKET_ACCEPTED seq=1 ack_sent=1\n[RBP_PROBE] REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1 tick=18 thread=0xaabb\n'
        self.assertFalse(assess(3,b,a,True)['all_log_preconditions_met'])
