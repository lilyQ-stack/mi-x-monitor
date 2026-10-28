#!/usr/bin/env python3
"""Check Nitter replies RSS and profile pagination without authentication."""
import json,re,urllib.request,xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin
HOSTS=['nitter.jaydenha.uk','nitter.meowing.monster']
PATHS=['/wr0789/with_replies/rss','/wr0789/with_replies','/wr0789']
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.text=''
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'):self.links.append((a['href'],a.get('class','')))
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=14) as r:return r.read(900000).decode('utf-8','replace')
out={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'diagnostic','complete':False,'results':[]}
for host in HOSTS:
 for path in PATHS:
  url=f'https://{host}{path}';v={'url':url}
  try:
   body=get(url)
   if path.endswith('/rss'):
    root=ET.fromstring(body)
    items=root.findall('.//item');v['rss_items']=len(items)
    v['sample_guids']=[(i.findtext('guid') or '')[-40:] for i in items[:4]]
    v['sample_titles']=[(i.findtext('title') or '')[:75] for i in items[:4]]
   else:
    p=Page();p.feed(body)
    v['post_ids']=len(set(re.findall(r'/status/(\\d+)',body)))
    v['pagination_links']=[urljoin(url,h) for h,c in p.links if 'cursor=' in h or 'show-more' in c][:3]
    v['html_replies_markers']=len(re.findall(r'replying to|Replying to|reply-to',body))
  except Exception as e:v['error']=type(e).__name__+': '+str(e)[:130]
  out['results'].append(v)
Path('state').mkdir(exist_ok=True)
Path('state/replies-pagination-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\\n')
print(json.dumps([{k:v for k,v in r.items() if k not in ('sample_titles','sample_guids')} for r in out['results']],ensure_ascii=False))
