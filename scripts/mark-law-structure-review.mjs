// Publish explicit review notices without altering statutory source text.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {escapeHtml as esc} from './reuse-provenance.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
assert(process.argv.length===3,'Usage: node scripts/mark-law-structure-review.mjs notices.json');
const input=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const catalogue=JSON.parse(await fs.readFile(path.join(root,'additions-catalog.json'),'utf8'));
const indices=new Map(await Promise.all(['index.html','en/index.html','zh/index.html','es/index.html'].map(async f=>[f,await fs.readFile(path.join(root,f),'utf8')])));
const prepared=[];const seen=new Set();
for(const item of input.documents){
 assert(/^[a-z0-9_-]+$/.test(item.id)&&!seen.has(item.id));seen.add(item.id);
 const d=catalogue.documents.find(d=>d.id===item.id);assert(d,'Unknown document');
 assert.equal(d.sourceSha256,item.sourceSha256);assert.equal(d.textSha256,item.textSha256);
 const oldLabel=d.versionLabel, sourceLabel=d.structuralReview?.sourceVersionLabel||oldLabel;
 const newLabel='구조 검토 중 · Structural review pending. '+sourceLabel;
 d.versionLabel=newLabel;
 d.structuralReview={status:'pending',sourceVersionLabel:sourceLabel,notice:input.notice,findings:item.findings||[],markedAt:input.markedAt};
 const file=path.join(root,d.html);const before=await fs.readFile(file,'utf8');
 let after=before.replace(`<p class="edition">${esc(oldLabel)}</p>`,`<p class="edition">${esc(newLabel)}</p>`);
 assert(after!==before||oldLabel===newLabel,'Edition label missing');
 const note=`<section class="scope structural-review-notice" role="note"><h2>원문 구조 검토 중 · Text structure under review</h2><p>${esc(input.notice)}</p>${(item.findings||[]).length?`<ul>${item.findings.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:''}<p><a href="${esc(d.sourcePage)}" rel="noopener">공식 원문에서 구조·판본 확인 · Check the official source</a></p></section>`;
 const notePattern=/<section class="scope structural-review-notice"[\s\S]*?<\/section>/g;
 after=notePattern.test(after)?after.replace(notePattern,note):after.replace('<article ',note+'<article ');
 assert(after.includes(note));
 assert.equal(before.match(/<article\b[\s\S]*?<\/article>/)?.[0],after.match(/<article\b[\s\S]*?<\/article>/)?.[0],'Legal source body changed');
 prepared.push({file,after});
 for(const [name,html] of indices){
  const pattern=new RegExp('(href="[^"<>]*world-laws/'+item.id+'\\.html"[^>]*>[\\s\\S]*?<p class="edition">)'+esc(oldLabel).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(<\\/p>)','g');
  assert.equal([...html.matchAll(pattern)].length,1,'Index edition mismatch '+name+' '+item.id);
  indices.set(name,html.replace(pattern,(_,a,b)=>a+esc(newLabel)+b));
 }
}
for(const {file,after} of prepared)await fs.writeFile(file,after);
for(const [file,html] of indices)await fs.writeFile(path.join(root,file),html);
await fs.writeFile(path.join(root,'additions-catalog.json'),JSON.stringify(catalogue,null,2)+'\n');
console.log(JSON.stringify({marked:seen.size,legalBodiesChanged:false},null,2));
