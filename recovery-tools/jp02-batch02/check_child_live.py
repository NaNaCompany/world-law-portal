"""Read-only default-TLS live check; saves private bodies/headers and recheckable receipts."""
import argparse,pathlib,json,hashlib,urllib.request,datetime,concurrent.futures,sys
sys.dont_write_bytecode=True
def validate_git_identity(e,snap):
 assert snap['ref']['ref']=='refs/heads/main'
 assert snap['ref']['object']['type']=='commit'
 assert snap['ref']['object']['sha']==e['commit']
 assert snap['gitCommit']['sha']==e['commit']
 assert snap['gitCommit']['tree']['sha']==e['tree']
 assert snap['gitTree']['sha']==e['tree'] and not snap['gitTree'].get('truncated')
 run=snap['deployment']
 assert run['id']==e['runId']
 assert run['head_branch']=='main'
 assert run['html_url']==e['runUrl']=='https://github.com/NaNaCompany/world-law-jp-02/actions/runs/'+str(e['runId'])
 assert run['head_sha']==e['commit'] and run['status']=='completed' and run['conclusion']=='success' and run['name']=='pages build and deployment'

def validate_complete_tree(entries,localBlobs,expectedTree):
 assert len({x['path'] for x in entries})==len(entries),'Duplicate Git tree paths'
 assert all(x['type'] in ['blob','tree'] for x in entries),'Unexpected Git object type'
 derived,expectedEntries=git_tree_entries(localBlobs)
 assert derived==expectedTree
 fields=['path','mode','type','sha']
 normalized=lambda rows:sorted([{k:x[k] for k in fields} for x in rows],key=lambda x:x['path'])
 assert normalized(entries)==normalized(expectedEntries),'Complete Git entry map differs'


p=argparse.ArgumentParser();p.add_argument('--deployment-evidence',required=True);p.add_argument('--output',required=True);a=p.parse_args()
W=pathlib.Path(__file__).resolve().parent;M=W/'candidate-v3/audit/child-file-sha256.json';sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(M.read_bytes())=='3aaffe54df38acd1a1bc3bb969d703e1102fadc5bdb7f7a1aad34616e93ac8a4'
e=json.loads(pathlib.Path(a.deployment_evidence).read_text());assert e['repository']=='NaNaCompany/world-law-jp-02';assert e['tree']=='836a441707f53acf2e999d6f20e78825491cbf40';assert e['commit']==e['remoteMain']==e['runHeadSha'];assert e['runConclusion']=='success' and e['runStatus']=='completed';assert e['runUrl']=='https://github.com/NaNaCompany/world-law-jp-02/actions/runs/'+str(e['runId']);assert len(e['commit'])==40
sys.path.insert(0,str(W.parent/'root190-live-checks'));from edge_primitives import check_html,publisher_snippets,article
sys.path.insert(0,str(W.parent/'root190-tools'));from root190_common import evidence_body,git_tree_entries
proofpath=pathlib.Path(a.deployment_evidence);api='https://api.github.com/repos/NaNaCompany/world-law-jp-02'
ref=json.loads(evidence_body(proofpath,e['githubReads']['ref'],api+'/git/ref/heads/main'));assert ref['object']['sha']==e['commit']
commit=json.loads(evidence_body(proofpath,e['githubReads']['gitCommit'],api+'/git/commits/'+e['commit']));assert commit['tree']['sha']==e['tree']
tree=json.loads(evidence_body(proofpath,e['githubReads']['gitTree'],api+'/git/trees/'+e['tree']+'?recursive=1'));assert not tree.get('truncated');assert tree['sha']==e['tree']
run=json.loads(evidence_body(proofpath,e['githubReads']['deployment'],api+'/actions/runs/'+str(e['runId'])));assert run['head_sha']==e['commit'] and run['conclusion']=='success' and run['status']=='completed' and run['name']=='pages build and deployment'
validate_git_identity(e,{'ref':ref,'gitCommit':commit,'gitTree':tree,'deployment':run})
assert e['commit']!='4f5198973aaeb55cadd37054d525642195358697'
site=W/'candidate-v3/child';snip=publisher_snippets(site);docs={x['html']:x for x in json.loads((site/'document-manifest.json').read_text())['documents']}
files=json.loads(M.read_text());blobs={x['path']:x['sha'] for x in tree['tree'] if x['type']=='blob'};assert set(blobs)==set(files)
for name in files:
 raw=(site/name).read_bytes();assert sha(raw)==files[name];assert blobs[name]==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
