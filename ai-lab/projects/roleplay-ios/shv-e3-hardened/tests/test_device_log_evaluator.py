"""Regression for actual Phase9 ACK/native-invoked log vocabulary.
All fixtures are synthesized text, NOT proof of iPhone or game execution.
"""
import unittest
from tools.evaluate_device_logs import assess

BASE = '''[RBP_PROBE] RUN_BEGIN phase=4 stage=3 platform=iphoneos-target
[RBP_PROBE] SOURCE_CHECKPOINT=phase12-e3-receipt-retry
[RBP_PROBE] DLLMAIN_ATTACH stage=3
[RBP_PROBE] SCRIPT_HOOK_UUID_MATCH=1
[RBP_PROBE] SCRIPT_REGISTER_ATTEMPTED
[RBP_PROBE] SCRIPT_CALLBACK_ENTER stage=3
[RBP_PROBE] SCRIPT_TICK tick=1
[RBP_PROBE] SCRIPT_TICK tick=900
[RBP_PROBE] SCRIPT_CALLBACK_COMPLETE=1 ticks=901
[RBP_PROBE] LOCAL_E1_GAME_ACTION_INVOKED=1
'''
A = BASE + '''[RBP_NET] PACKET_TRANSMITTED seq=1 attempt=1
[RBP_NET] ACK_VERIFIED seq=1 (queue receipt ONLY)
[RBP_NET] NATIVE_INVOCATION_REPORT_VERIFIED seq=1 (native API invoked, NOT HUD observed)
'''
B = BASE + '''[RBP_NET] PACKET_ACCEPTED seq=1 ack_sent=1
[RBP_PROBE] REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1 tick=18 thread=0xaabb
[RBP_PROBE] NATIVE_INVOCATION_REPORT_QUEUED=1 seq=1 (NOT visual proof)
[RBP_NET] NATIVE_INVOCATION_REPORT_SENT=1 seq=1 (API call only)
'''

