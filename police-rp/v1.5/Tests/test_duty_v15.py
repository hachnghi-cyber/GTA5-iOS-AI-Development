import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Tools'))
from check_duty_v15 import analyse
HEAD='[PRP_DIAG_V15] dylib_loaded=1 gta5_uuid_verified=1 hooks=0 network_events=0 police_gameplay=0 timer=main_queue_1s\n'
def line(tick,job,shift,active,label):
    return f'[PRP_DUTY_V15] tick={tick} job={job} shift={shift} police_active={active} label={label}\n'
class TestProbe(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(analyse('')['status'],'LOAD_NOT_VERIFIED')
    def test_header_only(self):
        self.assertEqual(analyse(HEAD)['status'],'TIMER_NO_SAMPLES')
    def test_single_idle(self):
        self.assertEqual(analyse(HEAD+line(1,-1,0,0,'none'))['status'],'SAMPLES_OK_NO_TRANSITION')
    def test_duty_transition(self):
        blob=HEAD+line(1,-1,0,0,'none')+line(15,0,1,1,'cop_ls')+line(25,0,0,0,'cop_ls')
        data=analyse(blob)
        self.assertEqual(data['status'],'DUTY_TRANSITION_OBSERVED')
        self.assertEqual(data['samples'],3)
    def test_bad_active(self):
        self.assertEqual(analyse(HEAD+line(1,2,0,1,'cop_paleto'))['status'],'BAD_SAMPLE')
    def test_bad_name(self):
        self.assertEqual(analyse(HEAD+line(1,2,1,1,'cop_ls'))['status'],'BAD_SAMPLE')
    def test_uuid_fail(self):
        self.assertEqual(analyse(HEAD.replace('uuid_verified=1','uuid_verified=0')+line(1,-1,0,0,'none'))['status'],'LOAD_NOT_VERIFIED')
if __name__=='__main__':unittest.main()
