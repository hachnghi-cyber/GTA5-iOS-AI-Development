import hmac
import hashlib
import socket
import struct
import tempfile
import sys
import threading
import unittest
from pathlib import Path

# Same regression file runs standalone from the kit and under GitHub tests/.
_TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if _TOOL_DIR.is_dir():
    sys.path.insert(0, str(_TOOL_DIR))
from unittest.mock import patch
from pc_sender import make_frame, parse_config, validate_response, exchange, verify_pair, get_outbound_ipv4, FRAME, now_ms, KIND_ACK, KIND_NATIVE
from prepare_one_phone_e3 import make_pair, atomic_create_pair


def port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('127.0.0.1', 0)); v = s.getsockname()[1]; s.close()
    return v


class DesktopSenderTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = port(), port()
        while self.a == self.b: self.b = port()
        self.key = bytes(range(32))
        self.sender = bytes(range(1,17))
        self.target = bytes(range(17,33))
        self.session = bytes(range(30,46))
        self.config = {'mode':'sender', 'listen_port':self.a, 'peer_port':self.b,
                       'peer_ipv4':'127.0.0.1', 'self_id_hex':self.sender,
                       'peer_id_hex':self.target, 'session_hex':self.session,
                       'key_hex':self.key}
    def test_hmac_frame_layout(self):
        nonce=b'12345678'
        f=make_frame(1,1,1,1000,self.sender,self.target,self.session,nonce,self.key)
        self.assertEqual(len(f),96)
        self.assertEqual(f[:4],b'RBP1')
        self.assertEqual(f[4:8],b'\x01\x01\x00\x01')
        self.assertEqual(f[8:16],b'\x00'*7+b'\x01')
        self.assertEqual(f[72:80],nonce)
        self.assertEqual(f[80:],hmac.new(self.key,f[:80],hashlib.sha256).digest()[:16])
    def test_refuse_zero_key(self):
        cfg='\n'.join([f'mode=sender',f'listen_port={self.a}',f'peer_port={self.b}',
                        'peer_ipv4=127.0.0.1','self_id_hex='+self.sender.hex(),
                        'peer_id_hex='+self.target.hex(), 'session_hex='+self.session.hex(),
                        'key_hex='+'00'*32])
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'test.cfg';f.write_text(cfg)
            with self.assertRaises(ValueError):parse_config(f)
    def test_ack_and_native_hmac_sequence_validations(self):
        original={'seq':1,'sender':self.sender,'target':self.target,'session':self.session,'nonce':b'12345678'}
        addr=('127.0.0.1',self.b)
        good=make_frame(KIND_ACK,0,1,now_ms(),self.target,self.sender,self.session,b'12345678',self.key)
        self.assertTrue(validate_response(good,addr,addr,original,KIND_ACK,self.key))
        self.assertFalse(validate_response(good,('127.0.0.1',self.a),addr,original,KIND_ACK,self.key))
        self.assertFalse(validate_response(good[:-1]+b'\x00',addr,addr,original,KIND_ACK,self.key))
        self.assertFalse(validate_response(good,addr,addr,original,KIND_NATIVE,self.key))
    def test_end_to_end_fake_peer_receive_once_retransmissions(self):
        seen=[];ready=threading.Event();done=threading.Event()
        def receiver():
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1',self.b));sock.settimeout(2);ready.set()
            try:
                while not done.is_set():
                    p,addr=sock.recvfrom(512)
                    if len(p)!=96:continue
                    seq=struct.unpack('!Q',p[8:16])[0]
                    if seq not in seen:seen.append(seq)
                    nonce=p[72:80]
                    for kind in (KIND_ACK,KIND_NATIVE):
                        out=make_frame(kind,0,seq,now_ms(),self.target,self.sender,self.session,nonce,self.key)
                        sock.sendto(out,addr)
                    break
            finally:sock.close()
        t=threading.Thread(target=receiver,daemon=True);t.start();ready.wait(2)
        try:
            ack,native=exchange(self.config,delay=0,listen_seconds=2,quiet=True)
            self.assertTrue(ack and native)
            self.assertEqual(seen,[1])
        finally:
            done.set();t.join(2)


