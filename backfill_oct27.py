#!/usr/bin/env python3
"""Bounded backfill of public Nitter timeline; metadata only, no private credentials."""
import json, re, time, urllib.request
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
TARGET_DATE='2026-10-27'
ROOT='https://nitter.jaydenha.uk/wr0789/with_replies'
TZ=ZoneInfo('Asia/Shanghai')
EPOCH=1288834974657
def day_from_id(id):
 try:return datetime.fromtimestamp(((int(id)>>22)+EPOCH)/1000,timezone.utc).astimezone(TZ).date().isoformat()
 except (ValueError,OverflowError,OSError):return None
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=15) as r:return r.read(1600000).decode('utf-8','replace')
url=ROOT; visited=set(); found={}; pages=[];errors=[]
for page_num in range(1,16):
 if url in visited:break
 visited.add(url)
 try:
  soup=BeautifulSoup(fetch(url),'html.parser')
  candidates=soup.select('.timeline-item')
  ids_on_page=[]
  for node in candidates:
   header=node.select_one('.tweet-header')
   if not header: continue
   owner=header.select_one('.username')
   if not owner or owner.get_text(' ',strip=True).lower().lstrip('@')!='wr0789':continue
   link=node.select_one('.tweet-date a[href*="/status/"]') or node.select_one('a.tweet-link[href*="/status/"]')
   if not link:continue
   hit=re.search(r'/status/(\d+)',link.get('href',''))
   if not hit:continue
   pid=hit.group(1); day=day_from_id(pid);ids_on_page.append(pid)
   if day!=TARGET_DATE:continue
   content=node.select_one('.tweet-content')
   text=content.get_text(' ',strip=True) if content else ''
   reply_node=node.select_one('.replying-to')
   # Do not interpret an unmarked item as an original tweet.
   # Nitter may omit the reply marker for some timeline entries.
   is_reply=bool(reply_node)
   has_quote=bool(node.select_one('.quote'))
   kind='reply' if is_reply else ('quote_or_unclassified' if has_quote else 'unclassified')
   found[pid]={'id':pid,'url':'https://x.com/wr0789/status/'+pid,'date':day,
       'kind':kind,
       'excerpt':text[:140], 'source':'nitter historical HTML',
       'attribution':'matched tweet header @wr0789', 'reply_marker':is_reply}
  nexts=[urljoin(url,a.get('href')) for a in soup.select('a[href*="cursor="]') if a.get('href')]
  pages.append({'page':page_num,'timeline_items':len(candidates),'author_ids':len(ids_on_page),
   'target_date_items':sum(day_from_id(i)==TARGET_DATE for i in ids_on_page),'next':bool(nexts)})
  if not nexts:break
  url=nexts[-1]
  time.sleep(0.8)
 except Exception as e:
  errors.append({'page':page_num,'error':type(e).__name__,'detail':str(e)[:130]});break
p=Path('data')/f'nitter-{TARGET_DATE}.json'
p.parent.mkdir(exist_ok=True)
previous=[]
if p.exists():
 try:previous=json.loads(p.read_text(encoding='utf-8')).get('items',[])
 except Exception:pass
items={str(x['id']):x for x in previous if x.get('id')}
items.update(found)
kind_counts={}
for item in items.values():
 kind_counts[item['kind']]=kind_counts.get(item['kind'],0)+1
record={'date':TARGET_DATE,'account':'wr0789','status':'partial','complete':False,
        'items':sorted(items.values(),key=lambda x:x['id'],reverse=True),
        'notes':'Bounded 15-page backfill. Unclassified is NOT an original post. Dates decoded from X snowflake IDs.',
        'pages_checked':len(pages),'errors':errors,'kind_counts':kind_counts}
p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=Path('state');state.mkdir(exist_ok=True)
(state/'backfill-report.json').write_text(json.dumps({'date':TARGET_DATE,'pages':pages,'new_found':len(found),'merged_count':len(items),'kind_counts':kind_counts,'earliest_id':min(items) if items else None,'latest_id':max(items) if items else None,'errors':errors,'complete':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('BACKFILL',TARGET_DATE,'pages',len(pages),'found',len(found),'merged',len(items),'errors',len(errors))
