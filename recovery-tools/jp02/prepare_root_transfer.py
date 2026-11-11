"""Prepare a bounded complete-file delta packet locally; no network writes."""
import pathlib,json,hashlib,sys
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;R=W.parent;S=W/'root-integration/site';A=W/'root-integration/audit';T=W/'root-transfer';sys.path.insert(0,str(R/'root190-tools'));from root190_common import git_tree_entries,evidence_body,fresh
sys.path.insert(0,str(R/'root190-live-checks'));from edge_primitives import check_html,publisher_snippets,article
sha=lambda b:hashlib.sha256(b).hexdigest();blob=lambda b:hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();read=lambda p:json.loads(p.read_text())
def pin(p,h):assert sha(p.read_bytes())==h,str(p)
def js(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
pin(A/'file-sha256.json','55d8caffeecf48eaf96648bfd7983c0c4a197e05273abb0cb7e48d6631dc7e17');pin(A/'change-manifest.json','db44e3c97e86e3e0f3538e725b913ef4d06fa0aa4568f3893f6df184076658b9');pin(R/'jp02-independent-review/root-review.json','4332ebf8b4d234bb8ff578e63a0aa25e820813923961521efa34ab7b0dfb4d84')
review=read(R/'jp02-independent-review/root-review.json');assert review['passed'];expected=review['expectedFinalGitTree'];assert expected=='bc5954cf884e3a7595b559b166066851f267923e'
ref=read(T/'root-main-receipt.json');snapshot=json.loads(evidence_body(T/'root-main-receipt.json',ref,'https://api.github.com/repos/NaNaCompany/world-law-portal/git/ref/heads/main'));assert snapshot['object']['sha']=='7293901a2e905e2c72a0f4b5f422121e97d1f8d8'
P=W/'live-proof-01/live-proof.json';pin(P,'458320451f040e5b99c45317c054144a0f7976ce4efd7d35a8c6459206f3afc5');proof=read(P);assert fresh(proof['checkedAt']);assert proof['commit']=='4f5198973aaeb55cadd37054d525642195358697';assert proof['tree']=='76d32a376af0a67bf4f3d1f244427b88baba201f';assert len(proof['checks'])==46
child=W/'release/sites/world-law-jp-02';snips=publisher_snippets(child);docs={d['html']:d for d in read(child/'document-manifest.json')['documents']};fmap=read(W/'release/audit/file-sha256.json');assert {r['path'] for r in proof['checks']}==set(fmap)-{'.nojekyll'}
for row in proof['checks']:
 raw=evidence_body(P,row);assert row['defaultTlsValidation'] and row['url']==row['finalUrl'];original=(child/row['path']).read_bytes()
 if row['path'].endswith('.html'):
  check_html(row['path'],raw,original,proof['publicBase'],snips,None)
  if row['path'] in docs:assert article(raw)==article(original) and sha(article(raw))==docs[row['path']]['articleSha256']
 else:assert raw==original
for name,row in proof['githubReads'].items():evidence_body(P,row)
sizes=read(W/'live-proof-01/git-blob-sizes.json');assert sizes['passed'] and sizes['files']==47
actual=read(A/'file-sha256.json');baseline=read(A/'baseline-files.json');change=read(A/'change-manifest.json');blobmap={}
for p,h in actual.items():
 raw=(S/p).read_bytes();assert sha(raw)==h;blobmap[p]=blob(raw)
tree,_=git_tree_entries(blobmap);assert tree==expected
paths=sorted([x['path'] for x in change['changed']]+change['added']);assert len(paths)==20 and len(change['changed'])==19 and len(change['added'])==1
files=[]
for i,p in enumerate(paths,1):
 raw=(S/p).read_bytes();args={'repository_full_name':'NaNaCompany/world-law-portal','content':raw.decode(),'encoding':'utf-8'};payload=json.dumps(args,ensure_ascii=False,separators=(',',':')).encode();assert len(payload)+65536<=16777216
 name=f'blob-{i:02}.json';assert not (T/name).exists();(T/name).write_bytes(payload);files.append({'path':p,'requestFile':name,'requestSha256':sha(payload),'gitBlobSha':blobmap[p],'sha256':sha(raw),'rawBytes':len(raw),'requestBytes':len(payload),'reserveBytes':65536,'operation':'modify' if p in baseline else 'add'})
tree_request={'repository_full_name':'NaNaCompany/world-law-portal','base_tree_sha':'d06e62db7178112f0be493b3c41e033171217938','tree_elements':[{'path':p,'mode':'100644','type':'blob','sha':blobmap[p]} for p in paths]};wire=json.dumps(tree_request,separators=(',',':')).encode();assert len(wire)+65536<=512000;(T/'tree-request.json').write_bytes(wire)
js(T/'transfer-plan.json',{'state':'prepared-awaiting-independent-transfer-and-child-live-gate-review','publicationEligible':False,'expectedParent':snapshot['object']['sha'],'expectedBaseTree':tree_request['base_tree_sha'],'expectedFinalTree':expected,'finalFileCount':len(actual),'changedExistingFiles':19,'addedFiles':1,'unchangedFiles':8348,'deletions':0,'files':files,'treeRequestFile':'tree-request.json','treeRequestSha256':sha(wire),'treeRequestBytes':len(wire),'treeReserveBytes':65536,'childProofSha256':sha(P.read_bytes()),'childProofScope':'47Git blobs including.nojekyll;46servedHTTP resources excluding.nojekyll','rootReviewSha256':sha((R/'jp02-independent-review/root-review.json').read_bytes()),'rootFileManifestSha256':sha((A/'file-sha256.json').read_bytes()),'rootMainReceiptSha256':sha((T/'root-main-receipt.json').read_bytes()),'mainUpdateRule':'Re-read main immediately before one complete commit and compare-and-swap; no partial main updates','externalWrites':False})
print(json.dumps({'files':len(files),'rawBytes':sum(x['rawBytes'] for x in files),'maxRequestBytes':max(x['requestBytes'] for x in files),'treeBytes':len(wire),'expectedTree':expected,'publicationEligible':False}))