class OnePhonePreflight(unittest.TestCase):
    def setUp(self):
        self.pc, self.iphone=make_pair('192.168.1.20','192.168.1.30')
    def test_pair_is_symmetric_and_mode_scoped(self):
        with tempfile.TemporaryDirectory() as d:
            pa,pb=atomic_create_pair(d,self.pc,self.iphone)
            a=parse_config(pa);b=parse_config(pb,'receiver')
            self.assertTrue(verify_pair(a,b))
            self.assertEqual(a['listen_port'],b['peer_port'])
            self.assertEqual(a['peer_port'],b['listen_port'])
            self.assertEqual(a['peer_ipv4'],'192.168.1.30')
            self.assertEqual(b['peer_ipv4'],'192.168.1.20')
            self.assertEqual(pa.name,'PC_sender.cfg')
            self.assertEqual(pb.name,'iPhone_RBPProbe.cfg')
    def test_pair_refuses_secret_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            pa,pb=atomic_create_pair(d,self.pc,self.iphone)
            before=(pa.read_bytes(),pb.read_bytes())
            with self.assertRaises(FileExistsError):atomic_create_pair(d,*make_pair('192.168.1.22','192.168.1.33'))
            self.assertEqual(before,(pa.read_bytes(),pb.read_bytes()))
    def test_reject_invalid_endpoint_ips(self):
        for ip in ('127.0.0.1','0.0.0.0','224.0.0.1','169.254.1.2'):
            with self.subTest(ip=ip),self.assertRaises(ValueError):make_pair(ip,'192.168.1.30')
        with self.assertRaises(ValueError):make_pair('192.168.1.30','192.168.1.30')
        with self.assertRaises(ValueError):make_pair('192.168.1.20','192.168.1.30',47880,47880)
    def test_pair_rejects_mismatched_secret_and_port(self):
        with tempfile.TemporaryDirectory() as d:
            pa,pb=atomic_create_pair(d,self.pc,self.iphone)
            a=parse_config(pa);b=parse_config(pb,'receiver')
            for field,value in [('key_hex',bytes(reversed(range(32)))),('session_hex',bytes(range(16))),('peer_port',49999),('self_id_hex',bytes(range(16)))]:
                mutated=dict(b);mutated[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):verify_pair(a,mutated)
    def test_parse_rejects_receiver_as_sender(self):
        with tempfile.TemporaryDirectory() as d:
            pa,pb=atomic_create_pair(d,self.pc,self.iphone)
            with self.assertRaises(ValueError):parse_config(pb)
            with self.assertRaises(ValueError):parse_config(pa,'receiver')
    def test_hmac_sender_rejects_stale_and_wrong_nonce(self):
        sender=bytes(range(1,17));target=bytes(range(17,33));session=bytes(range(30,46))
        original={'seq':1,'sender':sender,'target':target,'session':session,'nonce':b'abcdefgh'}
        peer=('127.0.0.1',47881);key=bytes(range(32))
        valid=make_frame(KIND_NATIVE,0,1,now_ms(),target,sender,session,b'abcdefgh',key)
        self.assertTrue(validate_response(valid,peer,peer,original,KIND_NATIVE,key))
        stale=make_frame(KIND_NATIVE,0,1,now_ms()-15001,target,sender,session,b'abcdefgh',key)
        self.assertFalse(validate_response(stale,peer,peer,original,KIND_NATIVE,key))
        wrong=make_frame(KIND_NATIVE,0,1,now_ms(),target,sender,session,b'abcdEFGH',key)
        self.assertFalse(validate_response(wrong,peer,peer,original,KIND_NATIVE,key))
    def test_no_native_receipt_must_fail_even_with_ack(self):
        sender=bytes(range(1,17));target=bytes(range(17,33));session=bytes(range(30,46))
        ka=bytes(range(32))
        first=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);first.bind(('127.0.0.1',0));port_b=first.getsockname()[1]
        pcport=port();
        while pcport==port_b:pcport=port()
        conf={'mode':'sender','listen_port':pcport,'peer_port':port_b,'peer_ipv4':'127.0.0.1','self_id_hex':sender,'peer_id_hex':target,'session_hex':session,'key_hex':ka}
        def answer():
            first.settimeout(4)
            try:
                packet,source=first.recvfrom(512)
                nonce=packet[72:80]
                rep=make_frame(KIND_ACK,0,1,now_ms(),target,sender,session,nonce,ka)
                first.sendto(rep,source)
            finally:first.close()
        t=threading.Thread(target=answer,daemon=True);t.start()
        ack,native=exchange(conf,delay=0,listen_seconds=1,quiet=True)
        t.join(5)
        self.assertTrue(ack);self.assertFalse(native)
    def test_wait_abort_closes_socket_and_no_send(self):
        from unittest.mock import MagicMock
        fake = MagicMock()
        fake.bind.return_value = None
        fake.settimeout.return_value = None
        conf={'mode':'sender','listen_port':47880,'peer_port':47881,
              'peer_ipv4':'192.168.1.30','self_id_hex':b'1'*16,
              'peer_id_hex':b'2'*16,'session_hex':b'3'*16,'key_hex':b'4'*32}
        with unittest.mock.patch('pc_sender.socket.socket',return_value=fake):
            with unittest.mock.patch('builtins.input',side_effect=EOFError):
                with self.assertRaises(EOFError):
                    exchange(conf,ready=True,quiet=True)
        fake.close.assert_called_once()
        fake.sendto.assert_not_called()

    def test_ip_route_selection_for_local_loopback(self):
        self.assertEqual(get_outbound_ipv4('127.0.0.1'),'127.0.0.1')

    def test_ready_mode_starts_after_user_enter(self):
        # Patch operator input; if packet timestamp were generated before the
        # prompt, the native receiver could reject it as stale after a delay.
        events=[]
        def prompt(_):
            events.append('ready')
            return ''
        import builtins
        with unittest.mock.patch.object(builtins,'input',side_effect=prompt):
            with unittest.mock.patch('pc_sender.make_frame',side_effect=RuntimeError('built_after_ready')):
                # No actual network packet is transmitted by the injected fault.
                conf={'mode':'sender','listen_port':port(),'peer_port':port(),'peer_ipv4':'127.0.0.1','self_id_hex':b'1'*16,'peer_id_hex':b'2'*16,'session_hex':b'3'*16,'key_hex':b'4'*32}
                with self.assertRaisesRegex(RuntimeError,'built_after_ready'):
                    exchange(conf,ready=True,quiet=True)
        self.assertEqual(events,['ready'])

if __name__=='__main__':unittest.main()

