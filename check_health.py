#!/usr/bin/env python3
"""Non-blocking health report. Never equate missing data with no posts."""
import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

root=Path(__file__).resolve().parent
state=root/'state/nitter-latest.json'
report={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'unknown','alerts':[],'verified_items':0,'source_successes':0}
try:
    payload=json.loads(state.read_text(encoding='utf-8'))
    sources=payload.get('sources',{})
    good=[k for k,v in sources.items() if v.get('status')=='ok' and v.get('attributed_by_link',0)>0]
    report['source_successes']=len(good)
    report['verified_items']=len(payload.get('items',[]))
    if not good:
        report['alerts'].append('NO_WORKING_SOURCE: no source returned attributable items')
    elif len(good)<2:
        report['alerts'].append('SINGLE_SOURCE: only one of the feeds returned attributable items')
    when=datetime.fromisoformat(payload['checked_at'].replace('Z','+00:00'))
    age=(datetime.now(timezone.utc)-when.astimezone(timezone.utc)).total_seconds()/3600
    report['age_hours']=round(age,2)
    if age>5:report['alerts'].append('STALE_RUN: collection older than 5 hours')
    if not payload.get('items'):report['alerts'].append('EMPTY_WINDOW: no posts captured; do not conclude no activity')
    if not any('/with_replies' in k and v.get('status')=='ok' for k,v in sources.items()):
        report['alerts'].append('REPLIES_FEED_DOWN: no successful reply feed')
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    file=root/f'data/nitter-{today}.json'
    if file.exists():
        day=json.loads(file.read_text(encoding='utf-8'))
        report['today_saved_count']=len(day.get('items',[]))
    report['status']='warning' if report['alerts'] else 'healthy_snapshot'
except Exception as e:
    report['status']='error'
    report['alerts'].append('HEALTH_CHECK_ERROR: '+type(e).__name__+': '+str(e)[:120])
(root/'state').mkdir(exist_ok=True)
(root/'state/health.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('COLLECT_HEALTH',report['status'],report['alerts'])
