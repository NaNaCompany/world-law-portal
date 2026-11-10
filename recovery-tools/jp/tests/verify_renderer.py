"""Independent AST-to-HTML and omission conservation checks.
Recovery adaptation: corpus paths must be supplied explicitly; no shared-temp defaults.
"""
import sys,json,hashlib,re,html,time,copy,argparse
from pathlib import Path
from html.parser import HTMLParser
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jp_structured_renderer import render,Unsupported,VERSION
ROOT=Path(__file__).resolve().parents[1]
def sha(x):return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def compact(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
class Parsed(HTMLParser):
 def __init__(self,source):
  super().__init__(convert_charrefs=True);self.stack=[];self.nodes=[];self.leaves=[];self.omissions=[];self.source=source;self.annotations=[]
 def handle_starttag(self,tag,at):
  a=dict(at);assert len(a)==len(at);assert tag in {'div','span','ruby','rt','a','strong'}
  assert set(a)<=set('class data-jp-renderer data-jp data-ja data-jl data-jp-annotation role data-jp-omitted-node data-jp-omission data-jp-subtree-sha256 href rel'.split())
  if tag=='a':assert a=={'href':self.source,'rel':'noopener'}
  parent=next((x['node'] for x in reversed(self.stack) if x['node'] is not None),None)
  frame={'tag':tag,'node':None,'leaf':None,'annotation':None}
  if 'data-jp'in a:
   source_tag,num=a['data-jp'].split(':');idx=int(num);frame['node']=idx;self.nodes.append({'index':idx,'parent':parent,'tag':source_tag,'attr':json.loads(a.get('data-ja','{}'))})
  if 'data-jl'in a:
   assert tag=='span';frame['leaf']=len(self.leaves);self.leaves.append({'index':int(a['data-jl']),'parent':parent,'text':''})
  if 'data-jp-omitted-node'in a:self.omissions.append({'sourceNode':int(a['data-jp-omitted-node']),'parent':parent,'tag':a['data-jp-omission'],'subtreeSha256':a['data-jp-subtree-sha256']})
  if 'data-jp-annotation'in a:frame['annotation']=len(self.annotations);self.annotations.append({'sourceNode':int(a['data-jp-annotation']),'text':''})
  self.stack.append(frame)
 def handle_data(self,data):
  for f in self.stack:
   if f['leaf'] is not None:self.leaves[f['leaf']]['text']+=data
   if f['annotation'] is not None:self.annotations[f['annotation']]['text']+=data
 def handle_endtag(self,tag):assert self.stack and self.stack.pop()['tag']==tag
 def handle_entityref(self,name):raise AssertionError('Unparsed entity')

def independently_project(tree):
 leaves=[];nodes=[];omissions=[];ni=0;li=0;retained_anns=[];allleaves=[]
 def visit(n,parent=None,hidden=False):
  nonlocal ni,li
  if isinstance(n,str):
   if not hidden:leaves.append({'index':li,'parent':parent,'text':n})
   allleaves.append(n);li+=1;return
  idx=ni;ni+=1;tag=n['tag'];exclude=tag in ['Table','ArithFormula','Fig'];start=li
  if not hidden and not exclude:nodes.append({'index':idx,'parent':parent,'tag':tag,'attr':n['attr']})
  for child in n['children']:visit(child,idx,hidden or exclude)
  if exclude and not hidden:omissions.append({'sourceNode':idx,'parent':parent,'tag':tag,'subtreeSha256':sha(compact(n)),'firstSourceLeaf':start,'sourceLeafCount':li-start})
 visit(tree);omissions.sort(key=lambda x:x['sourceNode']);return nodes,leaves,omissions,allleaves

def verify(tree,source):
 body,r=render(tree,source);p=Parsed(source);p.feed(body);assert not p.stack
 nodes,leaves,omissions,allleaves=independently_project(tree)
 assert p.nodes==nodes,'Retained node/attribute/parent mismatch';assert p.leaves==leaves,'Exact source leaf value/order/parent mismatch'
 assert p.omissions==[{k:v for k,v in o.items() if k not in ['firstSourceLeaf','sourceLeafCount']} for o in omissions]
 assert r['retainedNodes']==nodes and r['retainedLeaves']==leaves
 assert r['sourceLeafSequenceSha256']==sha(compact(allleaves));assert r['retainedLeafSequenceSha256']==sha(compact([x['text'] for x in leaves]));assert r['textSha256']==sha(''.join(x['text'] for x in leaves))
 covered=set(x['index'] for x in leaves)
 for o,a in zip(omissions,r['omissions']):
  for k in o:assert o[k]==a[k]
  ids=set(range(o['firstSourceLeaf'],o['firstSourceLeaf']+o['sourceLeafCount']));assert not covered&ids;covered|=ids
 assert covered==set(range(len(allleaves))),'Conservation: retained and omitted leaves partition original exactly'
 assert len(p.annotations)==len(r['annotations'])
 for x,y in zip(p.annotations,r['annotations']):assert x['sourceNode']==y['sourceNode'] and x['text']=='Portal annotation · 原文の条文ではありません: '+y['text']
 from lxml import html as lh
 dom=lh.fromstring(body)
 assert len(dom.xpath('//*[@data-jp]'))==len(nodes)
 assert [(int(e.get('data-jl')),''.join(e.itertext())) for e in dom.xpath('//*[@data-jl]')]==[(x['index'],x['text']) for x in leaves]
 assert not dom.xpath('//script|//iframe|//img|//object|//table|//style|//svg|//math')
 assert not dom.xpath('//span//div|//ruby//div|//rt//div'),'Invalid flow element inside phrasing-only source element'
 for e,n in zip(dom.xpath('//*[@data-jp]'),nodes):
  parents=e.xpath('ancestor::*[@data-jp]');assert (int(parents[-1].get('data-jp').split(':')[1]) if parents else None)==n['parent']
 return body,r

def malicious_tests():
 def law(children):return {'tag':'Law','attr':{},'children':children}
 def node(t,cs=[],a={}):return {'tag':t,'attr':a,'children':cs}
 payload='&<script>alert("x")</script>\r\n\t';b,r=verify(law([node('LawTitle',[payload],{'Kana':"\" onerror=\"alert(1) ' & <> \r &#39; &quot;"})]),'https://laws.e-gov.go.jp/law/123');assert '&lt;script&gt;'in b
 tests=[law([node('script',['x'])]),law([node('Paragraph',[],{'onload':'x'})]),law([node('Article',[],{'Hide':'true'})]),law([node('Sentence',['\x00'])]),law([node('TableColumn',[],{'rowspan':'0'})]),law([node('TableColumn',[],{'colspan':'2 onload=x'})]),law([node('Ruby',[node('Sentence',['x'])])])]
 for t in tests:
  try:render(t,'https://laws.e-gov.go.jp/law/123')
  except Unsupported:pass
  else:raise AssertionError('Unsafe tree accepted')
 for u in ['javascript:alert(1)','https://evil.example/law/123','https://laws.e-gov.go.jp@evil.example/law/123','https://laws.e-gov.go.jp/law/123?x=1']:
  try:render(law([]),u)
  except Unsupported:pass
  else:raise AssertionError('Unsafe link accepted')
 return len(tests)+5

def main():
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path);p.add_argument('--omission-map',type=Path);p.add_argument('--output',type=Path,default=ROOT/'artifacts/rendered');p.add_argument('--report',type=Path,default=ROOT/'reports/renderer-verification.json');p.add_argument('--selftest',action='store_true');args=p.parse_args()
 adversarial=malicious_tests()
 if args.selftest:
  print(json.dumps({'passed':True,'syntheticOnly':True,'adversarialTestsPassed':adversarial,'historical190CorpusRerun':False}));return
 assert args.audit and args.omission_map,'Corpus audit and independent omission map must be supplied explicitly'
 inputs=json.loads(args.audit.read_text());external={r['id']:r for r in json.loads(args.omission_map.read_text())['records']};docs=[];blocked=[];start=time.time();out=args.output;out.mkdir(parents=True,exist_ok=True)
 for d in inputs['laws']:
  raw=Path(d['rawSourceFile']).read_bytes();assert sha(raw)==d['sourceSha256'];tree=json.loads(raw)['law_full_text'];source='https://laws.e-gov.go.jp/law/'+d['lawIdentifier']
  body,r=verify(tree,source)
  assert r['textSha256']==external[d['id']]['retainedSourceLeafSha256'],'Independent collector retained text hash mismatch'
  assert [o['path'] for o in r['omissions']]==[o['path'] for o in external[d['id']]['omissions']],'Independent collector omission locations mismatch'
  (out/(d['id']+'.html')).write_text(body);public={k:v for k,v in r.items() if k not in ['retainedLeaves','retainedNodes']};(out/(d['id']+'.json')).write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
  docs.append({'id':d['id'],'sourceSha256':sha(raw),'oldTextSha256':d['textSha256'],'htmlSha256':r['htmlSha256'],'retainedTextSha256':r['textSha256'],'sourceLeaves':r['sourceLeafCount'],'retainedLeaves':r['retainedLeafCount'],'omittedLeaves':r['sourceLeafCount']-r['retainedLeafCount'],'omissions':len(r['omissions']),'annotations':len(r['annotations']),'sourceNodes':r['sourceNodeCount'],'retainedNodes':len(r['retainedNodes']),'passed':True})
 report={'passed':True,'renderer':VERSION,'documents':len(docs),'omissionDocuments':sum(d['omissions']>0 for d in docs),'omissions':sum(d['omissions'] for d in docs),'sourceLeaves':sum(d['sourceLeaves'] for d in docs),'retainedLeaves':sum(d['retainedLeaves'] for d in docs),'omittedLeaves':sum(d['omittedLeaves'] for d in docs),'adversarialTestsPassed':adversarial,'seconds':time.time()-start,'method':'Independent source AST projection compared against strict HTMLParser and lxml DOM. All retained leaf bytes, order, source parentage and attributes exact. Omitted and retained leaf-index sets partition every original leaf without overlap or omission. Whole excluded-subtree hash, source paths and leaf ranges checked. All raw SHA-256 checked. No table/formula/image content rendering.','results':docs,'errors':blocked}
 args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['results','errors']},ensure_ascii=False))
if __name__=='__main__':main()