class DeviceLogEvaluate(unittest.TestCase):
    def test_stale_phase11_log_without_phase12_marker_rejected(self):
        a=A.replace('[RBP_PROBE] SOURCE_CHECKPOINT=phase12-e3-receipt-retry\n','')
        b=B.replace('[RBP_PROBE] SOURCE_CHECKPOINT=phase12-e3-receipt-retry\n','')
        r=assess(3,b,a,True)
        self.assertFalse(r['all_log_preconditions_met'])
        self.assertFalse(r['observations']['B_E0']['SOURCE_CHECKPOINT=phase12-e3-receipt-retry'])

    def test_one_tick_does_not_prove_e0_completion(self):
        incomplete=B.replace('[RBP_PROBE] SCRIPT_TICK tick=900\n','')
        incomplete=incomplete.replace('[RBP_PROBE] SCRIPT_CALLBACK_COMPLETE=1 ticks=901\n','')
        result=assess(3,incomplete,A,True)
        self.assertFalse(result['all_log_preconditions_met'])
        self.assertFalse(result['observations']['B_E0']['SCRIPT_TICK tick=900'])

    def test_false_callback_complete_does_not_pass(self):
        bad=B.replace('SCRIPT_CALLBACK_COMPLETE=1','SCRIPT_CALLBACK_COMPLETE=0')
        self.assertFalse(assess(3,bad,A,True)['all_log_preconditions_met'])

    def test_failed_then_completed_does_not_pass(self):
        bad=B+'[RBP_PROBE] SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED\n'
        self.assertFalse(assess(3,bad,A,True)['all_log_preconditions_met'])

    def test_host_mock_rejected(self):
        e0=BASE.replace('stage=3','stage=0').replace('platform=iphoneos-target','platform=host-mock')
        self.assertFalse(assess(0,e0)['all_log_preconditions_met'])

    def test_stale_run_rejected(self):
        e0=BASE.replace('stage=3','stage=0')
        self.assertFalse(assess(0,e0+'[RBP_PROBE] RUN_BEGIN phase=4 stage=0 platform=iphoneos-target')['all_log_preconditions_met'])

    def test_ack_without_native_report_is_not_pass(self):
        a=A.split('[RBP_NET] NATIVE_INVOCATION_REPORT_VERIFIED')[0]
        b=B.split('[RBP_PROBE] NATIVE_INVOCATION_REPORT_QUEUED')[0]
        r=assess(3,b,a,True)
        self.assertFalse(r['all_log_preconditions_met'])
        self.assertFalse(r['observations']['A_native_report_verified'])

    def test_full_log_without_visual_is_log_only(self):
        r=assess(3,B,A)
        self.assertTrue(r['all_log_preconditions_met'])
        self.assertTrue(r['observations']['same_sequence_correlated_A_B'])
        self.assertEqual(r['evidence_level'],'DEVICE_LOG_ONLY')
        self.assertFalse(r['rage_multiplayer_replication_verified'])

    def test_full_log_with_manual_visual_is_not_replication(self):
        r=assess(3,B,A,True)
        self.assertTrue(r['all_log_preconditions_met'])
        self.assertEqual(r['evidence_level'],'LOGS_PLUS_MANUAL_VISUAL')
        self.assertFalse(r['rage_multiplayer_replication_verified'])

    def test_lost_native_report_recovered_without_duplicate_gameplay(self):
        b=B.replace('NATIVE_INVOCATION_REPORT_SENT=1',
                    'NATIVE_INVOCATION_REPORT_SENT=0') + (
            '[RBP_NET] PACKET_DUPLICATE seq=1 ack_sent=1\n'
            '[RBP_NET] NATIVE_INVOCATION_REPORT_RETRY_SENT=1 seq=1 (cached API call only)\n')
        a=A.replace('[RBP_NET] NATIVE_INVOCATION_REPORT_VERIFIED',
                    '[RBP_NET] NATIVE_RECEIPT_STATUS_QUERY_SENT=1 seq=1\n'
                    '[RBP_NET] NATIVE_INVOCATION_REPORT_VERIFIED')
        r=assess(3,b,a)
        self.assertTrue(r['all_log_preconditions_met'])
        self.assertTrue(r['observations']['B_native_report_recovered'])
        self.assertFalse(r['rage_multiplayer_replication_verified'])

    def test_second_native_call_for_same_sequence_is_rejected(self):
        r=assess(3,B+'[RBP_PROBE] REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1 tick=19 thread=0xaaaa\n',A,True)
        self.assertFalse(r['all_log_preconditions_met'])
        self.assertFalse(r['observations']['B_native_called_once_per_seq'])

    def test_native_report_not_sent(self):
        bad=B.replace('NATIVE_INVOCATION_REPORT_SENT=1','NATIVE_INVOCATION_REPORT_SENT=0')
        r=assess(3,bad,A,True)
        self.assertFalse(r['all_log_preconditions_met'])
        self.assertFalse(r['observations']['B_native_report_sent'])

    def test_sender_failed_to_verify_native_report(self):
        bad=A.replace('NATIVE_INVOCATION_REPORT_VERIFIED','NATIVE_INVOCATION_REPORT_UNCONFIRMED')
        r=assess(3,B,bad,True)
        self.assertFalse(r['all_log_preconditions_met'])
        self.assertFalse(r['observations']['A_native_report_verified'])

    def test_mismatched_report_sequence_is_rejected(self):
        bad=B.replace('NATIVE_INVOCATION_REPORT_SENT=1 seq=1','NATIVE_INVOCATION_REPORT_SENT=1 seq=2')
        r=assess(3,bad,A,True)
        self.assertFalse(r['observations']['same_sequence_correlated_A_B'])

    def test_mismatched_ack_sequence_is_rejected(self):
        bad=A.replace('ACK_VERIFIED seq=1','ACK_VERIFIED seq=10')
        self.assertFalse(assess(3,B,bad,True)['all_log_preconditions_met'])

    def test_legacy_ack_marker_is_rejected(self):
        bad=A.replace('(queue receipt ONLY)','(not a gameplay ACK)')
        r=assess(3,B,bad,True)
        self.assertFalse(r['observations']['A_queue_ack_verified'])

    def test_exact_sequence_not_substring(self):
        bad=A.replace('PACKET_TRANSMITTED seq=1','PACKET_TRANSMITTED seq=10')
        self.assertFalse(assess(3,B,bad,True)['all_log_preconditions_met'])

    def test_missing_b_receiver_ack(self):
        bad=B.replace('PACKET_ACCEPTED seq=1 ack_sent=1','PACKET_ACCEPTED seq=1 ack_sent=0')
        self.assertFalse(assess(3,bad,A,True)['all_log_preconditions_met'])

    def test_script_fail_closed_after_valid_events(self):
        bad=B + '[RBP_PROBE] SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED\n'
        r=assess(3,bad,A,True)
        self.assertFalse(r['all_log_preconditions_met'])
        self.assertFalse(r['observations']['B_E0']['no_script_fail_closed'])

    def test_stage0_fail_closed_after_tick(self):
        e0=BASE.replace('stage=3','stage=0')
        self.assertFalse(assess(0,e0+'[RBP_PROBE] SCHEDULER_CLOCK_OR_WAIT_INVALID FAIL_CLOSED\n')['all_log_preconditions_met'])

    def test_source_cross_run_not_correlated(self):
        bad=A+'[RBP_PROBE] RUN_BEGIN phase=4 stage=3 platform=iphoneos-target\n'
        self.assertFalse(assess(3,B,bad,True)['all_log_preconditions_met'])

if __name__=='__main__':unittest.main()
