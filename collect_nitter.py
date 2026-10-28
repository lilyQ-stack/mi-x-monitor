#!/usr/bin/env python3
"""Collect recent public RSS items; count verified author, never claim completeness."""
import urllib.request, xml.etree.ElementTree as ET, json, re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from pathlib import Path
HOSTS=['nitter.jaydenha.uk','nitter.meowing.monster']
USER='wr0789'
shanghai=ZoneInfo('Asia/Shanghai')
def fetch(host):
 req=urllib.request.Request(f'https://{host}/{USER}/rss',headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=15) as r:return r.read(2000000)
def parse(data,host):
 root=ET.fromstring(data); entries=[]
 for item in root.findall('.//item'):
  title=item.findtext('title') or ''
  link=item.findtext('link') or ''
  desc=item.findtext('description') or ''
  pub=item.findtext('pubDate') or ''
  match=re.search(r'/status/(\d+)',link)
  if not match:continue
  pid=match.group(1)
  try: day=parsedate_to_datetime(pub).astimezone(shanghai).date().isoformat()
  except (ValueError,TypeError):day=None
  # Nitter RSS typically includes the author's profile in link, but verify before attributing.
  author_match=re.search(r'https?://[^/]+/([^/]+)/status/',link)
  author=author_match.group(1) if author_match else None
  entries.append({'id':pid,'url':f'https://x.com/{USER}/status/{pid}', 'date':day,'published':pub,
   'title_excerpt':re.sub('<[^>]+>','',title)[:140],
   'verified_link_author':author.lower()==USER.lower() if author else False,
   'source':host})
 return entries
result={'checked_at':datetime.now(timezone.utc).isoformat(),'account':USER,'status':'error','complete':False,'sources':{},'items':[]}
items={}
for host in HOSTS:
 try:
  entries=parse(fetch(host),host)
  result['sources'][host]={'status':'ok','items':len(entries),'attributed_by_link':sum(e['verified_link_author'] for e in entries)}
  for item in entries:
   if item['verified_link_author']:items[item['id']]=item
 except Exception as exc:
  result['sources'][host]={'status':'error','type':type(exc).__name__,'message':str(exc)[:120]}
result['items']=sorted(items.values(),key=lambda x:x['id'],reverse=True)
result['status']='partial' if items else 'no_verified_items'
result['message']='Recent RSS window only; posts/replies may be missing. No posts must not be interpreted as no activity.'
base=Path('data');base.mkdir(exist_ok=True)
now=datetime.now(shanghai)
for day in [now.date().isoformat(),(now.date()-__import__('datetime').timedelta(days=1)).isoformat()]:
 subset=[e for e in result['items'] if e['date']==day]
 dest=Path(f'data/nitter-{day}.json')
 previous=[]
 if dest.exists():
  try:
   old=json.loads(dest.read_text(encoding='utf-8'))
   previous=old.get('items',[]) if isinstance(old.get('items'),list) else []
  except (json.JSONDecodeError, OSError):pass
 merged={str(x.get('id')):x for x in previous if x.get('id')}
 for item in subset:
  merged[str(item['id'])]=item
 # An empty RSS window must never erase previously seen posts.
 dest.write_text(json.dumps({'date':day,'account':USER,'status':result['status'],
   'complete':False,'items':sorted(merged.values(),key=lambda x:x['id'],reverse=True),
   'sources':result['sources'],'retained_previous':len(previous)},ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')
state=Path('state');state.mkdir(exist_ok=True)
(state/'nitter-latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('NITTER_COLLECT',result['status'],'verified',len(items),'by_day',[(d,sum(x['date']==d for x in items.values())) for d in [now.date().isoformat(),(now.date()-__import__('datetime').timedelta(days=1)).isoformat()]])
