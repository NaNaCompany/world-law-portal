// Read-only inventory. JP190 routing is an immutable transition receipt, not a law body.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
export const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
export const ROOT = 'https://nanalab.kr/world-law-portal/';
export const ROUTING_SHA256 = 'b0d0bf58a0d96445cd0c18d3d41a1c73fd4878e84e4b0d18c1ec12d42dfda249';
export const normalizeTitle = s => s.normalize('NFKC').replace(/\s+/g,' ').trim().toLowerCase();
export function normalizeUrl(s) { const u = new URL(s); assert(['http:','https:'].includes(u.protocol)); u.protocol='https:'; u.hash=''; u.hostname=u.hostname.toLowerCase().replace(/^www\./,''); u.searchParams.sort(); return u.href.replace(/\/$/,''); }
const decode = s => s.replace(/&#(x[\da-f]+|\d+);/gi,(_,n)=>String.fromCodePoint(n[0].toLowerCase()==='x'?parseInt(n.slice(1),16):Number(n))).replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&nbsp;',' ').replaceAll('&amp;','&');
export const plainBody = s => decode(s.replace(/<[^>]*>/g,' ')).replace(/\s+/g,' ').trim();
export function assertRouting(manifestText, registry, expectedDigest=ROUTING_SHA256) {
 assert.equal(sha256(manifestText),expectedDigest,'Routing manifest differs from reviewed receipt');
 const manifest=JSON.parse(manifestText); assert.equal(manifest.fullSplitComplete,false); assert.equal(manifest.routingMode,'partial-jp190-external');
 assert.equal(manifest.routes.length,190); const map=new Map();
 for(const r of manifest.routes) {
  assert(!map.has(r.oldPath),'Duplicate route'); map.set(r.oldPath,r);
  assert.equal(r.oldPath,'world-laws/'+r.id+'.html'); assert.equal(r.canonicalUrl,'https://nanalab.kr/world-law-jp-01/'+r.localPath);
  for(const key of ['rootRedirectHtmlSha256','originalRootHtmlSha256','originalTextSha256','correctedTextSha256','sourceSha256','correctedSourceHtmlSha256','childHtmlSha256','childArticleSha256'])assert(/^[a-f0-9]{64}$/.test(r[key]),'Missing route digest '+key);
  const matches=registry.documents.filter(d=>d.id===r.id); assert.equal(matches.length,1,'Missing/duplicate external record'); const d=matches[0];
  for(const [key,value] of Object.entries({repository:'world-law-jp-01',localPath:r.localPath,html:r.oldPath,canonicalUrl:r.canonicalUrl,htmlSha256:r.childHtmlSha256,articleSha256:r.childArticleSha256,textSha256:r.correctedTextSha256,sourceSha256:r.sourceSha256}))assert.equal(d[key],value,'External record drift '+key);
  assert.equal(d.rootRedirect.htmlSha256,r.rootRedirectHtmlSha256); assert.equal(d.originalRootSnapshot.textSha256,r.originalTextSha256); assert.equal(d.originalRootSnapshot.sourceSha256,r.sourceSha256); assert.equal(d.structuredRendering.originalTextSha256,r.originalTextSha256);
 }
 return map;
}
export function lawKey(d) {const id=d.lawIdentifier||d.id?.match(/^jp-egov-([a-z0-9]+)(?:_|$)/i)?.[1]||d.sourcePage?.match(/laws\.e-gov\.go\.jp\/law\/([a-z0-9]+)/i)?.[1];return id?(d.country||'JP')+':'+id.toUpperCase():null;}
export function revisionKey(d) {const revision=d.revisionIdentifier||d.id?.match(/^jp-egov-(.+_.+)$/i)?.[1];return revision?revision.toUpperCase():null;}
export function createDedup(records=[]) {
 const keys={lawIds:new Set(),versions:new Set(),paths:new Set(),ids:new Set(),urls:new Set(),hashes:new Set(),titles:new Set(),bodies:new Set()}, documents=new Map();
 const add=d=>{const previous=documents.get(d.id)||{}; d={...previous,...Object.fromEntries(Object.entries(d).filter(([,v])=>v!==undefined))};if(d.id)documents.set(d.id,d); const law=lawKey(d),revision=revisionKey(d);if(law)keys.lawIds.add(law);if(law&&revision)keys.versions.add(law+':'+revision);if(d.canonicalUrl)keys.paths.add(d.canonicalUrl);if(d.id)keys.ids.add(d.id);for(const u of [d.sourcePage,d.sourceData,d.sourceDownloadUrl].filter(u=>typeof u==='string'&&u))keys.urls.add(normalizeUrl(u));for(const h of [d.textSha256,d.originalRootSnapshot?.textSha256].filter(Boolean))keys.hashes.add(h);if(d.country&&d.title)keys.titles.add(d.country+':'+normalizeTitle(d.title));if(d.text)d.bodySha256=sha256(plainBody(d.text));if(d.bodySha256)keys.bodies.add(d.bodySha256);};
 records.forEach(add);
 return {keys,documents,add,reason(d,{verifiedEdition=false,sameTextReviewed=false}={}) {const law=lawKey(d),revision=revisionKey(d);if(keys.ids.has(d.id))return 'id';if(d.canonicalUrl&&keys.paths.has(d.canonicalUrl))return 'canonical/output path';if(law&&revision&&keys.versions.has(law+':'+revision))return 'law ID/revision ID';if(law&&keys.lawIds.has(law)&&!verifiedEdition)return 'official law ID';const bodyHash=sha256(plainBody(d.text));const matching=[...documents.values()].filter(r=>[r.textSha256,r.originalRootSnapshot?.textSha256].includes(d.textSha256)||r.bodySha256===bodyHash);const allowSameText=verifiedEdition&&sameTextReviewed&&matching.length>0&&matching.every(r=>lawKey(r)===law);if(keys.hashes.has(d.textSha256)&&!allowSameText)return 'text SHA-256';if(keys.bodies.has(bodyHash)&&!allowSameText)return 'normalized local body';if(!verifiedEdition&&keys.urls.has(normalizeUrl(d.sourcePage)))return 'official URL';if(!verifiedEdition&&keys.titles.has(d.country+':'+normalizeTitle(d.title)))return 'country/title';return null;}};
}
export function assertCounts({registry,pub,status,localLaws,htmlPages,canonicalPages,jpRedirects,krRedirects,verifiedChildRecords=[]}) {
 const external=registry.documents.filter(d=>d.repository&&d.repository!=='world-law-portal').length;
 const local=registry.documents.length-external;
 const extra=registry.documents.filter(d=>d.repository&& !['world-law-portal','world-law-jp-01'].includes(d.repository));
 assert.equal(extra.length,verifiedChildRecords.length,'Child inventory required');
 assert.equal(new Set(verifiedChildRecords.map(d=>d.id)).size,verifiedChildRecords.length,'Duplicate child identity');
 for(const d of extra){const v=verifiedChildRecords.find(v=>v.id===d.id);assert(v,'Unknown child record');assert.equal(d.repository,'world-law-jp-02');assert(!d.rootRedirect,'Invented child-only root redirect');assert.equal(d.canonicalUrl,'https://nanalab.kr/world-law-jp-02/'+d.localPath);for(const k of ['country','id','lawIdentifier','revisionIdentifier','sourceSha256','textSha256','articleSha256','htmlSha256','canonicalUrl','repository','localPath'])assert.equal(d[k],v[k],'Child inventory drift '+k);}
 assert.equal(external,jpRedirects+extra.length,'Unreviewed external ownership');
 if(extra.length){assert.equal(pub.externalLawDocuments,external);assert.equal(pub.externalJp02Documents,extra.length);assert.equal(status.externalLawDocuments,external);assert.equal(status.externalJp02Documents,extra.length);}

 for(const [key,val] of Object.entries({totalDocuments:registry.documents.length,aggregateDocuments:registry.documents.length,localDocuments:local,externalDocuments:external}))assert.equal(registry[key],val,'Catalog count drift '+key);
 for(const [key,val] of Object.entries({localLawDocuments:localLaws,aggregateLawDocuments:localLaws+external,htmlPages,publisherTagPages:htmlPages,localHtmlPages:htmlPages,sitemapUrls:canonicalPages,localCanonicalPages:canonicalPages,localRedirectPages:jpRedirects+krRedirects,koreanRedirects:krRedirects,externalJp190Documents:jpRedirects,localAdditionsCatalogDocuments:local,externalAdditionsCatalogDocuments:external,aggregateAdditionsCatalogDocuments:registry.documents.length,additionsCatalogDocuments:registry.documents.length,additionalForeignDocuments:localLaws-pub.existingGlobalDocuments,aggregateAdditionalForeignDocuments:localLaws-pub.existingGlobalDocuments+external}))assert.equal(pub[key],val,'Publication count drift '+key);
 assert.equal(status.additionalForeignDocuments,pub.additionalForeignDocuments); assert.equal(htmlPages,localLaws+jpRedirects+krRedirects+pub.localNavigationPages);
 return {localLaws,externalLaws:external,aggregateLaws:localLaws+external,htmlPages,canonicalPages,localCatalog:local,externalCatalog:external,aggregateCatalog:registry.documents.length,jpRedirects,krRedirects};
}
export async function inventory(root,verifiedChildRecords=[]) {
 const read=p=>fs.readFile(path.join(root,p),'utf8');
 const registry=JSON.parse(await read('additions-catalog.json')), pub=JSON.parse(await read('publication.json')),status=JSON.parse(await read('publisher-status.json'));
 const routes=assertRouting(await read('jp190-routes.json'),registry);
 const initial=JSON.parse(await read('catalog.json')); const dedup=createDedup([...initial.documents,...registry.documents]);
 const canonicals=new Set(); let htmlPages=0,localLaws=0,jpRedirects=0,krRedirects=0; const files=[];
 async function walk(dir='') {for(const e of await fs.readdir(path.join(root,dir),{withFileTypes:true})){assert(!e.isSymbolicLink(),'Symlink forbidden'); const p=path.posix.join(dir,e.name); if(e.isDirectory()){if(!['.git','node_modules'].includes(e.name))await walk(p);}else files.push(p);}} await walk();
 for(const file of files.filter(p=>p.endsWith('.html'))) {
  const html=await read(file); htmlPages++; const canonical=[...html.matchAll(/<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"/g)]; assert.equal(canonical.length,1,'Canonical missing '+file); const url=canonical[0][1];
  if(routes.has(file)){const r=routes.get(file); assert.equal(sha256(html),r.rootRedirectHtmlSha256,'Redirect drift');assert.equal(url,r.canonicalUrl);assert(!/<article\b/.test(html),'Redirect parsed as statute');jpRedirects++;continue;}
  if(file.startsWith('kr/laws/')&&/^https:\/\/nanalab.kr\/world-law-kr-(acts|orders)\//.test(url)){assert(html.includes('http-equiv="refresh"')); krRedirects++;continue;}
  assert.equal(url,ROOT+(file.endsWith('index.html')?file.slice(0,-10):file),'Unexpected external/local canonical');assert(!canonicals.has(url));canonicals.add(url);
  const articles=[...html.matchAll(/<article\b[^>]*>([\s\S]*?)<\/article>/g)]; if(!articles.length)continue; localLaws++;
  const title=decode(html.match(/<h1[^>]*>([^<]*)<\/h1>/)?.[1]||'');dedup.add({id:path.basename(file,'.html'),country:path.basename(file).slice(0,2).toUpperCase(),title,bodySha256:sha256(plainBody(articles.map(a=>a[1]).join(' '))),canonicalUrl:url,htmlSha256:sha256(html),articleSha256:sha256(articles.map(a=>a[0]).join('')),textSha256:html.match(/data-text-sha256="([a-f0-9]{64})"/)?.[1]});
  for(const m of html.matchAll(/data-text-sha256="([a-f0-9]{64})"/g))dedup.keys.hashes.add(m[1]);
  for(const [,body] of articles)dedup.keys.bodies.add(sha256(plainBody(body)));
  for(const m of html.matchAll(/<a[^>]*href="([^"]+)"[^>]*>(?:Official source[^<]*|원문 출처|공식 원문)[<]/g))dedup.keys.urls.add(normalizeUrl(decode(m[1])));
 }
 assert.equal(jpRedirects,190,'Missing routed HTML');assert.equal(krRedirects,5628,'Korean redirect drift');
 const locations=[...(await read('sitemap.xml')).matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>m[1]); assert.equal(new Set(locations).size,locations.length);assert.deepEqual(new Set(locations),canonicals,'Sitemap/canonical mismatch');
 const counts=assertCounts({registry,pub,status,localLaws,htmlPages,canonicalPages:canonicals.size,jpRedirects,krRedirects,verifiedChildRecords});
 return {counts,dedup,files,registry};
}
