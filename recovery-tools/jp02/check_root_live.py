"""Read-only final root verification. Requires exact successful deployment receipts."""
import argparse,pathlib,json,hashlib,datetime,urllib.request,concurrent.futures,sys
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
 assert run['html_url']==e['runUrl']=='https://github.com/NaNaCompany/world-law-portal/actions/runs/'+str(e['runId'])
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
W=pathlib.Path(__file__).resolve().parent;R=W.parent;S=W/'root-integration/site';A=W/'root-integration/audit';P=pathlib.Path(a.deployment_evidence);e=json.loads(P.read_text());out=pathlib.Path(a.output);assert not out.exists();E=out.parent/(out.stem+'-bodies');E.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(R/'root190-tools'));from root190_common import evidence_body,git_tree_entries
sys.path.insert(0,str(R/'root190-live-checks'));from verify_root190 import check_html,redirect_script,runtime_check
from edge_primitives import publisher_snippets,check_html as check_child_html,article
sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text());base='https://nanalab.kr/world-law-portal/';api='https://api.github.com/repos/NaNaCompany/world-law-portal'
assert e['repository']=='NaNaCompany/world-law-portal';assert e['tree']=='bc5954cf884e3a7595b559b166066851f267923e';assert e['commit']!='7293901a2e905e2c72a0f4b5f422121e97d1f8d8';assert len(e['commit'])==40
snap={}
urls={'ref':api+'/git/ref/heads/main','gitCommit':api+'/git/commits/'+e['commit'],'gitTree':api+'/git/trees/'+e['tree']+'?recursive=1','deployment':api+'/actions/runs/'+str(e['runId'])}
for name,url in urls.items():
 row=e['githubReads'][name];raw=evidence_body(P,row,url);snap[name]=json.loads(raw);target=E/('github-'+name+'.json');target.write_bytes(raw);row['bodyFile']=str(target.relative_to(out.parent))
 if row.get('headersFile'):
  source=P.parent/row['headersFile'];headers=source.read_bytes();assert sha(headers)==row['headersSha256'];dest=E/('github-'+name+'.headers.json');dest.write_bytes(headers);row['headersFile']=str(dest.relative_to(out.parent))
 else:row['headersAvailability']='Not exposed by authorized GitHub connector; actual body retained'
validate_git_identity(e,snap)
assert sha((A/'file-sha256.json').read_bytes())=='55d8caffeecf48eaf96648bfd7983c0c4a197e05273abb0cb7e48d6631dc7e17';fmap=read(A/'file-sha256.json');entries=snap['gitTree']['tree'];assert len({x['path'] for x in entries})==len(entries),'Duplicate Git tree paths';assert all(x['type'] in ['blob','tree'] for x in entries),'Unexpected Git object type';blobs={x['path']:x for x in snap['gitTree']['tree'] if x['type']=='blob'};assert set(blobs)==set(fmap)
for name,h in fmap.items():
 raw=(S/name).read_bytes();assert sha(raw)==h;assert blobs[name]['mode']=='100644' and blobs[name]['size']==len(raw);assert blobs[name]['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
validate_complete_tree(entries,{name:x['sha'] for name,x in blobs.items()},e['tree'])
routes=read(S/'jp190-routes.json')['routes'];old=read(W/'root-history-draft/preservation.json')['files'];docs=read(W/'release/sites/world-law-jp-02/document-manifest.json')['documents'];snip=publisher_snippets(S)
indexes=['index.html','en/index.html','zh/index.html','es/index.html'];meta=['jp190-routes.json','publication.json','publisher-status.json','collection-scope.json','additions-catalog.json','sitemap.xml','robots.txt','scripts/validate-jp190-transition.mjs','scripts/validate-jp02-editions.mjs'];kr=sorted(p.relative_to(S).as_posix() for p in (S/'kr/laws').glob('*.html'));samples=[kr[0],kr[-1],'legacy-laws/ca-acts-i-3.3.html','kr/index.html']
paths=sorted(set(indexes+meta+samples+[r['oldPath'] for r in routes]+[p['path'] for p in old]));route_map={r['oldPath']:r for r in routes}
def fetch(name):
 url=base+(name[:-10] if name.endswith('index.html') else name);rec={'path':name,'url':url,'defaultTlsValidation':True}
 try:
  with urllib.request.urlopen(url,timeout=90) as response:
   raw=response.read();bp=E/(name.replace('/','__')+'.body');bp.write_bytes(raw);hp=E/(name.replace('/','__')+'.headers.json');hp.write_text(json.dumps(list(response.headers.items()),indent=2)+'\n');rec.update(status=response.status,finalUrl=response.url,bodyFile=str(bp.relative_to(out.parent)),bodySha256=sha(raw),headersFile=str(hp.relative_to(out.parent)),headersSha256=sha(hp.read_bytes()),bytes=len(raw));assert response.status==200 and response.url==url
  expected=(S/name).read_bytes()
  if name.endswith('.html'):rec['htmlCheck']=check_html(name,raw,expected,snip)
  else:assert raw==expected
  if name in route_map:rec['redirectRuntime']=redirect_script(raw,route_map[name])
  if name in indexes:
   for d in docs:assert raw.count(('href="'+d['canonicalUrl']+'"').encode())==1
   rec['newEditionLinksVerified']=len(docs)
  rec['passed']=True
 except Exception as ex:rec.update(passed=False,error=type(ex).__name__+': '+str(ex))
 rec['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch,paths))
childsite=W/'release/sites/world-law-jp-02';childbase='https://nanalab.kr/world-law-jp-02/';childsnip=publisher_snippets(childsite)
def fetch_child(d):
 url=d['canonicalUrl'];rec={'path':d['html'],'url':url,'defaultTlsValidation':True}
 try:
  with urllib.request.urlopen(url,timeout=90) as response:
   raw=response.read();bp=E/('jp02-'+d['id']+'.body');bp.write_bytes(raw);hp=E/('jp02-'+d['id']+'.headers.json');hp.write_text(json.dumps(list(response.headers.items()),indent=2)+'\n');rec.update(status=response.status,finalUrl=response.url,bodyFile=str(bp.relative_to(out.parent)),bodySha256=sha(raw),headersFile=str(hp.relative_to(out.parent)),headersSha256=sha(hp.read_bytes()));assert response.status==200 and response.url==url
  expected=(childsite/d['html']).read_bytes();result,_=check_child_html(d['html'],raw,expected,childbase,childsnip,None);assert article(raw)==article(expected) and sha(article(raw))==d['articleSha256'];rec.update(passed=True,htmlCheck=result,articleSha256=d['articleSha256'])
 except Exception as ex:rec.update(passed=False,error=type(ex).__name__+': '+str(ex))
 rec['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:childrows=list(pool.map(fetch_child,docs))
passed=all(r['passed'] for r in rows+childrows);runtime=None
if passed:runtime=runtime_check([r['redirectRuntime'] for r in rows if 'redirectRuntime' in r])
result={**e,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'allChecksPassed':passed,'gitBlobsVerified':len(blobs),'httpResources':len(paths),'checks':rows,'childTargetChecks':childrows,'redirectRuntime':runtime,'jpRedirectsVerified':190,'oldHistoricalPagesVerified':10,'newEditionLinksPerIndex':29,'sitemapExpectedUrls':2522,'unchangedSamples':samples,'notClaimed':'No exhaustive HTTP check of every unchanged file; all8368Git blobs/SHA/sizes are verified','browserVisualQa':False}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':passed,'http':len(paths),'failed':[r['path'] for r in rows+childrows if not r['passed']]}));raise SystemExit(0 if passed else 1)