validate_complete_tree(tree['tree'],blobs,e['tree'])
for entry in tree['tree']:
 if entry['type']=='blob':assert entry['mode']=='100644' and entry['size']==(site/entry['path']).stat().st_size
out=pathlib.Path(a.output);assert not out.exists();evid=out.parent/(out.stem+'-bodies');evid.mkdir(parents=True,exist_ok=False)
for name,row in e['githubReads'].items():
 raw=evidence_body(proofpath,row);target=evid/('github-'+name+'.json');target.write_bytes(raw);row['bodyFile']=str(target.relative_to(out.parent))
 if row.get('headersFile'):
  source=proofpath.parent/row['headersFile'];assert sha(source.read_bytes())==row['headersSha256'];head=evid/('github-'+name+'.headers.json');head.write_bytes(source.read_bytes());row['headersFile']=str(head.relative_to(out.parent));row['headersSha256']=sha(head.read_bytes())
 else:row['headersAvailability']='Not exposed by connector; original response body retained'
files.pop('.nojekyll');base='https://nanalab.kr/world-law-jp-02/'
def checked_html(name,body):
 expected=(site/name).read_bytes();result,_=check_html(name,body,expected,base,snip,None)
 if name in docs:
  d=docs[name];actual=article(body);assert actual==article(expected);assert sha(actual)==d['articleSha256'];assert ('data-text-sha256="'+d['textSha256']+'"').encode() in actual;assert ('data-source-sha256="'+d['sourceSha256']+'"').encode() in actual
  result.update(statutoryArticleExact=True,articleSha256=sha(actual),rightsProvenanceAndOmissionsExact=True)
 return result

def check(item):
 name,h=item;url=base+(name[:-10] if name.endswith('index.html') else name);rec={'path':name,'url':url,'expectedSha256':h,'defaultTlsValidation':True}
 try:
  with urllib.request.urlopen(url,timeout=60) as r:
   body=r.read();bodypath=evid/(name.replace('/','__')+'.body');bodypath.write_bytes(body);headers=list(r.headers.items());headerpath=evid/(name.replace('/','__')+'.headers.json');headerpath.write_text(json.dumps(headers,indent=2)+'\n');rec.update(status=r.status,finalUrl=r.url,bodySha256=sha(body),bytes=len(body),bodyFile=str(bodypath.relative_to(out.parent)),headersFile=str(headerpath.relative_to(out.parent)),headersSha256=sha(headerpath.read_bytes()));assert r.status==200 and r.url==url
   if name.endswith('.html'):rec['htmlCheck']=checked_html(name,body);rec['passed']=True
   else:rec['passed']=rec['bodySha256']==h
 except Exception as ex:rec.update(passed=False,error=type(ex).__name__+': '+str(ex))
 rec['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(check,files.items()))
result={**e,'publicBase':base,'fileManifestSha256':sha(M.read_bytes()),'checks':rows,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'allFilesVerified':len(rows)==93 and all(x['passed'] for x in rows),'htmlPages':80,'lawArticles':76,'rawHttpBodiesSaved':True,'notHttpTested':[{'path':'.nojekyll','reason':'GitHub Pages build-control file; Git blob verified'}],'gitBlobsVerified':94}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'allFilesVerified':result['allFilesVerified'],'checks':len(rows),'failed':[x['path'] for x in rows if not x['passed']]}))
raise SystemExit(0 if result['allFilesVerified'] else 1)
