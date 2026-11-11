"""Independently compare pinned e-Gov JSON, original text receipts and structured HTML.
All inputs and the output report are explicit CLI paths. No network or publication.
Requires Python 3, html5lib and lxml.
"""
import argparse,collections,hashlib,html,importlib.util,json,re,subprocess,sys,time
from pathlib import Path
from html.parser import HTMLParser
from lxml import html as LH
import html5lib
R=None

def sha(x):return hashlib.sha256(x if isinstance(x,bytes) else x.encode('utf-8')).hexdigest()
def js(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def ck(ok,msg):
 if not ok:raise AssertionError(msg)
def project(tree):
 nodes=[];leaves=[];keptnodes=[];keptleaves=[];omissions=[];annotations=[]
 def visit(v,parent=None,path='/law_full_text',hidden=False):
  if isinstance(v,str):
   row=(len(leaves),parent,v);leaves.append(row)
   if not hidden:keptleaves.append(row)
   return
  ix=len(nodes);tag=v['tag'];attrs=v['attr'];row=(ix,parent,tag,list(attrs.items()));nodes.append(row);start=len(leaves);omit=tag in ('Table','Fig','ArithFormula')
  if not hidden and not omit:
   keptnodes.append(row);keys={'SupplProvision':['AmendLawNum','Extract','Type'],'MainProvision':['Extract']}.get(tag,[])
   if tag=='Paragraph' and attrs.get('OldNum')=='true':keys=['OldNum','Num']
   if any(k in attrs for k in keys):
    text='Portal annotation · 原文の条文ではありません: 原データ属性 '+tag+': '+'; '.join(k+'='+json.dumps(attrs[k],ensure_ascii=False) for k in keys if k in attrs)
    if tag=='Paragraph':
     def tx(n):return n if isinstance(n,str) else ''.join(tx(c) for c in n['children'])
     number=next(c for c in v['children'] if isinstance(c,dict) and c['tag']=='ParagraphNum');text+='; ParagraphNum='+json.dumps(tx(number),ensure_ascii=False)
    annotations.append((ix,text))
  for i,c in enumerate(v['children']):visit(c,ix,path+'/children/'+str(i),hidden or omit)
  if omit and not hidden:
   ns=nodes[ix:];ls=leaves[start:]
   omissions.append(dict(sourceNode=ix,parent=parent,tag=tag,path=path,attributes=attrs,subtreeSha256=sha(js(v)),sourceNodeCount=len(ns),firstSourceLeaf=start,sourceLeafCount=len(ls),sourceLeafSequenceSha256=sha(js([l[2] for l in ls])),nestedNodeCounts=dict(collections.Counter(n[2] for n in ns)),titles=[]))
 visit(tree);omissions.sort(key=lambda o:o['sourceNode']);return dict(nodes=nodes,leaves=leaves,keptnodes=keptnodes,keptleaves=keptleaves,omissions=omissions,annotations=annotations)
ALLOWED=set('class data-jp-renderer data-jp data-ja data-jl data-jp-annotation role data-jp-omitted-node data-jp-omission data-jp-subtree-sha256 href rel'.split())
class Strict(HTMLParser):
 def __init__(self):super().__init__();self.stack=[]
 def handle_starttag(self,t,aa):
  a=dict(aa);ck(t in ('div','span','ruby','rt','a','strong'),'Unexpected source HTML tag');ck(len(a)==len(aa) and set(a)<=ALLOWED,'Unexpected/duplicate source HTML attribute');ck(t!='div' or not any(x in ('span','ruby','rt') for x in self.stack),'Flow child in phrasing element');self.stack.append(t)
 def handle_endtag(self,t):ck(self.stack and self.stack.pop()==t,'Unbalanced source markup')
 def handle_comment(self,x):raise AssertionError('Source HTML comment')
 def handle_decl(self,x):raise AssertionError('Source HTML declaration')
def signature(root,url):
 nodes=[];leaves=[];omissions=[];annotations=[]
 def walk(e,parent=None):
  a=e.attrib;t=e.tag.split('}')[-1]
  if t!='DOCUMENT_FRAGMENT':ck(t in ('div','span','ruby','rt','a','strong') and set(a)<=ALLOWED,'Active/unsupported DOM element/attribute')
  if t=='a':ck(a=={'href':url,'rel':'noopener'},'Unexpected omission URL')
  if 'data-jp' in a:
   st,si=a['data-jp'].split(':');ix=int(si);ck(t=={'Ruby':'ruby','Rt':'rt'}.get(st,'div'),'Wrong native source element');nodes.append((ix,parent,st,list(json.loads(a.get('data-ja','{}')).items())));parent=ix
  if 'data-jl' in a:ck(t=='span','Non-span source leaf');leaves.append((int(a['data-jl']),parent,''.join(e.itertext())))
  if 'data-jp-omitted-node' in a:
   ck(a.get('class')=='jp-omission' and a.get('role')=='note','Unlabelled omission');omissions.append((int(a['data-jp-omitted-node']),parent,a['data-jp-omission'],a['data-jp-subtree-sha256'],''.join(e.itertext())))
  if 'data-jp-annotation' in a:
   ck(a.get('class')=='jp-source-annotation' and a.get('role')=='note','Unlabelled source attribute annotation');annotations.append((int(a['data-jp-annotation']),''.join(e.itertext())))
  for c in e:walk(c,parent)
 walk(root);return nodes,leaves,omissions,annotations

def verify(tree,url):
 p=project(tree);body,receipt=R.render(tree,url);parser=Strict();parser.feed(body);parser.close();ck(not parser.stack,'Unclosed markup');lxml=signature(LH.fromstring(body),url)
 hp=html5lib.HTMLParser(namespaceHTMLElements=False);dom=hp.parseFragment(body)
 bad=[e for e in hp.errors if not(e[1]=='illegal-codepoint-for-numeric-entity' and e[2]=={'charAsInt':13})];ck(not bad,'HTML5 parser errors '+repr(bad[:3]));h5=signature(dom,url);ck(h5==lxml,'HTML5/lxml trees differ')
 ns,ls,os,anns=h5;ck(ns==p['keptnodes'],'Source node/attribute order/value/parent mismatch');ck(ls==p['keptleaves'],'Leaf codepoint/value/order/parent mismatch');ck(anns==p['annotations'],'Source attribute annotation mismatch')
 ck([o[:4] for o in os]==[(o['sourceNode'],o['parent'],o['tag'],o['subtreeSha256']) for o in p['omissions']],'Omission location/hash mismatch')
 for actual,o in zip(os,p['omissions']):ck('Portal omission · 原文の条文ではありません:' in actual[4] and 'これは部分再現です。' in actual[4] and o['path'] in actual[4],'Omission context/partial/nonstatutory label missing')
 ck(receipt['omissions']==p['omissions'],'Full omission receipt mismatch')
 for actual,o in zip(receipt['omissions'],p['omissions']):ck(list(actual['attributes'].items())==list(o['attributes'].items()),'Omitted source attr order changed')
 expected={'sourceNodeCount':len(p['nodes']),'sourceLeafCount':len(p['leaves']),'retainedLeafCount':len(p['keptleaves']),'htmlSha256':sha(body),'textSha256':sha(''.join(l[2] for l in p['keptleaves'])),'sourceTreeSha256':sha(js(tree)),'sourceLeafSequenceSha256':sha(js([l[2] for l in p['leaves']])),'retainedLeafSequenceSha256':sha(js([l[2] for l in p['keptleaves']]))}
 for k,v in expected.items():ck(receipt[k]==v,'Renderer receipt mismatch '+k)
 nl={l[0] for l in p['keptleaves']};nn={n[0] for n in p['keptnodes']}
 for o in p['omissions']:
  ol=set(range(o['firstSourceLeaf'],o['firstSourceLeaf']+o['sourceLeafCount']));on=set(range(o['sourceNode'],o['sourceNode']+o['sourceNodeCount']));ck(not nl&ol and not nn&on,'Overlapping source coverage');nl|=ol;nn|=on
 ck(nl==set(range(len(p['leaves']))) and nn==set(range(len(p['nodes']))),'Unexplained source loss');return body,p,expected

def synthetic():
 def n(t,c=None,a=None):return dict(tag=t,children=c or [],attr=a or {})
 url='https://laws.e-gov.go.jp/law/123';text='a\r\nb\tc & <script>"\' &amp; &#13; 日本 e\u0301 \U00020bb7'
 tree=n('Law',[n('LawTitle',[text],{'Abbrev':text,'Kana':text}),n('MainProvision',[n('Paragraph',[n('ParagraphNum'),n('ParagraphSentence',[n('Sentence',['before',n('Column',[n('QuoteStruct',[n('Sentence',['nested'])])]),'after'])])],{'Num':'1','OldNum':'true'})],{'Extract':'true'}),n('SupplProvision',[n('SupplProvisionLabel',['附則'])],{'Type':'Amend','Extract':'true','AmendLawNum':text}),n('TableStruct',[n('TableStructTitle',['kept title']),n('Table',[n('TableRow',[n('TableColumn',['OMITTED',n('ArithFormula',['FORMULA'])])])]),n('Remarks',[n('RemarksLabel',['kept remark']),n('Sentence',['kept content'])])]),n('ArithFormula',['omitted standalone']),n('Fig',[],{'src':text}),n('Ruby',['base',n('Rt',['reading'])]),n('Ruby',['emphasis',n('Rt',['﹅'])])])
 b,p,_=verify(tree,url);ck(len(p['omissions'])==3 and 'OMITTED' not in b and 'FORMULA' not in b,'Nested omission leak')
 bad=[n('Law',[n('script')]),n('Law',[n('Sentence',['\0'])]),n('Law',[n('Article',[],{'Hide':'true'})]),n('Law',[n('Paragraph',[],{'onclick':'x'})]),n('Law',[n('Ruby',[n('Sentence',['x'])])]),n('Law',[n('Rt',[n('Sentence',['x'])])]),n('Law',[n('TableColumn',[],{'rowspan':'1001'})]),n('Law',[n('MainProvision',[],{'Extract':'TRUE'})]),n('Law',[n('TableColumn',['stray'])]),n('Law',[n('TableRow')]),n('Law',[n('Fig',[],{'src':'\0'})])]
 for t in bad:
  try:R.render(t,url)
  except (ValueError,TypeError):pass
  else:raise AssertionError('Invalid synthetic source accepted')
 urls=['javascript:alert(1)','https://evil.example/law/1','https://laws.e-gov.go.jp@evil.example/law/1','https://laws.e-gov.go.jp/law/1?x=1','https://laws.e-gov.go.jp/law/1#x','http://laws.e-gov.go.jp/law/1']
 for u in urls:
  try:R.render(n('Law'),u)
  except (ValueError,TypeError):pass
  else:raise AssertionError('Unsafe source URL accepted')
 for t in [n('Law',[n('LawTitle',['text'],{'Kana':'a\0b'})]),n('Law',[n('SupplProvision',[n('SupplProvisionLabel',['附則'])],{'AmendLawNum':'a\0b'})])]:
  safe,_,_=verify(t,url);ck('\0' not in safe,'Raw NUL emitted instead of JSON escape')
 return dict(passed=True,compositeFixture=True,safeJsonAttributeNulRoundtrips=2,negativeTests=len(bad)+len(urls),html5LxmlEqual=True)

def main():
 global R
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--renderer',type=Path,required=True);ap.add_argument('--pages',type=Path);ap.add_argument('--catalog',type=Path);ap.add_argument('--golden',type=Path);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--source-commit',required=True);ap.add_argument('--catalogue-sha256',required=True);a=ap.parse_args();start=time.time()
 spec=importlib.util.spec_from_file_location('reviewed_renderer',a.renderer);R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
 git=lambda *x:subprocess.check_output(['git','-C',str(a.source),*x]);pin=a.source_commit;ck(git('rev-parse','HEAD').decode().strip()==pin and not git('status','--porcelain').strip(),'Source checkout must be clean at the specified commit');cb=git('show',pin+':additions-catalog.json');ck(cb==(a.source/'additions-catalog.json').read_bytes(),'Catalogue differs from pinned remote');ck(sha(cb)==a.catalogue_sha256,'Catalogue historic byte pin mismatch');docs=[d for d in json.loads(cb)['documents'] if d['country']=='JP'];ck(len(docs)==len({d['id'] for d in docs})==190,'Wrong original190 IDs')
 rows=[];tot=collections.Counter();tags=collections.Counter();kepttags=collections.Counter();under=0;tableids=set();suppdocs=0;excerptdocs=0
 report=dict(passed=False,verificationMethod='Independent source AST projection, strict HTML parsing, HTML5 and lxml tree comparison',catalogueCommit=pin,catalogueSha256=sha(cb),rendererSha256=sha(a.renderer.read_bytes()),reviewProgramSha256=sha(Path(__file__).read_bytes()),html5Parser='html5lib1.1',synthetic=synthetic(),browserVisualQa=False,candidatePagesVerified=False,candidateCatalogVerified=False,testedDocuments=0,results=rows)
 newcat={d['id']:d for d in json.loads(a.catalog.read_bytes())['documents']} if a.catalog else None
 for d in docs:
  raw=(a.raw/(d['revisionIdentifier']+'.json')).read_bytes();ck(sha(raw)==d['sourceSha256'],'Raw source pin differs '+d['id']);src=json.loads(raw.decode('utf-8'));ck(src['law_info']['law_id']==d['lawIdentifier'] and src['revision_info']['law_revision_id']==d['revisionIdentifier'],'Raw semantic identity differs');tree=src['law_full_text']
  old=(a.source/d['html']).read_text();m=re.search(r'<article lang="ja" data-text-sha256="([0-9a-f]{64})"><div class="source-page" data-source-page="1">(.*?)</div></article>',old,re.S);ck(m and m[1]==d['textSha256'] and sha(html.unescape(m[2]))==d['textSha256'],'Old body/pinned text hash differs '+d['id'])
  body,p,e=verify(tree,d['sourcePage']);tags.update(n[2] for n in p['nodes']);kepttags.update(n[2] for n in p['keptnodes']);ix={n[0]:n for n in p['nodes']}
  for n in p['keptnodes']:
   if n[2]=='Remarks':
    parent=n[1]
    while parent is not None:
     pn=ix[parent]
     if pn[2]=='TableStruct':under+=1;tableids.add((d['id'],parent));break
     parent=pn[1]
  suppdocs+=any(n[2]=='SupplProvision' and set(dict(n[3]))&{'AmendLawNum','Extract','Type'} for n in p['keptnodes']);excerptdocs+=any(n[2]=='MainProvision' and dict(n[3]).get('Extract')=='true' for n in p['keptnodes'])
  if a.pages:
   page=(a.pages/d['html']).read_text();m=re.search(r'<article lang="ja" data-text-sha256="([0-9a-f]{64})">(.*?)</article>',page,re.S);ck(m and m[1]==e['textSha256'] and m[2]==body,'Actual candidate differs '+d['id']);ck('Partial text reproduction' in page and 'not a complete-law or current-force certification' in page,'Candidate caveats missing')
   if newcat:
    nd=newcat[d['id']];sm=nd['structuredRendering'];ck(nd['sourceSha256']==d['sourceSha256'] and sm['originalTextSha256']==d['textSha256'] and nd['textSha256']==e['textSha256'],'Candidate provenance mismatch');ck(nd['characters']==len(''.join(l[2] for l in p['keptleaves']).encode('utf-16-le'))//2,'Candidate character count differs');ck(sm['htmlSha256']==e['htmlSha256'] and sm['omissions']==p['omissions'],'Candidate structure receipt differs');ck(nd['structuralReview']['status']=='pending' and sm['scope']=='partial-text-only','Candidate overclaims scope/review');ck(sm['excludedSourceTags']==['Table','ArithFormula','Fig'],'Excluded-tag scope differs')
  row=dict(id=d['id'],passed=True,sourceSha256=sha(raw),oldTextSha256=d['textSha256'],retainedTextSha256=e['textSha256'],bodySha256=sha(body),sourceNodes=len(p['nodes']),retainedNodes=len(p['keptnodes']),sourceLeaves=len(p['leaves']),retainedLeaves=len(p['keptleaves']),retainedAttributes=sum(len(n[3]) for n in p['keptnodes']),omissions=len(p['omissions']),annotations=len(p['annotations']));rows.append(row)
  for k in ['sourceNodes','retainedNodes','sourceLeaves','retainedLeaves','retainedAttributes','omissions','annotations']:tot[k]+=row[k]
  tot['omissionDocuments']+=bool(row['omissions'])
  if d['lawIdentifier']=='325AC0000000226' and a.golden and a.golden.is_file():
   g=a.golden.read_bytes();gm=re.search(rb'<article lang="ja" data-text-sha256="([0-9a-f]{64})">(.*?)</article>',g,re.S);ck(len(g)==12039975 and sha(g)=='e5fc9adb649165d3d4b0ade6a4421544e41329611e12ca9bfadb2ea1906ffce9','Golden page differs');ck(gm and gm[2]==body.encode() and gm[1].decode()==e['textSha256'],'Golden article/text differ');ck(sha(raw)=='3dd29e0078bf24e09c79436ce7b0f00fd2cfb5a5bbcb97bd4f4352971be68d53','Golden source differs');report['golden']=dict(passed=True,pageSha256=sha(g),articleSha256=sha(gm[2]),retainedTextSha256=e['textSha256'],bytes=len(g))
  if len(rows)%25==0:
   report.update(testedDocuments=len(rows),seconds=round(time.time()-start,2));a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'testedDocuments':len(rows),'seconds':report['seconds']}),flush=True)
 ck(not git('status','--porcelain').strip() and report['rendererSha256']==sha(a.renderer.read_bytes()),'Source or renderer changed during review')
 report.update(passed=True,testedDocuments=len(rows),totals=dict(tot),sourceTagCounts=dict(tags),retainedTagCounts=dict(kepttags),retainedRemarksUnderTableStruct=under,tableStructWithRetainedRemarks=len(tableids),documentsWithSupplementAttributes=suppdocs,documentsWithMainExtractTrue=excerptdocs,candidatePagesVerified=bool(a.pages),candidateCatalogVerified=bool(a.catalog),sourceCheckoutUnchanged=True,seconds=round(time.time()-start,3));a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['results','sourceTagCounts','retainedTagCounts']},ensure_ascii=False))
if __name__=='__main__':main()
