"""Offline regression checks for daily merge behavior. No network calls."""
import ast
from pathlib import Path

source=Path('collect_nitter.py').read_text(encoding='utf-8')
tree=ast.parse(source)
func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='merge_record')
scope={}
exec(compile(ast.Module(body=[func],type_ignores=[]),'collect_nitter.py','exec'),scope)
merge=scope['merge_record']

old={'id':'1','excerpt':'A much more detailed excerpt from historical HTML','kind':'unclassified','source':'historical'}
new={'id':'1','title_excerpt':'short','kind':'reply','reply_to_handle':'friend','source':'rss'}
got=merge(old,new)
assert got['excerpt']==old['excerpt'],got
assert got['kind']=='reply',got
assert got['reply_to_handle']=='friend',got
assert got['source']=='historical',got
assert merge(got,{'id':'1','description_excerpt':'hello'})['description_excerpt']=='hello'
assert merge(None,new)==new
print('PASS merge retains rich text, honors reply evidence and adds context')
