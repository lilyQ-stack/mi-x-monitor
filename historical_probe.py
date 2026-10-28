#!/usr/bin/env python3
"""Bounded historical Nitter pagination: save only dated, attributable post metadata."""
import json, re, urllib.request, time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone
class Links(HTMLParser):
 def __init__(self): super().__init__(); self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'): self.links.append((a['href'],a.get('class','')))
base='https://nitter.jaydenha.uk/wr0789/with_replies'
url=base
seen=set()
report={'checked_at':datetime.now(timezone.utc).isoformat(),'target':'wr0789','pages':[],'complete':False,'status':'partial'}
for n in range(6):
 if url in seen: break
 seen.add(url)
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=12) as response:
   html=response.read(1500000).decode('utf-8','replace')
  p=Links(); p.feed(html)
  ids=list(dict.fromkeys(re.findall(r'/wr0789/status/(\d+)',html,re.I)))
  cursors=[urljoin(url,link) for link,cls in p.links if 'cursor=' in link]
  report['pages'].append({'page':n+1,'count':len(ids),'ids':ids,'has_next':bool(cursors)})
  if not cursors:break
  url=cursors[-1]
  time.sleep(1)
 except Exception as exc:
  report['pages'].append({'page':n+1,'error':type(exc).__name__+': '+str(exc)[:150]})
  break
Path('state').mkdir(exist_ok=True)
Path('state/historical-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('HISTORY',[(p['page'],p.get('count'),p.get('error')) for p in report['pages']])
