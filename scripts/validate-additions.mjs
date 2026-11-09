import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {assertPublisherTags} from './publisher-tags.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=p=>fs.readFile(path.join(root,p),'utf8');
const decode=s=>s.replaceAll('&#39;',"'").replaceAll('&quot;','"').replaceAll('&gt;','>').replaceAll('&lt;','<').replaceAll('&amp;','&');
const registry=JSON.parse(await read('additions-catalog.json'));
const sitemap=await read('sitemap.xml');
const indices=await Promise.all(['index.html','en/index.html','zh/index.html','es/index.html'].map(read));
const ids=new Set(),hashes=new Set(),urls=new Set();let characters=0;
for(const d of registry.documents){
 assert(!ids.has(d.id),'Duplicate id');ids.add(d.id);
 assert(!hashes.has(d.textSha256),'Duplicate body');hashes.add(d.textSha256);
 assert(!urls.has(d.sourcePage),'Duplicate official source');urls.add(d.sourcePage);
 const html=await read(d.html);assertPublisherTags(html);
 const body=decode(html.match(/<div class="source-page" data-source-page="1">([\s\S]*?)<\/div><\/article>/)?.[1]||'');
 assert.equal(crypto.createHash('sha256').update(body).digest('hex'),d.textSha256,'Public body differs from verified source text '+d.id);
 assert.equal(body.length,d.characters);characters+=body.length;
 assert(!/[\uFFFD]/.test(body),'Unicode replacement character '+d.id);
 assert(!/<(?:script|iframe|img|object)\b/i.test(body),'Unparsed active content '+d.id);
 assert(html.includes('href="'+d.sourcePage.replaceAll('&','&amp;')+'"'),'Missing official source '+d.id);
 for(const index of indices){
  assert.equal(index.split('world-laws/'+d.id+'.html"').length-1,1,'Missing/duplicate index link '+d.id);
  assert(index.includes('id="country-'+d.country+'"'),'Missing country anchor '+d.country);
 }
 assert.equal(sitemap.split('<loc>https://nanalab.kr/world-law-portal/'+d.html+'</loc>').length-1,1,'Missing/duplicate sitemap entry '+d.id);
 for(const m of html.matchAll(/<a rel="(?:next|prev)" href="([^"]+)"/g))assert((await read('world-laws/'+m[1])).includes('<article '),'Invalid previous/next link');
}
const publication=JSON.parse(await read('publication.json'));
assert.equal(publication.additionsCatalogDocuments,registry.documents.length);
const publisherStatus=JSON.parse(await read('publisher-status.json'));assert.equal(publisherStatus.additionalForeignDocuments,publication.additionalForeignDocuments,'Publisher status count must match publication');
assert.equal(registry.totalDocuments,registry.documents.length);
assert.equal(publication.sitemapUrls,(sitemap.match(/<loc>/g)||[]).length);
console.log(JSON.stringify({passed:true,documents:ids.size,countries:[...new Set(registry.documents.map(d=>d.country))].sort(),sourceTextCharacters:characters,verifiedTextHashes:hashes.size,languageIndices:4,publisherTags:true,sitemap:true},null,2));
