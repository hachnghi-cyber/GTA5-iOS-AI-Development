"""Two distinct UDP endpoints on localhost; does not access GTA.
Run `python -m src.loopback_demo` from repo root.
"""
import json
import os
import socket
import threading
import time
from .rbp_wire import Receiver, ack_matches, id16, make_ack, test_frame


def run():
    receiver_id, sender_id, session = (id16(i) for i in ('iphone-B','iphone-A','session-test'))
    key = os.urandom(32)
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(('127.0.0.1', 0))
    sender.bind(('127.0.0.1', 0))
    server.settimeout(2)
    sender.settimeout(2)
    state = Receiver(self_id=receiver_id, allowed_sender=sender_id, session=session, per_peer_key=key)
    history = []
    def rx():
        try:
            data, addr = server.recvfrom(4096)
            result, event = state.accept(data)
            history.append({'side':'B','stage':result,'seq':event.sequence,'bytes':len(data)})
            server.sendto(make_ack(event, receiver_id).encode(key), addr)
            # Re-transmission from A: suppressed duplicate, but ACKed again.
            data2, addr2 = server.recvfrom(4096)
            result2, event2 = state.accept(data2)
            history.append({'side':'B','stage':result2,'seq':event2.sequence})
            server.sendto(make_ack(event2, receiver_id).encode(key), addr2)
        except Exception as e:
            history.append({'side':'B','error':repr(e)})
    worker = threading.Thread(target=rx)
    worker.start()
    try:
        event = test_frame(sender_id, receiver_id, session, 42)
        data = event.encode(key)
        sender.sendto(data, server.getsockname())
        ack, _ = sender.recvfrom(4096)
        history.append({'side':'A','stage':'ACK_VERIFIED' if ack_matches(ack,event,key,receiver_id) else 'ACK_INVALID','seq':42})
        sender.sendto(data, server.getsockname())
        ack2, _ = sender.recvfrom(4096)
        history.append({'side':'A','stage':'DUPLICATE_ACK_VERIFIED' if ack_matches(ack2,event,key,receiver_id) else 'ACK_INVALID','seq':42})
    finally:
        worker.join(timeout=3)
        sender.close()
        server.close()
    print(json.dumps(history, ensure_ascii=False, indent=2))
    assert [x['stage'] for x in history if 'stage' in x and x['side']=='B'] == ['ACCEPTED_DIAGNOSTIC_EVENT_ONLY', 'DUPLICATE']
    assert all(x.get('stage') != 'ACK_INVALID' and 'error' not in x for x in history)
    return history

if __name__ == '__main__':
    run()
