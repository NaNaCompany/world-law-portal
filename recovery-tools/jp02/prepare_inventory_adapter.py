import pathlib
W=pathlib.Path(__file__).resolve().parent;src=W.parent/'route-aware-additions/candidate/scripts/route-aware-inventory.mjs';s=src.read_text()
s=s.replace('export function assertCounts({registry,pub,status,localLaws,htmlPages,canonicalPages,jpRedirects,krRedirects}) {','export function assertCounts({registry,pub,status,localLaws,htmlPages,canonicalPages,jpRedirects,krRedirects,verifiedChildRecords=[]}) {')
s=s.replace("const local=registry.documents.length-external; assert.equal(external,jpRedirects,'Unreviewed external ownership');", """const local=registry.documents.length-external;
 const extra=registry.documents.filter(d=>d.repository&& !['world-law-portal','world-law-jp-01'].includes(d.repository));
 assert.equal(extra.length,verifiedChildRecords.length,'Child inventory required');
 assert.equal(new Set(verifiedChildRecords.map(d=>d.id)).size,verifiedChildRecords.length,'Duplicate child identity');
 for(const d of extra){const v=verifiedChildRecords.find(v=>v.id===d.id);assert(v,'Unknown child record');assert.equal(d.repository,'world-law-jp-02');assert(!d.rootRedirect,'Invented child-only root redirect');assert.equal(d.canonicalUrl,'https://nanalab.kr/world-law-jp-02/'+d.localPath);for(const k of ['country','id','lawIdentifier','revisionIdentifier','sourceSha256','textSha256','articleSha256','htmlSha256','canonicalUrl','repository','localPath'])assert.equal(d[k],v[k],'Child inventory drift '+k);}
 assert.equal(external,jpRedirects+extra.length,'Unreviewed external ownership');
 if(extra.length){assert.equal(pub.externalLawDocuments,external);assert.equal(pub.externalJp02Documents,extra.length);assert.equal(status.externalLawDocuments,external);assert.equal(status.externalJp02Documents,extra.length);}
""")
s=s.replace('export async function inventory(root) {','export async function inventory(root,verifiedChildRecords=[]) {')
s=s.replace('canonicalPages:canonicals.size,jpRedirects,krRedirects});','canonicalPages:canonicals.size,jpRedirects,krRedirects,verifiedChildRecords});')
(W/'root-inventory-adapter.mjs').write_text(s)
