"""Fail-closed, escaped e-Gov JSON renderer. Generated HTML is never an input.

Source node/leaf identities and exact attributes are inert data attributes. Portal
annotations are explicitly distinguished from statutory text. Table, ArithFormula
and Fig subtrees are never reproduced. Every outermost exclusion has an auditable
marker. TableStruct siblings such as titles and Remarks remain intact.
"""
import hashlib, html, json, re
from collections import Counter

VERSION='jp-text-structure-v2'
OMITTED={'Table','ArithFormula','Fig'}
BLOCK=set('Law LawBody TOC TOCPart TOCChapter TOCSection TOCSubsection TOCDivision TOCSupplProvision MainProvision Part Chapter Article Paragraph ParagraphSentence Item ItemSentence Section Subsection Division SupplProvision TableStruct AppdxTable Remarks SupplProvisionAppdxTable List ListSentence QuoteStruct Preamble AmendProvision AmendProvisionSentence'.split())|{f'Subitem{i}{suffix}' for i in range(1,5) for suffix in ['', 'Sentence']}
LABEL=set('LawNum LawTitle TOCLabel PartTitle ChapterTitle SectionTitle SubsectionTitle DivisionTitle ArticleCaption ArticleTitle ParagraphNum ItemTitle SupplProvisionLabel ParagraphCaption AppdxTableTitle RelatedArticleNum EnactStatement RemarksLabel TableStructTitle SupplProvisionAppdxTableTitle SupplNote TOCPreambleLabel ArticleRange'.split())|{f'Subitem{i}Title' for i in range(1,5)}
INLINE={'Sentence','Column','Ruby','Rt','ArithFormula'}
TAGS=BLOCK|LABEL|INLINE|{'Table','TableRow','TableColumn','Fig'}
ATTRS={t:set() for t in TAGS}
ATTRS.update({'Law':set('Lang Era Year Num PromulgateMonth PromulgateDay LawType'.split()),'LawTitle':set('Kana Abbrev AbbrevKana'.split()),'MainProvision':{'Extract'},'SupplProvision':{'AmendLawNum','Extract','Type'},'TableColumn':set('rowspan colspan BorderBottom BorderLeft BorderRight BorderTop'.split()),'Fig':{'src'}})
for t in 'TOCPart TOCChapter TOCSection TOCSubsection TOCDivision Part Chapter Article Paragraph Item Column Subitem1 Subitem2 Subitem3 Subitem4 Section Subsection Division AppdxTable SupplProvisionAppdxTable Sentence'.split():ATTRS[t].add('Num')
for t in 'TOCChapter Chapter Article Item Subitem1'.split():ATTRS[t]|={'Delete'}
for t in 'Chapter Article Paragraph Item Subitem1'.split():ATTRS[t]|={'Hide'}
ATTRS['Paragraph']|={'OldNum','OldStyle'}
for t in 'Sentence Table AppdxTableTitle TableStructTitle SupplProvisionAppdxTableTitle'.split():ATTRS[t].add('WritingMode')
ATTRS['Sentence'].add('Function')
for t in ['Column','RemarksLabel']:ATTRS[t].add('LineBreak')
REFERENCE_TEXT={'この表の附表','附則別表第三','改正法附則別表第一'}
DOTS=set('ヽ﹅﹆・･、。•●◦○˙.．')
class Unsupported(ValueError):pass
def require(ok,message):
 if not ok:raise Unsupported(message)
