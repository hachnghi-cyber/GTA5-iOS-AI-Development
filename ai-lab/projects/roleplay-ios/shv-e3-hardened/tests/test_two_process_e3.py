"""Real UDP across TWO Linux processes, scripted game callback and native MOCK.
Never claims any iPhone, RAGE or remote ped effect.
"""
from pathlib import Path
import ipaddress
import os
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

def wait_for_log(path: Path, marker: str, timeout: float):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if path.exists() and marker in path.read_text(errors='replace'):
            return True
        time.sleep(.025)
    return False

def main():
    # Test harness must already be built by run_phase3_checks.sh.
    plugin=ROOT/'build/RBPProbe-host-e3.so'
    runner=ROOT/'build/test_plugin_peer_host'
    with tempfile.TemporaryDirectory(prefix='rbp-two-process-') as tmp:
        a=Path(tmp)/'A';b=Path(tmp)/'B'
        for p in (a,b): (p/'Documents').mkdir(parents=True)
        pa=free_port();pb=free_port()
        while pa==pb:pb=free_port()
        config=ROOT/'tools/make_two_phone_configs.py'
        created=Path(tmp)/'keys'
        subprocess.run([sys.executable,str(config),'--a-ip','127.0.0.1','--b-ip','127.0.0.1',
                        '--port-a',str(pa),'--port-b',str(pb),'--output-dir',str(created)],
                       check=True,capture_output=True,text=True)
        (a/'Documents/RBPProbe.cfg').write_bytes((created/'iPhone_A_RBPProbe.cfg').read_bytes())
        (b/'Documents/RBPProbe.cfg').write_bytes((created/'iPhone_B_RBPProbe.cfg').read_bytes())
        os.chmod(a/'Documents/RBPProbe.cfg',0o600)
        os.chmod(b/'Documents/RBPProbe.cfg',0o600)
        loga=a/'Documents/RBPProbe.log';logb=b/'Documents/RBPProbe.log'
        envb=dict(os.environ, HOME=str(b)); enva=dict(os.environ,HOME=str(a))
        stderr_a=ROOT/'evidence/two_process_sender_stderr.log'
        stderr_b=ROOT/'evidence/two_process_receiver_stderr.log'
        with stderr_a.open('w') as ea, stderr_b.open('w') as eb:
            recv=subprocess.Popen([str(runner),str(plugin)],env=envb,stdout=subprocess.DEVNULL,stderr=eb)
            try:
                if not wait_for_log(logb,'NETWORK_ACTIVE mode=receiver',3):
                    raise AssertionError('receiver did not start; see stderr logs')
                send=subprocess.Popen([str(runner),str(plugin)],env=enva,
                                      stdout=subprocess.DEVNULL,stderr=ea)
                try:
                    assert send.wait(timeout=12)==0, 'sender process failed'
                    assert recv.wait(timeout=12)==0, 'receiver process failed'
                finally:
                    if send.poll() is None:send.kill();send.wait()
            finally:
                if recv.poll() is None:recv.kill();recv.wait()
        sa=loga.read_text();sb=logb.read_text()
        for tag in ('NETWORK_ACTIVE mode=sender','PACKET_TRANSMITTED seq=1','ACK_VERIFIED seq=1','NATIVE_INVOCATION_REPORT_VERIFIED seq=1'):
            assert tag in sa, ('sender missing:',tag)
        for tag in ('NETWORK_ACTIVE mode=receiver','PACKET_ACCEPTED','REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1','NATIVE_INVOCATION_REPORT_SENT=1 seq=1'):
            assert tag in sb, ('receiver missing:',tag)
        assert sa.count('LOCAL_E1_GAME_ACTION_INVOKED=1')==1
        assert sb.count('LOCAL_E1_GAME_ACTION_INVOKED=1')==1
        assert sb.count('REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1')==1
        print('PASS E3 two independent HOST PROCESSES: UDP -> authenticated RX -> queue -> ScriptHook MOCK -> native MOCK; NOT RAGE/iPhone')

if __name__=='__main__':main()
