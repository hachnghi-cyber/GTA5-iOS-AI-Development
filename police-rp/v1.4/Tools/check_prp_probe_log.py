#!/usr/bin/env python3
"""Check diagnostic marker exported from iPhone Files. Does not contact networks.

This marker proves library loading/UUID only; it does NOT prove any Police RP gameplay.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

PATTERN = re.compile(
    r'^\[PRP_DIAG_V14\] dylib_loaded=(?P<loaded>[01]) '
    r'gta5_uuid_verified=(?P<uuid>[01]) hooks=(?P<hooks>[01]) '
    r'network_events=(?P<network>[01]) police_gameplay=(?P<gameplay>[01])$',
)


def parse_probe_log(text: str) -> dict:
    markers=[m for line in text.splitlines() if (m:=PATTERN.fullmatch(line.strip()))]
    if not markers:
        return {'status':'MISSING_MARKER', 'verified':False,
                'explanation':'Chưa thấy PRP_DIAG_V14. Không thể khẳng định thư viện đã được nạp.'}
    data={k:int(v) for k,v in markers[-1].groupdict().items()}
    success=(data['loaded']==1 and data['uuid']==1 and
             data['hooks']==0 and data['network']==0 and data['gameplay']==0)
    return {'status':'LOADER_VERIFIED' if success else 'FAILED_CHECK',
            'verified':success,
            'observations':data,
            'explanation':('Đã thấy dylib nạp và đúng UUID. Đây chưa phải Police RP hoạt động.'
                           if success else 'Marker không đạt; không thử Online.')}


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('report',type=Path,help='Tệp PoliceRPProbe-v14.txt lấy từ iPhone')
    args=ap.parse_args()
    if not args.report.is_file():
        ap.exit(2,'Chưa có tệp report; không thể kết luận probe đã nạp.\n')
    result=parse_probe_log(args.report.read_text(encoding='utf-8',errors='replace'))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['verified']:
        ap.exit(1)

if __name__=='__main__':main()
