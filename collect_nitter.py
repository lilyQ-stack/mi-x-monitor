#!/usr/bin/env python3
"""Collect recent public RSS items; count verified author, never claim completeness."""
import urllib.request, xml.etree.ElementTree as ET, json, re, html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from pathlib import Path
HOSTS=['nitter.jaydenha.uk','nitter.meowing.monster']
USER='wr0789'
shanghai=ZoneInfo('Asia/Shanghai')
def fetch(host,with_replies=False):
 route='with_replies/rss' if with_replies else 'rss'
 req=urllib.request.Request(f'https://{host}/{USER}/{route}',headers={'User-Agent':'Mozilla/5.0'})
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
  clean=html.unescape(re.sub(r'<[^>]+>',' ',desc))
  clean=re.sub(r'\s+',' ',clean).strip()
  mentioned=re.search(r'^R to @([A-Za-z0-9_]+)',title.strip(),re.I)
  space=re.search(r'https?://(?:x\.com|twitter\.com)/i/spaces/([A-Za-z0-9]+)',title+' '+desc)
  entries.append({'id':pid,'url':f'https://x.com/{USER}/status/{pid}', 'date':day,'published':pub,
   'title_excerpt':html.unescape(re.sub('<[^>]+>','',title))[:140],
   'description_excerpt':clean[:240], 'reply_to_handle':mentioned.group(1) if mentioned else None,
   'space_url':f'https://x.com/i/spaces/{space.group(1)}' if space else None,
   'kind':'reply' if re.match(r'^R to @',title.strip(),flags=re.I) else 'unclassified',
   'verified_link_author':author.lower()==USER.lower() if author else False,
   'source':host})
 return entries
result={'checked_at':datetime.now(timezone.utc).isoformat(),'account':USER,'status':'error','complete':False,'sources':{},'items':[]}
items={}
for host,with_replies in [(h,replies) for h in HOSTS for replies in (False,True)]:
 key=host+('/with_replies' if with_replies else '/tweets')
 try:
  entries=parse(fetch(host,with_replies),host)
  result['sources'][key]={'status':'ok','items':len(entries),'attributed_by_link':sum(e['verified_link_author'] for e in entries)}
  for item in entries:
   if not item['verified_link_author']:continue
   previous=items.get(item['id'])
   # Prefer an explicit RSS reply marker over unclassified entries from another feed.
   if not previous or (item['kind']=='reply' and previous.get('kind')!='reply'):
    items[item['id']]=item
 except Exception as exc:
  result['sources'][key]={'status':'error','type':type(exc).__name__,'message':str(exc)[:120]}
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
  prev=merged.get(str(item['id']))
  if not prev or (item.get('kind')=='reply' and prev.get('kind')!='reply'):
   merged[str(item['id'])]=item
 # An empty RSS window must never erase previously seen posts.
 dest.write_text(json.dumps({'date':day,'account':USER,'status':result['status'],
   'complete':False,'items':sorted(merged.values(),key=lambda x:x['id'],reverse=True),
   'sources':result['sources'],'retained_previous':len(previous)},ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')
state=Path('state');state.mkdir(exist_ok=True)
(state/'nitter-latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('NITTER_COLLECT',result['status'],'verified',len(items),'by_day',[(d,sum(x['date']==d for x in items.values())) for d in [now.date().isoformat(),(now.date()-__import__('datetime').timedelta(days=1)).isoformat()]])
