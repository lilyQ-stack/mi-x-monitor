#!/usr/bin/env python3
"""Offline smoke checks: these do not access X."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta, timezone
import mi_space_collect as m

assert m.SPACE_ID.findall('https://x.com/i/spaces/1XyJEEvejdRndj') == ['1XyJEEvejdRndj']
assert not m.SPACE_ID.findall('https://x.com/something')
now=datetime.now(timezone.utc)
assert m.due_for_retry({'status':'not_attempted','attempts':0},now)
assert not m.due_for_retry({'status':'transcribed','attempts':1},now)
assert not m.due_for_retry({'status':'download_failed','attempts':3},now)
assert not m.due_for_retry({'status':'download_failed','attempts':1,'last_attempt':now.isoformat()},now)
assert m.due_for_retry({'status':'download_failed','attempts':1,'last_attempt':(now-timedelta(hours=30)).isoformat()},now)
with TemporaryDirectory() as d:
    prev=os.getcwd(); os.chdir(d)
    try:
        Path('data').mkdir()
        Path('data/nitter-2026-11-09.json').write_text(json.dumps({'items':[{'verified_link_author':True,'date':'2026-11-09','space_url':'https://x.com/i/spaces/1XyJEEvejdRndj'},{'verified_link_author':False,'date':'2026-11-09','space_url':'https://x.com/i/spaces/1BADSPACE10'}]}))
        result=m.discover()
        assert '1XyJEEvejdRndj' in result
        assert '1BADSPACE10' not in result
        x={'schema_version':1,'spaces':{'example':{'status':'download_failed'}}}
        m.write_index(x)
        assert m.read_json(m.INDEX,{})==x
    finally: os.chdir(prev)
print('ALL_OFFLINE_TESTS_PASSED')
