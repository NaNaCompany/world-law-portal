#!/usr/bin/env python3
"""Local JP02 build only. Frozen reviewed fragments; no network or publication."""
import sys,json,hashlib,pathlib,html,re,base64
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;R=W.parent;I=R/'next-japan-inputs/jp02-batch01';O=W/'release';S=O/'sites/world-law-jp-02';A=O/'audit'
sys.path.insert(0,str(R/'split-tools'))
from build_release import page,snippets,sitemap,LANGS,DISCLAIMERS,splitarticle
sha=lambda b:hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v.encode() if isinstance(v,str) else v)
def js(p,v):put(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def pin(p,h):assert sha(p.read_bytes())==h,str(p)
pin(I/'batch.json','45dace91d4a1fdbbf25af9689fe02fcc369e9710b586bb4a51d2525c2e983b68')
pin(I/'freeze-manifest.json','567744a3f6fc683e34771cc53447410376ef1ec0122b9c7f71e92f8bea03ba76')
pin(I/'review/independent-review.json','6cd3766467c65beb0b0d7b6d96d576e1f644e720fc39a879812b23e963ffb780')
pin(I/'review/planner-result.json','2a5ec225c32825a118493dffaf10e9c16ec02473eb13ea639bb9a78bf5186dbe')
pin(R/'jp-tools/scripts/jp_structured_renderer.py','55bda06be8e8f356d08ca4f0664fc1a8b571f0b4693ee85ce9946cfd02d502ca')
for f in read(I/'freeze-manifest.json')['files']:pin(I/f['path'],f['sha256'])
b=read(I/'batch.json');plan=read(I/'review/planner-result.json');assert not plan['duplicates'];assert {x['id'] for x in plan['accepted']}=={x['id'] for x in b['documents']}
assert not O.exists(),'New isolated output required'
root=R/'root190-prepared/sites/world-law-portal';child=R/'jp01-phase1-release-v2/sites/world-law-jp-01';base=b['publicBase'];snip=snippets(root);e=lambda v:html.escape(str(v),quote=True)
assets=['.nojekyll','style.css','jp-structured.css','scripts/publisher-tags.mjs','LICENSE.md']
for asset in assets:
 source=child/asset if asset=='jp-structured.css' else root/asset
 put(S/asset,source.read_bytes())
records=[];checks=[]
for d in b['documents']:
 fragment=(I/d['fragmentFile']).read_bytes();assert sha(fragment)==d['fragmentSha256'];assert sha(d['text'].encode())==d['textSha256']
 path='world-laws/'+d['id']+'.html';url=base+path
 warning='<p class="scope official-excerpt">Official source excerpt: e-Gov marks MainProvision Extract=true. This source itself is an excerpt, not the complete main provisions.</p>' if d['officialSourceExcerpt'] else ''
 content='<h1>'+e(d['title'])+'</h1>'+warning+'<p class="scope">'+e(d['versionLabel'])+'</p>'
 content+='<dl>'+''.join('<dt>'+e(k)+'</dt><dd>'+e(v)+'</dd>' for k,v in [('Law ID',d['lawIdentifier']),('Revision ID',d['revisionIdentifier']),('Revision amendment effective date',d['effectiveDate']),('Effective-date meaning',d['effectiveDateMeaning']),('Original promulgation date',d['promulgationDate']),('Amendment promulgation date',d['amendmentPromulgationDate']),('Retrieved at',d['retrievedAt']),('Current revision observed at',d['scopeAsOf']),('Scope',d['scopeDefinition'])])+'</dl>'
 content+='<p><a href="'+e(d['sourcePage'])+'">Official source</a> · <a href="'+e(d['sourceData'])+'">Exact revision source data</a> · <a href="'+e(b['coverageEvidence']['officialSource'])+'">Dated current-revision census source</a></p>'
 if d.get('lineage'):content+='<aside class="scope edition-history">Additional newer edition. The previous page is retained unchanged: <a href="'+e(d['lineage']['previousCanonicalUrl'])+'">Previous collected edition</a>. A previous edition does not mean the law is repealed.</aside>'
 content+='<p class="scope">Unofficial processed original-language text snapshot. Tables, figures and formulas are omitted with source-location notices. No translation or certification of legal force or completeness. Census metadata and revision source data were observed separately.</p>'
 article='<article lang="ja" data-source-sha256="'+d['sourceSha256']+'" data-text-sha256="'+d['textSha256']+'">'+fragment.decode()+'</article>'
 content+=article+'<section class="source-provenance"><h2>Source, processing and reuse</h2><p>'+e(d['publisher'])+'</p><p>'+e(d['rights'])+' <a href="'+e(d['rightsUrl'])+'">Rights basis</a></p><ul>'+''.join('<li>'+e(v)+'</li>' for v in d['reuseConditions'])+'</ul><p>'+e(d['extraction'])+'</p><p>Source SHA-256: '+d['sourceSha256']+'<br>Retained text SHA-256: '+d['textSha256']+'</p></section>'
 rendered=page(d['title'],'ja',url,content,snip,base).replace('<link rel="stylesheet" href="'+base+'style.css">','<link rel="stylesheet" href="'+base+'style.css"><link rel="stylesheet" href="'+base+'jp-structured.css">')
 assert splitarticle(rendered)[1]==article
 put(S/path,rendered)
 public={k:v for k,v in d.items() if k not in ['text','fragmentFile','localRawSource','officialRevisionMetadata']}
 public.update(html=path,localPath=path,repository='world-law-jp-02',canonicalUrl=url,htmlSha256=sha(rendered.encode()),articleSha256=sha(article.encode()),sourceFragmentSha256=d['fragmentSha256'])
 records.append(public);checks.append({'path':path,'fragmentSha256':sha(fragment),'articleSha256':public['articleSha256'],'htmlSha256':public['htmlSha256']})
for lang,prefix in LANGS.items():
 heading,disclaimer=DISCLAIMERS[lang]
 content='<h1>'+e(heading)+' · JP02</h1><p class="scope">'+e(disclaimer)+'</p><p>'+str(len(records))+' selected editions: '+str(sum(x['editionIntent']=='new-law' for x in records))+' newly covered laws and '+str(sum(x['editionIntent']=='newer-edition' for x in records))+' additional newer editions. Current-edition selection observed '+e(b['coverageEvidence']['checkedAt'])+'. Existing editions remain available.</p><p><a href="https://nanalab.kr/world-law-portal/'+prefix+'">World Law Portal</a> · <a href="https://nanalab.kr/world-law-jp-01/'+prefix+'">JP01 collection</a></p><section id="country-JP"><h2>JP</h2><ul>'
 for d in records:content+='<li><a class="document-link" href="'+e(d['canonicalUrl'])+'">'+e(d['title'])+'</a> · '+e(d['revisionIdentifier'])+(' · Official source excerpt' if d['officialSourceExcerpt'] else '')+' · <a class="official-source" href="'+e(d['sourcePage'])+'">Official source</a></li>'
 content+='</ul></section><footer><a href="'+base+'additions-catalog.json">Edition provenance</a> · <a href="'+base+'sitemap.xml">Sitemap</a> · <a href="'+base+'collection-scope.json">Collection scope</a></footer>'
 put(S/(prefix+'index.html'),page(heading+' · JP02',lang,base+prefix,content,snip,base))
meta={'schemaVersion':2,'repository':'world-law-jp-02','publicBase':base,'fullSplitComplete':False,'complete':False,'scopeAsOf':b['coverageEvidence']['checkedAt'],'counts':{'localLawDocuments':len(records),'localNavigationPages':4,'localCanonicalPages':len(records)+4,'localRedirectPages':0,'localHtmlPages':len(records)+4,'newlyCoveredLawIDs':sum(x['editionIntent']=='new-law' for x in records),'additionalNewerEditions':sum(x['editionIntent']=='newer-edition' for x in records)},'interfaceLanguages':list(LANGS),'sitemap':'sitemap.xml'}
for name in ['site-manifest.json','publication.json','publisher-status.json']:js(S/name,meta)
for name in ['document-manifest.json','additions-catalog.json']:js(S/name,{'schemaVersion':2,'complete':False,'totalDocuments':len(records),'documents':records})
js(S/'catalog.json',{'schemaVersion':2,'complete':False,'totalDocuments':0,'documents':[]})
js(S/'collection-scope.json',{**meta,'textOnly':True,'imagesProvided':False,'pdfsProvided':False,'translation':False,'officialSourceExcerptDocuments':sum(x['officialSourceExcerpt'] for x in records),'omittedSubtrees':sum(len(x['omissions']) for x in records),'scope':'Partial unofficial original-language legislative snapshots, not a complete national corpus or certification of legal force. Figures, tables and formulas are omitted with exact notices. Separate newer editions retain links to earlier snapshots.'})
put(S/'sitemap.xml',sitemap([base+p for p in LANGS.values()]+[d['canonicalUrl'] for d in records]))
put(S/'README.md','# JP02 legislative snapshots\n\nPartial original-language collection with19 newly covered laws and10 additional newer editions. Earlier editions are retained. Not a complete national corpus, complete source reproduction, translation or certification of legal force. See each page for dated revision evidence and omissions.\n')
js(A/'fragment-preservation.json',checks)
js(A/'input-pins.json',{'batchSha256':sha((I/'batch.json').read_bytes()),'freezeSha256':sha((I/'freeze-manifest.json').read_bytes()),'reviewSha256':sha((I/'review/independent-review.json').read_bytes()),'plannerSha256':sha((I/'review/planner-result.json').read_bytes()),'state':'local-candidate-not-published','externalWrites':False})
files={p.relative_to(S).as_posix():sha(p.read_bytes()) for p in sorted(S.rglob('*')) if p.is_file()}
js(A/'file-sha256.json',files)
transport=[]
for p,h in files.items():
 raw=(S/p).read_bytes();args={'repository_full_name':'NaNaCompany/world-law-jp-02','content':raw.decode(),'encoding':'utf-8'};size=len(json.dumps(args,ensure_ascii=False).encode());assert size+65536<=16777216
 transport.append({'path':p,'sha256':h,'gitBlobSha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'bytes':len(raw),'utf8ArgumentBytes':size,'reserveBytes':65536})
tree=[{'path':x['path'],'mode':'100644','type':'blob','sha':x['gitBlobSha']} for x in transport];tree_args={'repository_full_name':'NaNaCompany/world-law-jp-02','base_tree_sha':'32b1f4e0044e7c3b81eac5aa47b13a46263299d8','tree_elements':tree};assert len(json.dumps(tree_args).encode())<=524288
js(A/'change-manifest.json',{'baselineCommit':'0ca4d7ee9057dc441504a53703789b98bc8f393e','baselineTree':'32b1f4e0044e7c3b81eac5aa47b13a46263299d8','delete':[],'files':transport,'state':'local-candidate-not-published'})
js(A/'tree-request.json',tree_args)
print(json.dumps({'site':str(S),'documents':len(records),'files':len(files),'bytes':sum(x['bytes'] for x in transport),'maxBlobArguments':max(x['utf8ArgumentBytes'] for x in transport),'treeArgumentBytes':len(json.dumps(tree_args).encode()),'published':False}))