def esc(s):return html.escape(s,quote=True).replace('\r','&#13;')
def esc_single(s):return html.escape(s,quote=False).replace("'",'&#39;').replace('\r','&#13;')
def compact(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def sha(x):return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def textual(n):return n if isinstance(n,str) else ''.join(textual(c) for c in n['children'])
def walk(n,path='/law_full_text',parent=None):
 yield path,n,parent
 if isinstance(n,dict):
  for i,c in enumerate(n['children']):yield from walk(c,path+'/children/'+str(i),path)

def validate(tree):
 require(isinstance(tree,dict) and tree.get('tag')=='Law','Expected law_full_text Law root')
 counts=Counter();attrs=Counter();leaves=[];nodes=[];issues=[]
 for path,n,parent in walk(tree):
  if isinstance(n,str):
   require(not any(ord(c)<32 and c not in '\n\r\t' for c in n),'Unsupported text control character at '+path)
   leaves.append(n);continue
  require(type(n) is dict and set(n)=={'tag','attr','children'},'Unknown node shape at '+path)
  tag=n['tag'];a=n['attr'];cs=n['children'];require(tag in TAGS,'Unsupported tag '+str(tag));require(type(a) is dict and type(cs) is list,'Malformed source node '+path)
  require(set(a)<=ATTRS[tag],'Unsupported '+tag+' attributes '+str(set(a)-ATTRS[tag]))
  require(all(type(v) is str for v in a.values()),'Non-string source attribute')
  for k,v in a.items():
   if k in ['Hide','Delete']:require(v=='false','Hidden/deleted node requires review')
   if k in ['Extract','OldNum','OldStyle','LineBreak']:require(v in ['true','false'],'Invalid Boolean source attribute')
   if k in ['rowspan','colspan']:require(re.fullmatch('[1-9][0-9]*',v) and int(v)<=1000,'Invalid or excessive table span')
   if k.startswith('Border'):require(v in ['none','solid'],'Unsupported cell border')
   if k=='WritingMode':require(v in ['vertical','horizontal'],'Unsupported writing mode')
   if k=='Function':require(v in ['main','proviso'],'Unsupported sentence function')
   if k=='Type':require(v in ['New','Amend'],'Unsupported supplement type')
   attrs[tag,k]+=1
  if tag=='Fig':issues.append({'kind':'withheld-figure','path':path,'src':a.get('src','')})
  if tag=='MainProvision' and a.get('Extract')=='true':issues.append({'kind':'official-main-excerpt','path':path})
  if tag=='Paragraph' and a.get('OldNum')=='true':
   nums=[x for x in cs if isinstance(x,dict) and x['tag']=='ParagraphNum'];require(len(nums)==1,'OldNum missing unique ParagraphNum')
   issues.append({'kind':'historic-numbering-metadata','path':path,'Num':a.get('Num'),'ParagraphNum':textual(nums[0])})
  if tag=='Ruby':
   require(cs and any(isinstance(c,dict) and c['tag']=='Rt' for c in cs),'Ruby missing readings')
   require(all(isinstance(c,str) or isinstance(c,dict) and c['tag']=='Rt' for c in cs),'Complex Ruby needs review')
  if tag=='Rt':require(all(isinstance(c,str) for c in cs),'Complex Rt needs review')
  nodes.append({'path':path,'tag':tag,'attr':a});counts[tag]+=1
 return {'counts':dict(counts),'nodes':nodes,'leaves':leaves,'issues':issues}

def render(tree,source_page):
 from urllib.parse import urlsplit
 url=urlsplit(source_page)
 require(url.scheme=='https' and url.netloc=='laws.e-gov.go.jp' and re.fullmatch(r'/law/[A-Za-z0-9_]+',url.path) and not url.query and not url.fragment,'Unverified official source URL')
 audit=validate(tree);ni=0;li=0;annotations=[];omissions=[];retained=[];retained_nodes=[]
 def ann(n,idx):
  tag=n['tag'];a=n['attr'];keys=[]
  if tag=='SupplProvision':keys=['AmendLawNum','Extract','Type']
  elif tag=='MainProvision':keys=['Extract']
  elif tag=='Paragraph' and a.get('OldNum')=='true':keys=['OldNum','Num']
  if not any(k in a for k in keys):return ''
  text='原データ属性 '+tag+': '+'; '.join(k+'='+json.dumps(a[k],ensure_ascii=False) for k in keys if k in a)
  if tag=='Paragraph':text+='; ParagraphNum='+json.dumps(textual(next(x for x in n['children'] if isinstance(x,dict) and x['tag']=='ParagraphNum')),ensure_ascii=False)
  annotations.append({'sourceNode':idx,'text':text})
  return '<div class="jp-source-annotation" data-jp-annotation="'+str(idx)+'" role="note"><span class="jp-annotation-label">Portal annotation · 原文の条文ではありません: </span>'+esc(text)+'</div>'
 def one(n,path='/law_full_text',parent=None):
  nonlocal ni,li
  if isinstance(n,str):
   idx=li;li+=1;retained.append({'index':idx,'text':n,'parent':parent});return '<span data-jl="'+str(idx)+'">'+esc(n)+'</span>'
  idx=ni;ni+=1;tag=n['tag'];a=n['attr'];cs=n['children']
  if tag in OMITTED:
   nodes=[v for _,v,_ in walk(n) if isinstance(v,dict)];leaves=[v for _,v,_ in walk(n) if isinstance(v,str)]
   counts=dict(Counter(v['tag'] for v in nodes));label={'TableStruct':'表','Table':'表','ArithFormula':'数式・参照ノード','Fig':'図'}[tag]
   titles=[textual(c) for c in cs if isinstance(c,dict) and c['tag'] in ['TableStructTitle','RelatedArticleNum']]
   entry={'sourceNode':idx,'parent':parent,'tag':tag,'path':path,'attributes':a,'subtreeSha256':sha(compact(n)),'sourceNodeCount':len(nodes),'firstSourceLeaf':li,'sourceLeafCount':len(leaves),'sourceLeafSequenceSha256':sha(compact(leaves)),'nestedNodeCounts':counts,'titles':titles}
   omissions.append(entry);li+=len(leaves);ni+=len(nodes)-1
   body='<strong>Portal omission · 原文の条文ではありません: '+label+'を省略しました。</strong> このポータルのテキストのみの提供範囲から、当該ノード全体を除外しています。これは部分再現です。'
   if titles:body+=' <span class="jp-omission-title">原データの見出し: '+esc(' / '.join(titles))+'</span>'
   if a.get('src'):body+=' <span>原データ識別子: '+esc(a['src'])+'</span>'
   body+=' <span class="jp-source-path">原データ位置: '+esc(path)+'</span> <a href="'+esc(source_page)+'" rel="noopener">公式原文で確認 · Official source</a>'
   return '<div class="jp-omission" data-jp-omitted-node="'+str(idx)+'" data-jp-omission="'+tag+'" data-jp-subtree-sha256="'+entry['subtreeSha256']+'" role="note">'+body+'</div>'
  retained_nodes.append({'index':idx,'parent':parent,'tag':tag,'attr':a})
  element={'Ruby':'ruby','Rt':'rt'}.get(tag,'div')
  meta=f' data-jp="{tag}:{idx}"'
  if tag=='Ruby' and any(isinstance(c,dict) and c['tag']=='Rt' and textual(c) and all(ch in DOTS for ch in textual(c)) for c in cs):meta+=' class="jp-emphasis"'
  if a:meta+=" data-ja='"+esc_single(compact(a))+"'"
  annotation=ann(n,idx);parts=[];placed=False
  if annotation and tag in ['MainProvision','Paragraph']:parts.append(annotation);placed=True
  for i,child in enumerate(cs):
   parts.append(one(child,path+'/children/'+str(i),idx))
   if annotation and isinstance(child,dict) and child['tag']=='SupplProvisionLabel':parts.append(annotation);placed=True
  if annotation and not placed:parts.insert(0,annotation)
  return '<'+element+meta+'>'+''.join(parts)+'</'+element+'>'
 body='<div class="jp-structured-source" data-jp-renderer="'+VERSION+'">'+one(tree)+'</div>'
 text=''.join(x['text'] for x in retained)
 return body,{'renderer':VERSION,'htmlSha256':sha(body),'sourceLeafSequenceSha256':sha(compact(audit['leaves'])),'retainedLeafSequenceSha256':sha(compact([r['text'] for r in retained])),'sourceTreeSha256':sha(compact(tree)),'textSha256':sha(text),'characters':len(text),'sourceLeafCount':len(audit['leaves']),'retainedLeafCount':len(retained),'sourceNodeCount':len(audit['nodes']),'annotations':annotations,'structureCounts':audit['counts'],'omissions':omissions,'issues':audit['issues'],'retainedLeaves':retained,'retainedNodes':retained_nodes}
