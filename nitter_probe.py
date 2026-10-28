#!/usr/bin/env python3
"""No-login Nitter reachability probe. No credentials, no full-text publishing."""
import json, re, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser
TARGETS = ["wr0789", "NASA"]
HOSTS = ["nitter.jaydenha.uk", "nitter.meowing.monster", "nitter.tiekoetter.com"]
class TweetParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.protected=False; self.title=''
        self.in_title=False
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='a' and '/status/' in d.get('href',''):
            self.links.append(d['href'])
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title+=data
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; MI-monitor-diagnostic/0.1)'})
    with urllib.request.urlopen(req,timeout=12) as resp:
        content=resp.read(750000).decode('utf-8','replace')
        return resp.status, content
out={'checked_at':datetime.now(timezone.utc).isoformat(),'method':'public_nitter_probe',
     'target':'wr0789','complete':False,'entries':[]}
for host in HOSTS:
    for user in TARGETS:
        v={'host':host,'account':user}
        for suffix,kind in [('', 'html'),('/rss','rss')]:
            try:
                code,body=get(f'https://{host}/{user}{suffix}')
                v[kind+'_http']=code
                if kind=='html':
                    p=TweetParser();p.feed(body)
                    links=set(re.findall(r'/status/(\d+)',body))
                    v['html_post_ids']=len(links)
                    v['html_title']=p.title[:90]
                    v['html_challenge']=any(x in body.lower() for x in ['just a moment','checking your browser','captcha'])
                else:
                    v['rss_entries']=len(re.findall(r'<item[\s>]',body))
                    v['rss_is_xml']=body.lstrip().startswith(('<?xml','<rss','<feed'))
            except Exception as e:
                v[kind+'_error']=type(e).__name__+': '+str(e)[:90]
        out['entries'].append(v)
Path('state').mkdir(exist_ok=True)
Path('state/nitter-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for v in out['entries']:
    print(v['host'],v['account'], 'HTML',v.get('html_post_ids',0),'RSS',v.get('rss_entries',0),'errors',bool(v.get('html_error') or v.get('rss_error')))
