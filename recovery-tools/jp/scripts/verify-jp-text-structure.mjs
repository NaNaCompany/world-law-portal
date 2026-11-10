// Validate only this renderer's finite escaped HTML grammar and complete public receipts.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const decode=s=>s.replaceAll('&#13;','\r').replaceAll('&#x27;',"'").replaceAll('&#39;',"'").replaceAll('&quot;','"').replaceAll('&gt;','>').replaceAll('&lt;','<').replaceAll('&amp;','&');
const tags=new Set(['div','span','ruby','rt','a','strong']);
const attrs=new Set('class data-jp-renderer data-jp data-ja data-jl data-jp-annotation role data-jp-omitted-node data-jp-omission data-jp-subtree-sha256 href rel'.split(' '));
export function verifyJapaneseStructuredArticle(page,d){
 const m=page.match(/<article lang="ja" data-text-sha256="([a-f0-9]{64})">([\s\S]*?)<\/article>/);assert(m,'Structured article missing');assert.equal(m[1],d.textSha256);
 const meta=d.structuredRendering,html=m[2];assert.equal(meta.renderer,'jp-text-structure-v2');assert.equal(hash(html),meta.htmlSha256,'Structured HTML receipt mismatch');
 const stack=[],leaves=[],nodes=[],omissions=[],annotations=[];let offset=0;const tokens=/<(\/?)([a-z]+)([^<>]*)>|([^<]+)/g;
 for(const t of html.matchAll(tokens)){
  assert.equal(t.index,offset,'Invalid unparsed markup');offset+=t[0].length;
  if(t[4]!==undefined){const f=stack.findLast(x=>x.leaf!==undefined);if(f)leaves[f.leaf].text+=decode(t[4]);continue;}
  const closing=t[1],tag=t[2],tail=t[3];assert(tags.has(tag),'Unsupported rendered HTML element');
  if(closing){assert.equal(tail,'');assert.equal(stack.pop()?.tag,tag,'Unbalanced markup');continue;}
  const a={};let consumed='';for(const x of tail.matchAll(/ ([a-z0-9-]+)=(?:"([^"]*)"|'([^']*)')/g)){assert(!Object.hasOwn(a,x[1]));assert(attrs.has(x[1]),'Unsupported HTML attribute');a[x[1]]=decode(x[2]??x[3]);consumed+=x[0];}assert.equal(consumed,tail,'Malformed HTML attributes');
  if(tag==='a'){assert.equal(a.href,d.sourcePage);assert.equal(a.rel,'noopener');}else assert(!Object.hasOwn(a,'href'));
  const frame={tag};if(a['data-jp']!==undefined){const nm=a['data-jp'].match(/^([A-Za-z][A-Za-z0-9]*):(0|[1-9][0-9]*)$/);assert(nm,'Malformed compact source identity');const sourceTag=nm[1],index=Number(nm[2]);assert(Number.isSafeInteger(index)&&index>=0);assert(!['Table','TableRow','TableColumn','ArithFormula','Fig'].includes(sourceTag));assert.equal(tag,({Ruby:'ruby',Rt:'rt'})[sourceTag]||'div');if(a['data-ja'])assert.equal(typeof JSON.parse(a['data-ja']),'object');nodes.push(index);}
  if(a['data-jl']!==undefined){assert.equal(tag,'span');assert.equal(stack.findLast(x=>x.leaf!==undefined),undefined);const index=Number(a['data-jl']);assert(Number.isSafeInteger(index)&&index>=0);frame.leaf=leaves.length;leaves.push({index,text:''});}
  if(a['data-jp-omitted-node']!==undefined)omissions.push({sourceNode:Number(a['data-jp-omitted-node']),tag:a['data-jp-omission'],subtreeSha256:a['data-jp-subtree-sha256']});
  if(a['data-jp-annotation']!==undefined)annotations.push(Number(a['data-jp-annotation']));
  stack.push(frame);
 }
 assert.equal(offset,html.length);assert.equal(stack.length,0);assert.equal(leaves.length,meta.retainedLeafCount);assert.equal(annotations.length,meta.annotationCount);assert.equal(omissions.length,meta.omissionCount);
 assert.deepEqual(omissions,meta.omissions.map(o=>({sourceNode:o.sourceNode,tag:o.tag,subtreeSha256:o.subtreeSha256})));
 const coverage=new Set();for(const [i,l] of leaves.entries()){assert(!i||leaves[i-1].index<l.index);assert(l.index<meta.sourceLeafCount);coverage.add(l.index);}
 for(const o of meta.omissions){assert(['Table','ArithFormula','Fig'].includes(o.tag));assert(Number.isSafeInteger(o.firstSourceLeaf)&&Number.isSafeInteger(o.sourceLeafCount)&&o.firstSourceLeaf>=0&&o.sourceLeafCount>=0);assert(o.firstSourceLeaf+o.sourceLeafCount<=meta.sourceLeafCount);for(let i=o.firstSourceLeaf;i<o.firstSourceLeaf+o.sourceLeafCount;i++){assert(!coverage.has(i),'Overlapping source-leaf coverage');coverage.add(i);}}
 assert.equal(coverage.size,meta.sourceLeafCount,'Unexplained missing source leaf');
 const nodeCoverage=new Set(nodes);assert.equal(nodeCoverage.size,nodes.length);for(const o of meta.omissions)for(let i=o.sourceNode;i<o.sourceNode+o.sourceNodeCount;i++){assert(!nodeCoverage.has(i),'Overlapping source-node coverage');nodeCoverage.add(i);}assert.equal(nodeCoverage.size,meta.sourceNodeCount);assert([...nodeCoverage].every(x=>x>=0&&x<meta.sourceNodeCount));
 const values=leaves.map(x=>x.text),text=values.join('');assert.equal(hash(JSON.stringify(values)),meta.retainedLeafSequenceSha256,'Retained leaf-sequence mismatch');assert.equal(hash(text),d.textSha256);return text;
}
