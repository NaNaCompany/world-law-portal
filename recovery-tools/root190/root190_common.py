"""Shared local-only primitives for an explicit JP190 root transition."""
import datetime,hashlib,html,json,os,re,subprocess
from pathlib import Path
from urllib.parse import urljoin,urlsplit
ROOT='https://nanalab.kr/world-law-portal/'
CHILD='https://nanalab.kr/world-law-jp-01/'
REPOSITORY='NaNaCompany/world-law-jp-01'
NAV=['index.html','en/index.html','zh/index.html','es/index.html']
MARKERS=['adsense','gtm','ga4-loader','ga4-config','gtm-noscript','cloudflare-fallback']
MUTATORS=['add-verified-laws.mjs','mark-law-structure-review.mjs','update-law-provenance.mjs']
LEGACY_VALIDATORS=['validate-additions.mjs','validate-published.mjs']
NS='http://www.sitemaps.org/schemas/sitemap/0.9'
BANNER='<!-- NaNa shared book banner --><script defer src="https://nanalab.kr/src_cdn/banner/astra.js"></script><!-- /NaNa shared book banner -->'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def js(value):return json.dumps(value,ensure_ascii=False).replace('<',r'\u003c').replace('>',r'\u003e').replace('&',r'\u0026').replace('\u2028',r'\u2028').replace('\u2029',r'\u2029')
def readjson(p):return json.loads(Path(p).read_bytes())
def write(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode() if isinstance(data,str) else data)
def writejson(p,v):write(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode().strip()
def files(root):return {p.relative_to(root).as_posix():p for p in Path(root).rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def fingerprint(root):
 hashes={p:sha(f.read_bytes()) for p,f in sorted(files(root).items())};return hashes,sha(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode())
def snippets(root):
 text=(Path(root)/'scripts/publisher-tags.mjs').read_text()
 return {k:json.loads(re.search('export const '+k+r'=("(?:[^"\\]|\\.)*");',text).group(1)) for k in ['publisherHead','publisherBodyStart','publisherFooter']}
def article(text):
 m=list(re.finditer(r'<article\b[\s\S]*?</article>',text))
 if len(m)!=1:raise ValueError('Expected one article')
 return m[0].group()
def fresh(value,max_age=3600):
 try:t=datetime.datetime.fromisoformat(value.replace('Z','+00:00'));now=datetime.datetime.now(datetime.timezone.utc);return t.tzinfo is not None and -60<=(now-t).total_seconds()<=max_age
 except Exception:return False

def git_tree_entries(blob_map):
 tree={}
 for path,value in blob_map.items():
  parts=path.split('/')
  if not path or any(x in ['','.','..'] for x in parts):raise ValueError('Unsafe Git path')
  node=tree
  for part in parts[:-1]:node=node.setdefault(part,{})
  if parts[-1] in node:raise ValueError('Duplicate Git path')
  node[parts[-1]]=value
 entries=[]
 def walk(node,prefix=''):
  body=b''
  for name,value in sorted(node.items(),key=lambda item:(item[0]+('/' if isinstance(item[1],dict) else '')).encode()):
   directory=isinstance(value,dict);target=walk(value,prefix+name+'/') if directory else value
   mode='040000' if directory else '100644';entries.append({'path':prefix+name,'mode':mode,'type':'tree' if directory else 'blob','sha':target});body+=(('40000' if directory else mode)+' '+name).encode()+b'\0'+bytes.fromhex(target)
  return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()
 return walk(tree),entries

def evidence_body(proof_path,row,expected_url=None):
 if not isinstance(row,dict) or row.get('status')!=200 or not fresh(row.get('checkedAt','')):raise ValueError('Evidence missing/stale read receipt')
 if expected_url and row.get('url')!=expected_url:raise ValueError('Evidence wrong read URL')
 rel=row.get('bodyFile','');root=Path(proof_path).parent.resolve()
 if not isinstance(rel,str) or not rel or Path(rel).is_absolute() or any(x in ['.','..'] for x in Path(rel).parts):raise ValueError('Unsafe evidence path')
 path=root/rel
 if root not in path.resolve().parents or any(p.is_symlink() for p in [path,*path.parents] if p==root or root in p.parents) or not path.is_file():raise ValueError('Evidence path escape, symlink or missing file')
 raw=path.read_bytes()
 if sha(raw)!=row.get('bodySha256'):raise ValueError('Evidence body hash')
 return raw

def validate_child_proof(proof_path,child_site):
 """Validate actual saved HTTP bodies and GitHub response snapshots, never booleans alone."""
 proof_path=Path(proof_path);p=readjson(proof_path);site=Path(child_site);docs=readjson(site/'document-manifest.json')['documents'];known={CHILD+(n[:-10] if n.endswith('index.html') else n):n for n in files(site) if n.endswith('.html')};rows={d['canonicalUrl']:d for d in docs};expected_files={n:blob(f.read_bytes()) for n,f in files(site).items()};checks=[];expected_tree,expected_entries=git_tree_entries(expected_files)
 def need(ok,msg):
  if not ok:raise ValueError('Child live proof: '+msg)
 need(p.get('schemaVersion')==1 and p.get('repository')==REPOSITORY and p.get('publicBase')==CHILD,'identity/schema')
 need(fresh(p.get('checkedAt','')),'missing/stale checkedAt')
 commit=p.get('commit','');need(bool(re.fullmatch('[a-f0-9]{40}',commit)),'actual commit required')
 ref=p.get('ref',{});co=p.get('gitCommit',{});tree=p.get('gitTree',{});run=p.get('deployment',{})
 need(ref.get('ref')=='refs/heads/main' and ref.get('object',{}).get('sha')==commit,'current main ref')
 need(co.get('sha')==commit and co.get('tree',{}).get('sha')==tree.get('sha') and not tree.get('truncated'),'commit/tree')
 entries=tree.get('tree',[]);need(len(expected_files)==208 and len(entries)==len(expected_entries) and len({x.get('path') for x in entries})==len(entries),'exact208 Git blobs and unique complete tree entries');need(tree.get('sha')==expected_tree,'frozen complete Git tree SHA');need(sorted(({k:x.get(k) for k in ['path','mode','type','sha']} for x in entries),key=lambda x:x['path'])==sorted(expected_entries,key=lambda x:x['path']),'complete Git tree entries/modes/types')
 need(all(x.get('mode')=='100644' for x in tree.get('tree',[]) if x.get('type')=='blob'),'Git modes')
 need(run.get('head_sha')==commit and run.get('head_branch')=='main' and run.get('status')=='completed' and run.get('conclusion')=='success','successful exact-main Pages deployment')
 need(run.get('name')=='pages build and deployment' and str(run.get('id','')).isdigit() and run.get('html_url')=='https://github.com/'+REPOSITORY+'/actions/runs/'+str(run['id']),'verified Pages run identity')
 github=p.get('githubReads',{});api='https://api.github.com/repos/'+REPOSITORY
 for name,snapshot,url in [('ref',ref,api+'/git/ref/heads/main'),('gitCommit',co,api+'/git/commits/'+commit),('gitTree',tree,api+'/git/trees/'+expected_tree+'?recursive=1'),('deployment',run,api+'/actions/runs/'+str(run['id']))]:
  need(json.loads(evidence_body(proof_path,github.get(name,{}),url))==snapshot,'fresh saved GitHub snapshot '+name)
 def body(row):
  need(row.get('status')==200 and row.get('url')==row.get('finalUrl') and row.get('defaultTlsValidation') is True and fresh(row.get('checkedAt','')),'HTTP response status/destination/TLS/freshness')
  return evidence_body(proof_path,row).decode('utf-8')
 pages=p.get('pages',[]);need(len(pages)==194 and len({x.get('url') for x in pages})==194 and {x.get('url') for x in pages}==set(known),'exact194 URLs');snip=snippets(site)
 for row in pages:
  text=body(row);url=row['url'];can=[html.unescape(x) for x in re.findall(r'<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"',text)];need(can==[url],'one self canonical '+url)
  for k,v in snip.items():need(text.count(v)==1,'exact publisher '+k+' '+url)
  for marker in MARKERS:need(text.count('data-nana-publisher="'+marker+'"')==1,'publisher marker '+url)
  need('http-equiv="refresh"' not in text,'unexpected child redirect '+url)
  if url in rows:
   d=rows[url];need(sha(article(text).encode())==d['articleSha256'],'article '+url);need(d['sourceSha256'] in text and d['textSha256'] in text,'source/text pins '+url)
  checks.append(url)
 sm=p.get('sitemap',{});need(sm.get('url')==CHILD+'sitemap.xml','sitemap identity');xml=body(sm);locs=[html.unescape(x) for x in re.findall(r'<loc>([^<]+)</loc>',xml)];need(len(locs)==194 and len(set(locs))==194 and set(locs)==set(known),'exact194 sitemap')
 return {'commit':commit,'tree':tree['sha'],'checkedAt':p['checkedAt'],'runId':run['id'],'runUrl':run['html_url'],'proofSha256':sha(proof_path.read_bytes()),'pages':194,'articles':190}

def redirect_page(record,original,snip):
 target=record['canonicalUrl']
 if target!=CHILD+record['html']:raise ValueError('Unexpected redirect destination')
 lang=re.search(r'<html lang="([^"]+)"',original).group(1);title=html.unescape(re.search(r'<title>([\s\S]*?)</title>',original).group(1));e=lambda x:html.escape(str(x),quote=True)
 # Query and fragment are preserved by JS; static noscript fallback cannot reconstruct them.
 script='const destination=new URL('+js(target)+');destination.search=window.location.search;destination.hash=window.location.hash;const visible=document.getElementById("relocated-law");if(visible)visible.href=destination.href;window.location.replace(destination.href);'
 return '<!doctype html><html lang="'+e(lang)+'"><head>'+BANNER+'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+'</title><link rel="canonical" href="'+e(target)+'"><meta name="nana-jp190-redirect" content="true"><link rel="stylesheet" href="../style.css">'+snip['publisherHead']+'<noscript><meta http-equiv="refresh" content="0;url='+e(target)+'"></noscript></head><body>'+snip['publisherBodyStart']+'<header><a class="brand" href="'+ROOT+'">NaNa Law Library</a></header><main class="law-document"><h1>'+e(record['title'])+'</h1><p>This corrected partial-text snapshot has moved. / 정정된 텍스트 전용 부분 재현 문서가 이동했습니다.</p><p><a id="relocated-law" href="'+e(target)+'">Read the document / 법령 원문 보기</a></p><noscript><p><a href="'+e(target)+'">Continue to the canonical document</a>. The static fallback uses the canonical URL; query and fragment preservation requires JavaScript.</p></noscript><p><a href="'+e(record['sourcePage'])+'" rel="noopener">Official source / 공식 원문</a> · <a href="'+e(record['rightsUrl'])+'" rel="noopener">Reuse terms</a></p><p><a href="'+ROOT+'#country-JP">Country index</a> · <a href="'+ROOT+'">Main index</a></p></main><a class="more-apps" href="https://nanalab.kr/apps/" lang="en">More Apps</a><script id="jp190-redirect">'+script+'</script>'+snip['publisherFooter']+'</body></html>\n'

def rewrite_index(text,path,records):
 mapped={ROOT+r['html']:r for r in records};seen=[]
 pattern=re.compile(r'(<a class="document-link" href=")([^"]+)(" lang="[^"]*">[\s\S]*?</a><p class="edition">)([\s\S]*?)(</p>)')
 def replace(m):
  absolute=urljoin(ROOT+path,html.unescape(m[2]));r=mapped.get(absolute)
  if not r:return m.group()
  seen.append(r['html']);return m[1]+html.escape(r['canonicalUrl'],quote=True)+m[3]+html.escape(r['versionLabel'],quote=True)+m[5]
 result=pattern.sub(replace,text)
 if len(seen)!=190 or set(seen)!={r['html'] for r in records}:raise ValueError('Expected each selected190 index card exactly once: '+path)
 return result

def rewrite_sitemap(text,paths):
 targets={ROOT+p for p in paths};removed=[]
 def replace(m):
  loc=re.search(r'<loc>([^<]+)</loc>',m.group())
  if loc and html.unescape(loc[1]) in targets:removed.append(html.unescape(loc[1]));return ''
  return m.group()
 result=re.sub(r'<url>[\s\S]*?</url>',replace,text)
 if len(removed)!=190 or set(removed)!=targets:raise ValueError('Exactly190 canonical URLs must be removed')
 return result
