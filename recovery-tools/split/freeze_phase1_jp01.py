#!/usr/bin/env python3
"""Freeze reviewed JP190 public files, Git blob IDs and local artifact. No network."""
import argparse,base64,json,sys,tarfile
from pathlib import Path
sys.dont_write_bytecode=True
from build_release import sha,git_blob,readjson,writejson,files_digest,git
from phase1_jp01 import REPO
def freeze(release,source,independent_review,expected_remote_head,recovered_blob=None,recovered_receipt=None):
 root=Path(release).resolve();source=Path(source).resolve();site=root/'sites'/REPO;phase=readjson(root/'audit/phase1.json');validation=readjson(root/'audit/phase1-validation.json');independent=readjson(independent_review);hashes,digest=files_digest(root/'sites');relative={k[len(REPO)+1:]:v for k,v in hashes.items()}
 if any(not k.startswith(REPO+'/') for k in hashes):raise ValueError('Only JP01 may be frozen')
 relative_digest=sha(json.dumps(relative,sort_keys=True,separators=(',',':')).encode())
 if validation.get('passed') is not True or validation.get('siteFileManifestSha256')!=digest or validation.get('phase')!='jp190-only' or validation.get('fullSplitComplete') is not False:raise ValueError('Current successful phase1 validation required')
 if independent.get('passed') is not True or independent.get('siteRelativeFileManifestSha256')!=relative_digest or independent.get('filesSha256')!=relative:raise ValueError('Independent review must cover exact current public files')
 if git(source,'rev-parse','HEAD')!=phase['frozenSourceCommit'] or git(source,'status','--porcelain'):raise ValueError('Frozen clean source changed')
 if len(expected_remote_head)!=40 or any(c not in '0123456789abcdef' for c in expected_remote_head):raise ValueError('Explicit expected remote HEAD required')
 artifact=readjson(root/'audit/phase1-artifact.json');archive=root/artifact['artifact']
 if sha(archive.read_bytes())!=artifact['sha256']:raise ValueError('Packed artifact digest differs')
 with tarfile.open(archive,'r:gz') as tar:
  members=tar.getmembers()
  if len(members)!=len(relative) or any(not m.isfile() or m.name not in relative for m in members) or len({m.name for m in members})!=len(members):raise ValueError('Archive file set differs')
  for m in members:
   if sha(tar.extractfile(m).read())!=relative[m.name]:raise ValueError('Archive bytes differ')
 rows=[]
 for path,d in sorted(relative.items()):
  p=site/path
  if p.is_symlink():raise ValueError('Symlink not permitted')
  raw=p.read_bytes();text=raw.decode('utf-8');utf=len(json.dumps({'repository_full_name':'NaNaCompany/'+REPO,'content':text,'encoding':'utf-8'},ensure_ascii=False,separators=(',',':')).encode());b64=len(json.dumps({'repository_full_name':'NaNaCompany/'+REPO,'content':base64.b64encode(raw).decode(),'encoding':'base64'},separators=(',',':')).encode());rows.append({'path':path,'bytes':len(raw),'sha256':d,'gitBlobSha1':git_blob(raw),'utf8JsonArgumentBytes':utf,'base64JsonArgumentBytes':b64,'reserveBytes':65536,'requestLimitBytes':16777216,'utf8FitsWithReserve':utf+65536<=16777216,'base64FitsWithReserve':b64+65536<=16777216})
 if not all(r['utf8FitsWithReserve'] or r['base64FitsWithReserve'] for r in rows):raise ValueError('No safe transfer representation')
 total=sum(r['bytes'] for r in rows)
 if total>=100_000_000:raise ValueError('100MB operational cap exceeded')
 reuse={'checked':False,'mustNotTransformToMatch':True}
 if recovered_blob:
  recovered=Path(recovered_blob).read_bytes();receipt=readjson(recovered_receipt)
  if sha(recovered)!=receipt.get('sha256') or git_blob(recovered)!=receipt.get('gitBlobSha') or len(recovered)!=receipt.get('bytes'):raise ValueError('Recovered blob receipt differs')
  matching=[r for r in rows if r['sha256']==sha(recovered) and (site/r['path']).read_bytes()==recovered];reuse={'checked':True,'byteIdentical':len(matching)==1,'matchingPaths':[r['path'] for r in matching],'gitBlobSha1':git_blob(recovered),'sha256':sha(recovered),'bytes':len(recovered),'evidence':receipt,'mustNotTransformToMatch':True,'remoteObjectMustBeRecheckedBeforeReuse':True,'noRemoteReadPerformedByFreezer':True}
 manifest={'schemaVersion':1,'phase':'jp190-only','fullSplitComplete':False,'repository':'NaNaCompany/'+REPO,'frozenSourceCommit':phase['frozenSourceCommit'],'frozenSourceTree':git(source,'rev-parse','HEAD^{tree}'),'publicBase':phase.get('publicBase'),'proposedPublicBase':phase.get('proposedPublicBase'),'baseVerified':phase.get('baseVerified'),'siteFileManifestSha256':digest,'siteRelativeFileManifestSha256':relative_digest,'files':rows,'counts':phase['counts'],'siteBytes':total,'operationalLimitBytes':100_000_000,'requestLimitBytes':16777216,'requestReserveBytes':65536,'transportScope':'Exact compact JSON args plus reserved overhead; actual caller envelope must be measured again','expectedRemoteHead':expected_remote_head,'expectedRemoteHeadSource':'Parent-provided checkpoint, not a new remote read','remoteHeadMustBeRecheckedBeforeCAS':True,'externalStateWrites':False,'published':False,'validationSha256':sha((root/'audit/phase1-validation.json').read_bytes()),'independentReviewSha256':sha(Path(independent_review).read_bytes()),'artifact':artifact,'recoveredBlobComparison':reuse,'publicationGates':['Recheck current HEAD, access and base before publication','Verify each blob and complete208-file tree before commit/ref CAS','Verify exact Pages revision,194 canonicals/sitemap,190 articles and publisher snippets','Run browser desktop/mobile QA; hub and other repositories stay unchanged']}
 writejson(root/'audit/public-files-manifest.json',manifest);receipt={'phase':'jp190-only','fullSplitComplete':False,'siteFileManifestSha256':digest,'siteRelativeFileManifestSha256':relative_digest,'publicFilesManifestSha256':sha((root/'audit/public-files-manifest.json').read_bytes()),'artifactSha256':artifact['sha256'],'files':len(rows),'siteBytes':total,'published':False};writejson(root/'audit/freeze-receipt.json',receipt);print(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--source',required=True);p.add_argument('--independent-review',required=True);p.add_argument('--expected-remote-head',required=True);p.add_argument('--recovered-blob');p.add_argument('--recovered-receipt');a=p.parse_args();freeze(a.release,a.source,a.independent_review,a.expected_remote_head,a.recovered_blob,a.recovered_receipt)
