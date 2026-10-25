import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {assertPublisherTags} from './publisher-tags.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=new URL('https://nanalab.kr/world-law-portal/');
const files=new Set();let bytes=0;
async function walk(folder){
 for(const entry of await fs.readdir(folder,{withFileTypes:true})){
  if(['.git','node_modules'].includes(entry.name))continue;
  const file=path.join(folder,entry.name);
  if(entry.isDirectory())await walk(file);
  else{
   const relative=path.relative(root,file).replaceAll('\\','/');files.add(relative);
   assert(!/\.(?:pdf|png|jpe?g|gif|svg|webp|avif|tiff?|bmp|ico)$/i.test(entry.name),'Forbidden image/PDF: '+relative);
   assert(!/^(?:\.env(?:\.|$)|\.openai\/|originals\/|research\/|text-cache\/)/.test(relative),'Private source material: '+relative);
   bytes+=(await fs.stat(file)).size;
  }
 }
}
await walk(root);
assert(bytes<1024**3,'GitHub Pages published site must remain below 1 GiB');
let htmlPages=0,checkedLinks=0;
for(const relative of files){
 if(!relative.endsWith('.html'))continue;
 const html=await fs.readFile(path.join(root,relative),'utf8');htmlPages++;
 assertPublisherTags(html);
 assert(!/<(?:img|svg|picture|object|embed|video|audio|canvas)\b/i.test(html),'Non-text markup: '+relative);
 assert(!/<\/article>}/.test(html),'Unexpected trailing template character: '+relative);
 assert(!/<a\b[^>]*\bdownload(?:[\s=>])|href="[^"\n]*\.pdf(?:[?#"])/i.test(html),'PDF/download link: '+relative);
 assert(html.includes('https://nanalab.kr/apps/'),'Missing More Apps: '+relative);
 const canonical=html.match(/<link rel="canonical" href="([^"]+)"/)?.[1];
 assert(canonical?.startsWith(base.href),'Wrong canonical base: '+relative);
 assert(!canonical.endsWith('/index.html'),'Directory canonical must use a trailing slash: '+relative);
 const expected=new URL(relative,base).href;
 assert(canonical===expected||relative.endsWith('index.html')&&canonical===expected.slice(0,-10),'Wrong canonical route: '+relative);
 for(const [,article] of html.matchAll(/<article\b[^>]*>([\s\S]*?)<\/article>/g)){
  assert(!/<script\b|<[^>]+\son[a-z]+\s*=|(?:href|src)="(?:javascript|data):/i.test(article),'Active original body: '+relative);
 }
 for(const [,href] of html.matchAll(/(?:href|src)="([^"]+)"/g)){
  if(href.startsWith('#'))continue;
  const resolved=new URL(href.replaceAll('&amp;','&'),new URL(relative,base));
  if(resolved.origin!==base.origin||!resolved.pathname.startsWith(base.pathname))continue;
  let target=decodeURIComponent(resolved.pathname.slice(base.pathname.length));
  if(!target||target.endsWith('/'))target+='index.html';
  assert(files.has(target),'Broken local link: '+relative+' -> '+target);checkedLinks++;
 }
}
const sitemap=await fs.readFile(path.join(root,'sitemap.xml'),'utf8');
const locations=[...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>m[1]);
assert.equal(new Set(locations).size,locations.length);
const mapped=new Set();
for(const location of locations){
 assert(location.startsWith(base.href),'Wrong sitemap base');
 assert(!location.endsWith('/index.html'),'Directory sitemap URL must use a trailing slash: '+location);
 let file=decodeURIComponent(new URL(location).pathname.slice(base.pathname.length));
 if(!file||file.endsWith('/'))file+='index.html';
 assert(files.has(file),'Missing sitemap page: '+file);mapped.add(file);
}
assert.equal(mapped.size,htmlPages,'Every HTML page must appear in the root sitemap');
for(const language of ['', 'en/', 'es/', 'zh/'])assert(mapped.has(language+'index.html'));
const scope=JSON.parse(await fs.readFile(path.join(root,'collection-scope.json'),'utf8'));
assert(scope.textOnly===true&&scope.pdfsProvided===false&&scope.imagesProvided===false);
console.log(JSON.stringify({passed:true,htmlPages,sitemapUrls:locations.length,checkedLinks,publisherTagPages:htmlPages,pdfFiles:0,imageFiles:0,totalBytes:bytes,base:base.href},null,2));
