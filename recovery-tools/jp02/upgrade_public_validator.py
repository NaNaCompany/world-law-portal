import pathlib,json,hashlib
W=pathlib.Path(__file__).resolve().parent;S=W/'root-integration/site';read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
docs=read(W/'release/sites/world-law-jp-02/document-manifest.json')['documents'];pins=read(W/'root-history-draft/preservation.json')['files'];digest=sha(json.dumps(docs,ensure_ascii=False,separators=(',',':')).encode())
companion='''// Read-only JP02 edition extension. No mutation or publication actions.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const approvedRecordsSha256=RECORD_HASH;
const preservationPins=PINS;
export async function validateJp02Editions(read,registry){
 const records=registry.documents.filter(d=>d.repository==='world-law-jp-02');
 if(!records.length)return {records,urls:new Set(),count:0};
 assert.equal(hash(JSON.stringify(records)),approvedRecordsSha256,'Exact reviewed child editions required');
 const ids=new Set(registry.documents.map(d=>d.id));assert.equal(ids.size,registry.documents.length,'Duplicate document ID');
 const versions=new Set();
 for(const d of records){assert(!d.rootRedirect,'No fabricated root redirect');assert.equal(d.canonicalUrl,'https://nanalab.kr/world-law-jp-02/'+d.localPath);assert.equal(d.localPath,'world-laws/'+d.id+'.html');const key=d.lawIdentifier+':'+d.revisionIdentifier;assert(!versions.has(key));versions.add(key);assert(d.sourceData.includes(d.revisionIdentifier));assert.equal(d.editionScope,'current-at-check');
  for(const prefix of ['','en/','zh/','es/']){const text=await read(prefix+'index.html');assert.equal(text.split('href="'+d.canonicalUrl+'"').length-1,1);}
 }
 for(const p of preservationPins){const text=await read(p.path);const bytes=Buffer.from(text);assert.equal(hash(bytes),p.candidateHTMLSha256,'Historical shell changed');const removed=Buffer.concat([bytes.subarray(0,p.insertionOffset),bytes.subarray(p.insertionOffset+p.insertedBytes)]);assert.equal(hash(removed),p.baselineHTMLSha256,'Original full page not recoverable');const article=[...text.matchAll(/<article\\b[\\s\\S]*?<\\/article>/g)];assert.equal(article.length,1);assert.equal(hash(article[0][0]),p.baselineArticleSha256);const canon=[...text.matchAll(/<link\\b[^>]*rel="canonical"[^>]*href="([^"]+)"/g)];assert.equal(canon.length,1);assert.equal(canon[0][1],p.previousCanonicalUrl);const d=records.find(d=>d.lawIdentifier===p.lawIdentifier);assert.equal(d.lineage.previousCanonicalUrl,p.previousCanonicalUrl);assert.equal(d.lineage.previousRevisionIdentifier,p.previousRevisionIdentifier);assert(text.includes('href="'+d.canonicalUrl+'"'));}
 const pub=JSON.parse(await read('publication.json'));const status=JSON.parse(await read('publisher-status.json'));assert.equal(pub.externalJp02Documents,records.length);assert.equal(pub.externalLawDocuments,190+records.length);assert.equal(status.externalJp02Documents,records.length);assert.equal(status.aggregateLawDocuments,pub.aggregateLawDocuments);
 const c=pub.japaneseEditionCoverage;assert.equal(c.newlyCoveredLawIDs,records.filter(d=>d.editionIntent==='new-law').length);assert.equal(c.additionalNewerEditions,records.filter(d=>d.editionIntent==='newer-edition').length);assert.equal(c.uniqueLawIDs,590+c.newlyCoveredLawIDs);assert.equal(c.editionPages,590+records.length);assert.equal(c.currentEditionsMatchedToCensus,580+records.length);assert(records.every(d=>d.scopeAsOf===c.scopeAsOf));
 return {records,urls:new Set(records.map(d=>d.canonicalUrl)),count:records.length};
}
'''.replace('RECORD_HASH',json.dumps(digest)).replace('PINS',json.dumps(pins,ensure_ascii=False,separators=(',',':')))
(S/'scripts/validate-jp02-editions.mjs').write_text(companion)
p=S/'scripts/validate-jp190-transition.mjs';s=p.read_text();s="import {validateJp02Editions} from './validate-jp02-editions.mjs';\n"+s
needle="const files=new Set();";s=s.replace(needle,"const registry=JSON.parse(await read('additions-catalog.json'));const jp02=await validateJp02Editions(read,registry);\n "+needle,1)
s=s.replace("['world-law-portal','world-law-jp-01','world-law-kr-acts','world-law-kr-orders'].includes(u.pathname.split('/')[1])","(['world-law-portal','world-law-jp-01','world-law-kr-acts','world-law-kr-orders'].includes(u.pathname.split('/')[1])||jp02.urls.has(u.href))")
s=s.replace("const registry=JSON.parse(await read('additions-catalog.json'));assert.equal(registry.documents.length,356);", "assert.equal(registry.documents.length,356+jp02.count);")
s=s.replace("assert.equal(registry.externalDocuments,190);", "assert.equal(registry.externalDocuments,190+jp02.count);")
s=s.replace("ids.add(d.id);assert(!hashes.has(d.textSha256)","ids.add(d.id);if(d.repository==='world-law-jp-02')continue;assert(!hashes.has(d.textSha256)")
s=s.replace("assert.equal(pub.aggregateAdditionalForeignDocuments,2673)","assert.equal(pub.aggregateAdditionalForeignDocuments,2673+jp02.count)")
s=s.replace("assert.equal(pub.aggregateLawDocuments,2707)","assert.equal(pub.aggregateLawDocuments,2707+jp02.count)")
p.write_text(s)
# Refresh private manifests after explicit public validator extension.
A=W/'root-integration/audit';before=read(A/'baseline-files.json');after={p.relative_to(S).as_posix():sha(p.read_bytes()) for p in S.rglob('*') if p.is_file()};manifest=read(A/'change-manifest.json');changed=[p for p in after if p in before and before[p]!=after[p]];added=sorted(set(after)-set(before));assert added==['scripts/validate-jp02-editions.mjs'];assert len(changed)==19
manifest.update(fileCount=len(after),unchangedFiles=len(before)-len(changed),added=added,changed=[{'path':p,'beforeSha256':before[p],'afterSha256':after[p]} for p in sorted(changed)])
(A/'file-sha256.json').write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n');(A/'change-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('Prepared public read-only validator extension;19modified+1added,8348baselinefiles unchanged')
