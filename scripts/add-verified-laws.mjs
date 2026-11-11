import {blockLegacyMutation} from './root190-route-guard.mjs';
await blockLegacyMutation(new URL('../jp190-routes.json',import.meta.url),"add-verified-laws.mjs");
// Add complete, independently checked original-language source text to the existing portal.
// Input receipts stay outside this published repository. Only public provenance is retained.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {renderReuseSection} from './reuse-provenance.mjs';
import {publisherHead,publisherBodyStart,publisherFooter,assertPublisherTags} from './publisher-tags.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base='https://nanalab.kr/world-law-portal/';
const inputFiles=process.argv.slice(2);assert(inputFiles.length,'Usage: node scripts/add-verified-laws.mjs /path/to/verified.json [...]');
const read=relative=>fs.readFile(path.join(root,relative),'utf8');
const write=(relative,value)=>fs.writeFile(path.join(root,relative),value);
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const decode=s=>s.replaceAll('&amp;','&').replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&lt;','<').replaceAll('&gt;','>');
const stableUrl=s=>{const u=new URL(s);u.hash='';u.hostname=u.hostname.toLowerCase().replace(/^www\./,'');return u.href.replace(/\/$/,'');};
let registry;try{registry=JSON.parse(await read('additions-catalog.json'));}catch(e){if(e.code!=='ENOENT')throw e;registry={schemaVersion:1,complete:false,description:'Verified additions to the legacy catalogue. Original-language source snapshots, not a complete or certified current-law database.',documents:[]};}
const existingIds=new Set(registry.documents.map(d=>d.id)), existingUrls=new Set(), existingHashes=new Set(),existingTitles=new Set();
for(const folder of ['world-laws','legacy-laws'])for(const file of await fs.readdir(path.join(root,folder))){
 if(!file.endsWith('.html'))continue;
 const html=await read(folder+'/'+file);
 existingIds.add(file.slice(0,-5));
 for(const m of html.matchAll(/data-text-sha256="([a-f0-9]{64})"/g))existingHashes.add(m[1]);
 const title=decode(html.match(/<h1[^>]*>([^<]*)<\/h1>/)?.[1]||'').normalize('NFKC').replace(/\s+/g,' ').trim();
 if(title)existingTitles.add(file.slice(0,2).toUpperCase()+':'+title);
 for(const m of html.matchAll(/<a[^>]*href="([^"]+)"[^>]*>(?:Official source[^<]*|원문 출처|공식 원문)[<]/g))try{existingUrls.add(stableUrl(decode(m[1])));}catch{}
}
const accepted=[],skipped=[];
for(const inputFile of inputFiles){
 const input=JSON.parse(await fs.readFile(inputFile,'utf8'));assert(Array.isArray(input),'Input must be a JSON array');
 for(const d of input){
  assert(/^[a-z0-9][a-z0-9_-]*$/.test(d.id),'Invalid ID '+d.id);assert(/^[A-Z]{2}$/.test(d.country));
  for(const key of ['title','documentLanguage','kind','sourcePage','publisher','versionLabel','retrievedAt','rights','rightsUrl','sourceSha256','textSha256','text','extraction'])assert(typeof d[key]==='string'&&d[key].trim(),'Missing '+key+' for '+d.id);
  assert(/^https?:$/.test(new URL(d.sourcePage).protocol)&&!/^javascript:|\.pdf(?:[?#]|$)/i.test(d.sourcePage));
  assert(/^https?:$/.test(new URL(d.rightsUrl).protocol));
  assert(/^[a-f0-9]{64}$/.test(d.sourceSha256));assert.equal(hash(d.text),d.textSha256,'Text receipt mismatch '+d.id);
  assert(d.text.length>=200,'Body suspiciously short '+d.id);assert(Array.isArray(d.completenessChecks)&&d.completenessChecks.length,'Completeness checks required');
  assert(Array.isArray(d.reuseConditions)&&d.reuseConditions.length,'Reuse conditions required');
  const titleKey=d.country+':'+d.title.normalize('NFKC').replace(/\s+/g,' ').trim();
  let reason=existingIds.has(d.id)?'id':existingHashes.has(d.textSha256)?'text SHA-256':existingUrls.has(stableUrl(d.sourcePage))?'source URL':existingTitles.has(titleKey)?'country and title':null;
  if(reason){skipped.push({id:d.id,reason});continue;}
  existingIds.add(d.id);existingHashes.add(d.textSha256);existingUrls.add(stableUrl(d.sourcePage));existingTitles.add(titleKey);accepted.push(d);
 }
}
if(!accepted.length){console.log(JSON.stringify({added:0,skipped},null,2));process.exit(0);}
accepted.sort((a,b)=>a.country.localeCompare(b.country)||a.id.localeCompare(b.id));
const banners='<!-- NaNa shared book banner --><script defer src="https://nanalab.kr/src_cdn/banner/astra.js"></script><!-- /NaNa shared book banner -->';
for(const [i,d] of accepted.entries()){
 const slug=d.id+'.html'; const prev=accepted[i-1], next=accepted[i+1];
 const dl=[['Publisher',d.publisher],['Retrieved',d.retrievedAt],['Reuse',d.rights],['Source SHA-256',d.sourceSha256],['Text SHA-256',d.textSha256]];
 const html=`<!doctype html><html lang="${esc(d.documentLanguage)}"><head>${banners}<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(d.title)} · NaNa Law Library</title><link rel="canonical" href="${base}world-laws/${slug}"><link rel="stylesheet" href="../style.css">${publisherHead}</head><body>${publisherBodyStart}<header><a class="brand" href="../">NaNa Law Library</a><a href="${base}">세계 법령포털</a></header><main class="law-document"><p class="kind">${esc(d.country)} · ${esc(d.kind)} · ${esc(d.documentLanguage)}</p><h1 lang="${esc(d.documentLanguage)}">${esc(d.title)}</h1><p class="edition">${esc(d.versionLabel)}</p><p><a href="${esc(d.sourcePage)}" rel="noopener">Official source / 공식 원문</a></p><dl>${dl.map(([k,v])=>`<dt>${k}</dt><dd${k.includes('SHA-256')?' class="hash"':''}>${esc(v)}${k==='Reuse'?` · <a href="${esc(d.rightsUrl)}" rel="noopener">Reuse terms</a>`:''}</dd>`).join('')}</dl>${renderReuseSection(d)}<p class="transformation-notice"><strong>Changes:</strong> ${esc(d.extraction)}</p><p class="scope">Original-language source snapshot; no translation. Independent, unofficial reproduction. Only the listed document is collected, not all legislation of this country. Check the official source for legal force, latest amendments and complete formatting. Images and PDF files are not reproduced.</p><article lang="${esc(d.documentLanguage)}" data-text-sha256="${d.textSha256}"><div class="source-page" data-source-page="1">${esc(d.text)}</div></article><nav class="document-pagination" aria-label="Previous and next law in this collection">${prev?`<a rel="prev" href="${prev.id}.html">← Previous law: ${esc(prev.title)}</a>`:''}${next?`<a rel="next" href="${next.id}.html">Next law →: ${esc(next.title)}</a>`:''}</nav><p><a href="../#country-${d.country}">Country index / 국가별 목록</a> · <a href="../">Main index</a></p><footer><p>독립 자료실 · 정부 공식 서비스가 아닙니다. 원문 언어 그대로 제공하며 법령을 번역·요약하지 않습니다. 판본과 법적 효력은 공식 출처에서 확인하세요.</p></footer></main><a class="more-apps" href="https://nanalab.kr/apps/" lang="en">More Apps</a>${publisherFooter}</body></html>\n`;
 assertPublisherTags(html);await write('world-laws/'+slug,html);
 const publicFields=['id','country','countryNameKo','title','documentLanguage','kind','sourcePage','publisher','versionLabel','retrievedAt','rights','rightsUrl','sourceSha256','textSha256','extraction','completenessChecks','reuseConditions','siteTermsReview','rightsEvidenceUrls','lawIdentifier','revisionIdentifier','sourceData','sourceDownloadUrl','officialLawType','snapshotDate','effectiveDate'];
 const record=Object.fromEntries(publicFields.filter(k=>d[k]!==undefined).map(k=>[k,d[k]]));record.html='world-laws/'+slug;record.translation=false;record.fullCountryCollection=false;record.characters=d.text.length;registry.documents.push(record);
}
for(const [file,language,prefix] of [['index.html','ko','./'],['en/index.html','en','../'],['zh/index.html','zh','../'],['es/index.html','es','../']]){
 let html=await read(file);
 const marker=/<!-- github-publisher-world:start -->([\s\S]*?)<!-- github-publisher-world:end -->/;
 const old=html.match(marker)?.[1];assert(old,'Missing index marker '+file);
 const blocks=new Map();
 for(const m of old.matchAll(/<h3(?: id="country-([A-Z]{2})")?>([\s\S]*?)<\/h3><ol>([\s\S]*?)<\/ol>/g)){
  const code=m[1]||m[2];assert(/^[A-Z]{2}$/.test(code),'Unexpected country heading '+code);blocks.set(code,{heading:m[2],items:m[3]});
 }
 assert(blocks.size,'No country groups');
 const firstHeading=old.indexOf('<h3');let intro=old.slice(0,firstHeading);
 for(const d of accepted){
  if(!blocks.has(d.country)){let label;try{label=new Intl.DisplayNames([language],{type:'region'}).of(d.country);}catch{label=d.country;}blocks.set(d.country,{heading:esc(label)+' · '+d.country,items:''});}
  blocks.get(d.country).items+=`<li><div class="document"><a class="document-link" href="${prefix}world-laws/${d.id}.html" lang="${esc(d.documentLanguage)}">${esc(d.title)}</a><p class="edition">${esc(d.versionLabel)}</p></div></li>`;
 }
 const count=[...blocks.values()].reduce((n,b)=>n+(b.items.match(/<li>/g)||[]).length,0);intro=intro.replace(/<small>\d+<\/small>/,`<small>${count}</small>`);
 const replacement=intro+[...blocks].sort(([a],[b])=>a.localeCompare(b)).map(([country,b])=>`<h3 id="country-${country}">${b.heading}</h3><ol>${b.items}</ol>`).join('')+'</section>';
 html=html.replace(marker,'<!-- github-publisher-world:start -->'+replacement+'<!-- github-publisher-world:end -->');
 // Preserve existing navigation and add routes only for countries not already represented there.
 html=html.replace(/<div class="country-nav">([\s\S]*?)<\/div>/,(_,nav)=>{
  for(const country of [...new Set(accepted.map(d=>d.country))].sort())if(!new RegExp(`href="#(?:country-)?${country}"`).test(nav)){
   const label=language==='ko'?(accepted.find(d=>d.country===country).countryNameKo||country):new Intl.DisplayNames([language],{type:'region'}).of(country);
   nav+=`<a href="#country-${country}">${esc(label)}</a>`;
  }return '<div class="country-nav">'+nav+'</div>';
 });
 html=html.replace(/(<a href="(?:\.\/|\.\.\/)catalog\.json">)[^<]+(<\/a>)/, '$1'+({ko:'초기 문서 목록 · SHA-256',en:'Initial document catalogue · SHA-256',zh:'初始文档目录 · SHA-256',es:'Catálogo inicial · SHA-256'}[language])+'$2');
 if(!html.includes('href="'+prefix+'additions-catalog.json"'))html=html.replace(/(<a href="(?:\.\/|\.\.\/)collection-scope\.json">[^<]+<\/a>)/,'$1 · <a href="'+prefix+'additions-catalog.json">'+({ko:'추가 문서 목록 · 출처·검증',en:'Added documents · provenance',zh:'新增文档 · 来源',es:'Documentos añadidos · fuentes'}[language])+'</a>');
 await write(file,html);
}
const now=process.env.COLLECTION_TIMESTAMP||new Date().toISOString();assert(!Number.isNaN(Date.parse(now)),'Invalid COLLECTION_TIMESTAMP');registry.updatedAt=now;registry.totalDocuments=registry.documents.length;await write('additions-catalog.json',JSON.stringify(registry,null,2)+'\n');
let sitemap=await read('sitemap.xml');
for(const d of accepted){const location=base+'world-laws/'+d.id+'.html';assert(!sitemap.includes('<loc>'+location+'</loc>'));sitemap=sitemap.replace('</urlset>',`<url><loc>${location}</loc><lastmod>${d.retrievedAt.slice(0,10)}</lastmod></url>\n</urlset>`);}
await write('sitemap.xml',sitemap);
const scope=JSON.parse(await read('collection-scope.json'));scope.additionsCatalog='additions-catalog.json';scope.additionsAsOf=now;
for(const country of [...new Set(accepted.map(d=>d.country))]){
 const documents=registry.documents.filter(d=>d.country===country);let entry=scope.countries.find(d=>d.country===country);
 if(!entry){entry={country,status:'partial'};scope.countries.push(entry);}
 if(entry.status==='research-only')entry.scope='Verified original-language statutory snapshots are listed in the public portal and additions-catalog.json. National corpus incomplete.';
 entry.status='partial';entry.addedDocuments=documents.length;entry.addedDocumentScope='Only individually listed original-language source snapshots in additions-catalog.json; not the full national corpus, not a certified statement of current force.';entry.additionsCatalog='additions-catalog.json';
 if(entry.scope?.includes('공개 법령 본문 없음'))entry.scope='Verified original-language statutory snapshots are listed in the public portal and additions-catalog.json. National corpus incomplete.';
}
await write('collection-scope.json',JSON.stringify(scope,null,2)+'\n');
const publication=JSON.parse(await read('publication.json'));publication.asOf=now.slice(0,10);publication.htmlPages+=accepted.length;publication.sitemapUrls=(sitemap.match(/<loc>/g)||[]).length;publication.additionalForeignDocuments+=accepted.length;publication.publisherTagPages+=accepted.length;publication.lastAdditionAt=now;publication.additionsCatalogDocuments=registry.documents.length;publication.collectionComplete=false;
await write('publication.json',JSON.stringify(publication,null,2)+'\n');
const publisherStatus=JSON.parse(await read('publisher-status.json'));publisherStatus.additionalForeignDocuments=publication.additionalForeignDocuments;await write('publisher-status.json',JSON.stringify(publisherStatus,null,2)+'\n');
console.log(JSON.stringify({added:accepted.length,countries:[...new Set(accepted.map(d=>d.country))],skipped,documents:accepted.map(d=>d.id)},null,2));
