"""Additive local JP02 candidate. No network, settings, refs or transfer writes."""
import sys,pathlib,json,hashlib,shutil,re,html,subprocess
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;R=W.parent;I=R/'next-japan-inputs/jp02-batch02';OLD=R/'jp02-release-work';B=OLD/'root-integration/site';C=OLD/'release/sites/world-law-jp-02';O=W/'candidate-v3';S=O/'child';T=O/'root';A=O/'audit'
sys.path.insert(0,str(R/'split-tools'))
from build_release import page,snippets,sitemap,LANGS,DISCLAIMERS
from render_documents import render_documents
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())
e=lambda x:html.escape(str(x),quote=True)
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v.encode() if isinstance(v,str) else v)
def js(p,v):put(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def pin(p,h):assert sha(p.read_bytes())==h,str(p)
def files(p):return {f.relative_to(p).as_posix():sha(f.read_bytes()) for f in sorted(p.rglob('*')) if f.is_file()}
def delta(before,after):return {'deleted':sorted(set(before)-set(after)),'added':[{'path':p,'sha256':after[p]} for p in after if p not in before],'changed':[{'path':p,'beforeSha256':before[p],'afterSha256':after[p]} for p in after if p in before and before[p]!=after[p]],'unchanged':sum(after.get(p)==h for p,h in before.items())}
pins={'batch.json':'5f06be80083ca51ff10a3f309fce01963b43dbdcd2c4c684453d9124d5ac3e55','freeze-manifest.json':'ca03914982835a924b8ac430bf6e516faf7f8b55c284bc5819a68f081ab277ee','review/independent-review.json':'da32a36802e17ea554834cc2f9334edc0fda0509efebf1592984bd461b594224'}
for p,h in pins.items():pin(I/p,h)
pin(R/'jp-tools/scripts/jp_structured_renderer.py','55bda06be8e8f356d08ca4f0664fc1a8b571f0b4693ee85ce9946cfd02d502ca')
for f in read(I/'freeze-manifest.json')['files']:pin(I/f['path'],f['sha256'])
b=read(I/'batch.json');review=read(I/'review/independent-review.json');assert review['frozenInputs']['batchFileSha256']==pins['batch.json'];assert len(b['documents'])==47
oldrecords=read(C/'document-manifest.json')['documents']; assert len(oldrecords)==29
assert all(d['editionIntent']=='new-law' and not d.get('lineage') for d in b['documents'])
assert {d['id'] for d in review['documents']}=={d['id'] for d in b['documents']}
assert not O.exists(),'Immutable candidate already exists; use a new output version'
cb=files(C);rb=files(B);assert len(cb)==47 and len(rb)==8368
shutil.copytree(C,S);shutil.copytree(B,T)
new,checks=render_documents(b,I,S,snippets(B),put);records=oldrecords+new;base=b['publicBase']
assert len({d['id'] for d in records})==len(records)
for d in oldrecords:assert (S/d['localPath']).read_bytes()==(C/d['localPath']).read_bytes()
# Each article keeps its own observation date. Aggregate scope records the range, not a fabricated shared date.
dates=sorted({d['scopeAsOf'] for d in records});scopeRange={'earliest':dates[0],'latest':dates[-1],'observations':dates,'meaning':'Per-document dated API metadata observations; no certification of current legal force.'}
for lang,prefix in LANGS.items():
 heading,disclaimer=DISCLAIMERS[lang]
 content='<h1>'+e(heading)+' · JP02</h1><p class="scope">'+e(disclaimer)+'</p><p>'+str(len(records))+' selected editions: '+str(sum(d['editionIntent']=='new-law' for d in records))+' newly covered laws and '+str(sum(d['editionIntent']=='newer-edition' for d in records))+' additional newer editions. Each page retains its own source observation date. Existing editions remain available.</p><p><a href="https://nanalab.kr/world-law-portal/'+prefix+'">World Law Portal</a> · <a href="https://nanalab.kr/world-law-jp-01/'+prefix+'">JP01 collection</a></p><section id="country-JP"><h2>JP</h2><ul>'
 for d in records:content+='<li><a class="document-link" href="'+e(d['canonicalUrl'])+'">'+e(d['title'])+'</a> · '+e(d['revisionIdentifier'])+(' · Official source excerpt' if d['officialSourceExcerpt'] else '')+' · <a class="official-source" href="'+e(d['sourcePage'])+'">Official source</a></li>'
 content+='</ul></section><footer><a href="'+base+'additions-catalog.json">Edition provenance</a> · <a href="'+base+'sitemap.xml">Sitemap</a> · <a href="'+base+'collection-scope.json">Collection scope</a></footer>'
 put(S/(prefix+'index.html'),page(heading+' · JP02',lang,base+prefix,content,snippets(B),base))
for name in ['document-manifest.json','additions-catalog.json']:
 x=read(S/name);x.update(totalDocuments=len(records),documents=records);js(S/name,x)
for name in ['site-manifest.json','publication.json','publisher-status.json','collection-scope.json']:
 x=read(S/name);x.update(scopeAsOf=dates[-1],observationScope=scopeRange);x['counts'].update(localLawDocuments=len(records),localCanonicalPages=len(records)+4,localHtmlPages=len(records)+4,newlyCoveredLawIDs=sum(d['editionIntent']=='new-law' for d in records),additionalNewerEditions=sum(d['editionIntent']=='newer-edition' for d in records))
 if name=='collection-scope.json':x.update(officialSourceExcerptDocuments=sum(d['officialSourceExcerpt'] for d in records),omittedSubtrees=sum(len(d['omissions']) for d in records))
 js(S/name,x)
put(S/'sitemap.xml',sitemap([base+p for p in LANGS.values()]+[d['canonicalUrl'] for d in records]))
put(S/'README.md','# JP02 legislative snapshots\n\nPartial original-language collection: '+str(len(records))+' editions, including '+str(sum(d['editionIntent']=='new-law' for d in records))+' newly covered laws and10 additional newer editions. Earlier editions are retained. Each page preserves its dated source metadata. Not a complete national corpus, complete source reproduction, translation or certification of legal force. Figures, tables and formulas are omitted with source-location notices.\n')
reg=read(T/'additions-catalog.json');reg['documents']+=new;ext=sum(d.get('repository','world-law-portal')!='world-law-portal' for d in reg['documents']);reg.update(totalDocuments=len(reg['documents']),aggregateDocuments=len(reg['documents']),externalDocuments=ext,localDocuments=len(reg['documents'])-ext,updatedAt=b['preparedAt']);js(T/'additions-catalog.json',reg)
# Derive Japanese identities from actual root catalogs and external records, not expected counts.
allrecords=read(T/'catalog.json')['documents']+reg['documents']
def lawid(d):return d.get('lawIdentifier') or ((re.search(r'^jp-egov-([a-z0-9]+)',d.get('id',''),re.I) or re.search(r'/law/([a-z0-9]+)',d.get('sourcePage',''),re.I)).group(1).upper() if d.get('country')=='JP' else None)
jp=[d for d in allrecords if d.get('country')=='JP'];ids={d['id'] for d in jp}
for p in sorted((T/'world-laws').glob('jp-egov-*.html')):
 if '<article' in p.read_text() and p.stem not in ids:jp.append({'id':p.stem,'country':'JP'});ids.add(p.stem)
unique={lawid(d) for d in jp};assert None not in unique
ident=read(B/'publication.json')['japaneseEditionCoverage'];ident['baselineMeaning']='currentEditionsBeforeBatch=580 is the original pre-JP02-series current-edition baseline, not the prior incremental batch. newlyCoveredLawIDs and additionalNewerEditions are cumulative across JP02 batches.';ident.update(uniqueLawIDs=len(unique),editionPages=len(jp),currentEditionsMatchedToCensus=len(unique),newlyCoveredLawIDs=sum(d['editionIntent']=='new-law' for d in records),additionalNewerEditions=sum(d['editionIntent']=='newer-edition' for d in records),scopeAsOf=dates[-1],observationScope=scopeRange,scope=review['coverage']['scope']+' Per-page observations are retained. API metadata is not certification of current legal force.')
for name in ['publication.json','publisher-status.json']:
 x=read(T/name);x.update(aggregateAdditionalForeignDocuments=x['additionalForeignDocuments']+ext,aggregateLawDocuments=2517+ext,externalLawDocuments=ext,externalJp02Documents=len(records),japaneseEditionCoverage=ident)
 if name=='publication.json':x.update(lastAdditionAt=b['preparedAt'],additionsCatalogDocuments=len(reg['documents']),externalAdditionsCatalogDocuments=ext,aggregateAdditionsCatalogDocuments=len(reg['documents']))
 js(T/name,x)
x=read(T/'collection-scope.json');j=next(d for d in x['countries'] if d['country']=='JP');j.update(addedDocuments=ext,externalLawDocuments=ext,aggregateLawDocuments=len(jp),externalAddedDocuments=ext,editionCoverage=ident,addedDocumentScope=f'190 corrected snapshots in JP01 plus {len(records)} selected editions in JP02. All400 existing root Japanese articles and earlier URLs remain. Per-page observation dates and original excerpt notices are preserved. Tables, figures and formulas are omitted with notices; not a complete national corpus or legal-force certification.');js(T/'collection-scope.json',x)
labels={'':'일본 신규 법률47건 추가. 기존 판본과 관찰일은 보존됩니다. 일본 고유 법률656개, 판본666개. 완전한 법령 전수나 완전 원문이 아닙니다.','en/':'47 newly covered Japanese laws. Earlier editions and their observation dates are preserved.656 unique Japanese law IDs and666 edition pages; not a complete national corpus or complete source reproduction.','zh/':'新增47项日本法律。保留旧版本及其查询日期。656个日本法律标识、666个版本页面；并非完整法律库或完整原文。','es/':'47 leyes japonesas incorporadas. Se conservan las ediciones anteriores y sus fechas de consulta.656 leyes japonesas únicas y666 páginas de edición; no es un corpus nacional completo ni una reproducción íntegra.'}
for prefix,label in labels.items():
 p=T/(prefix+'index.html');raw=p.read_text();start=raw.index('<section class="jp02-editions">');end=raw.index('</section>',start)+len('</section>');cards='<section class="jp02-editions"><h4>JP02</h4><p class="scope">'+e(label)+'</p><ul>'
 for d in records:cards+='<li><div class="document"><a class="document-link" lang="ja" href="'+e(d['canonicalUrl'])+'">'+e(d['title'])+'</a><p class="edition">'+e(d['versionLabel'])+'</p><a class="official-source" href="'+e(d['sourceData'])+'">Official revision source</a></div></li>'
 cards+='</ul></section>';put(p,raw[:start]+cards+raw[end:])
# Keep all original historical preservation checks and mutation guards. Extend only read-only accepted-record/date pins.
p=T/'scripts/validate-jp02-editions.mjs';v=p.read_text();digest=subprocess.check_output(['node','-e','const fs=require("fs"),c=require("crypto");console.log(c.createHash("sha256").update(JSON.stringify(JSON.parse(fs.readFileSync(process.argv[1])).documents)).digest("hex"))',str(S/'document-manifest.json')],text=True).strip();v=re.sub(r'const approvedRecordsSha256="[a-f0-9]+";',f'const approvedRecordsSha256="{digest}";',v)
v=v.replace('assert(records.every(d=>d.scopeAsOf===c.scopeAsOf));',"assert.deepEqual([...new Set(records.map(d=>d.scopeAsOf))].sort(),c.observationScope.observations);assert.equal(c.scopeAsOf,c.observationScope.latest);")
put(p,v)
ca=files(S);ra=files(T);cd=delta(cb,ca);rd=delta(rb,ra);assert not cd['deleted'] and not rd['deleted'] and not rd['added'];assert len(cd['added'])==47;assert len(rd['changed'])==9
for name in ['child','root']:
 before,after,d=(cb,ca,cd) if name=='child' else (rb,ra,rd);js(A/(name+'-baseline-files.json'),before);js(A/(name+'-file-sha256.json'),after);js(A/(name+'-delta.json'),d)
js(A/'input-pins.json',pins);js(A/'fragment-preservation.json',checks);js(A/'summary.json',{'state':'local-candidate-not-published','publicationEligible':False,'childFiles':len(ca),'childEditions':len(records),'childCanonicalPages':len(records)+4,'rootFiles':len(ra),'rootLocalDocuments':2517,'rootExternalDocuments':ext,'rootDocumentUnits':2517+ext,'additions':len(reg['documents']),'japaneseCoverage':ident,'inputReviewSha256':pins['review/independent-review.json'],'requirements':['Independent final candidate review','Parent fresh expected-head CAS','Actual child live evidence before root publication'],'expectedHeads':{'root':'7af86ecca1cc668461b9980d66c521df3c9b5d5d','child':'4f5198973aaeb55cadd37054d525642195358697'},'expectedTrees':{'root':'bc5954cf884e3a7595b559b166066851f267923e','child':'76d32a376af0a67bf4f3d1f244427b88baba201f'}})
assert len(unique)==656 and len(jp)==666
print(json.dumps(read(A/'summary.json'),ensure_ascii=False))
