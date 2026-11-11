#!/usr/bin/env python3
"""EXPLICIT PARTIAL phase1: corrected JP190 only; full-split guard is untouched.
Default is paused. Creates no portal redirects and never modifies the source/remote.
Recovered from conversation; historical byte identity is not certified.
"""
import argparse,collections,html,json,re,shutil,sys
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
sys.dont_write_bytecode=True
from build_release import ROOT_BASE,HUB,LANGS,NAV,TAG,ATTR,DISCLAIMERS,sha,git,readjson,write,writejson,splitarticle,snippets,page,sitemap,valid_public_base,git_blob
REPO='world-law-jp-01'
KR_EXISTING={'world-law-kr-acts','world-law-kr-orders'}
def validate_jp_manifest(manifest):
 records=manifest.get('documents',[]);paths=[r.get('html') or r.get('oldPath') for r in records]
 if len(records)!=190 or len(set(paths))!=190:raise ValueError('Exactly190 unique reviewed JP paths required')
 for r,path in zip(records,paths):
  if r.get('country')!='JP' or not isinstance(path,str) or not path.startswith('world-laws/jp-') or not path.endswith('.html') or '..' in path.split('/'):raise ValueError('Unexpected phase1 law path/country')
  for field in ['htmlSha256','articleSha256','sourceSha256','textSha256']:
   if not re.fullmatch(r'[a-f0-9]{64}',r.get(field,'')):raise ValueError('Missing reviewed '+field+' for '+path)
 return records

def law_path_from_url(url,known_paths):
 p=urlsplit(url)
 if p.hostname not in {'nanalab.kr','nanacompany.github.io'}:return None
 chunks=p.path.strip('/').split('/')
 if not chunks or not chunks[0].startswith('world-law-'):return None
 relative='/'.join(chunks[1:])
 if relative in known_paths:return relative
 if len(chunks)==2 and relative.endswith('.html'):
  matches=[path for path in known_paths if path.rsplit('/',1)[-1]==relative]
  if len(matches)==1:return matches[0]
 return None

def rewrite_phase1_shell(text,old_url,base,jp_paths,known_paths,fallbacks=None):
 fallbacks=fallbacks if fallbacks is not None else set()
 def rewrite_tag(match):
  def rewrite_attr(m):
   key,quote,value=m.groups();raw=html.unescape(value)
   if raw.startswith(('#','mailto:','tel:','javascript:','data:')):return m.group()
   absolute=urljoin(old_url,raw);parts=urlsplit(absolute);pure=urlunsplit((parts.scheme,parts.netloc,parts.path,'',''));law=law_path_from_url(pure,known_paths)
   if law:
    new=base+law if law in jp_paths else ROOT_BASE+law
    if law not in jp_paths:fallbacks.add(new)
   elif pure.startswith(ROOT_BASE):
    local=pure[len(ROOT_BASE):]
    if local.startswith(('world-laws/','legacy-laws/')):raise ValueError('Unknown portal law target: '+pure)
    if local in ['style.css','jp-structured.css']:new=base+local
    elif local in ['', 'index.html','en/','en/index.html','zh/','zh/index.html','es/','es/index.html'] and not parts.fragment:new=base+(local[:-10] if local.endswith('index.html') else local)
    else:new=pure;fallbacks.add(new)
   elif parts.hostname in {'nanalab.kr','nanacompany.github.io'} and parts.path.startswith('/world-law-'):
    chunks=parts.path.strip('/').split('/');repo=chunks[0];remainder='/'.join(chunks[1:])
    if repo in KR_EXISTING:return m.group()
    if remainder in ['', 'index.html','en','en/','en/index.html','zh','zh/','zh/index.html','es','es/','es/index.html']:
     prefix=next((lang+'/' for lang in ['en','zh','es'] if remainder.startswith(lang)),'');new=base+prefix if repo==REPO else ROOT_BASE+prefix;fallbacks.add(new) if repo!=REPO else None
    elif remainder in ['style.css','jp-structured.css'] and repo==REPO:new=base+remainder
    elif remainder in ['catalog.json','additions-catalog.json','collection-scope.json','sitemap.xml']:new=ROOT_BASE+remainder;fallbacks.add(new)
    else:raise ValueError('Unprovisioned/unknown child target in phase1: '+pure)
   else:return m.group()
   new+=('?' + parts.query if parts.query else '')+('#'+parts.fragment if parts.fragment else '')
   return key+'='+quote+html.escape(new,quote=True)+quote
  return ATTR.sub(rewrite_attr,match.group())
 return TAG.sub(rewrite_tag,text)

def assert_phase1_ready(source,manifest,proof):
 source=Path(source);records=validate_jp_manifest(manifest);commit=manifest.get('frozenCommit')
 if not commit or git(source,'rev-parse','HEAD')!=commit or git(source,'status','--porcelain'):raise ValueError('Corrected source must be frozen and clean at manifest HEAD')
 if proof.get('frozenCommit')!=commit or any(proof.get(k) is not True for k in ['jp190StructureRestorationPassed','omissionReceiptsVerified','independentJp190ReviewPassed']) or not proof.get('evidenceLocation'):raise ValueError('Corrected JP190 structure/omission/independent proof required; counts alone do not certify it')
 additions=readjson(source/'additions-catalog.json');by_path={r['html']:r for r in additions['documents']};jp_actual={r['html'] for r in additions['documents'] if r.get('country')=='JP'};reviewed={r.get('html') or r.get('oldPath') for r in records}
 if reviewed!=jp_actual:raise ValueError('Reviewed set must equal the actual190 JP catalogue entries; no substitution')
 for r in records:
  path=r.get('html') or r['oldPath'];raw=(source/path).read_bytes();text=raw.decode();body=splitarticle(text)[1];catalog=by_path[path]
  if sha(raw)!=r['htmlSha256'] or sha(body.encode())!=r['articleSha256']:raise ValueError('Reviewed corrected HTML/article differs: '+path)
  if catalog.get('sourceSha256')!=r['sourceSha256'] or catalog.get('textSha256')!=r['textSha256'] or r['sourceSha256'] not in text or r['textSha256'] not in text:raise ValueError('Source/text provenance differs: '+path)
 for asset in ['.nojekyll','style.css','jp-structured.css','scripts/publisher-tags.mjs','LICENSE.md']:
  if not (source/asset).is_file():raise ValueError('Required unchanged asset missing: '+asset)
 return commit,by_path

def build_phase1(args):
 if not args.enable_reviewed_phase1:raise SystemExit('PAUSED: phase1 JP190 preparation only. Corrected frozen source,190-record SHA-pinned manifest and independent readiness proof are required.')
 source=Path(args.source).resolve();output=Path(args.output).resolve()
 if output.exists() or output==source or source in output.parents:raise ValueError('New output outside source required')
 if sha(Path(args.jp_manifest).read_bytes())!=args.expected_manifest_sha256:raise ValueError('Reviewed JP190 manifest SHA256 pin required')
 manifest=readjson(args.jp_manifest);proof=readjson(args.readiness_proof);commit,catalogs=assert_phase1_ready(source,manifest,proof);base=args.public_base or 'https://nanalab.kr/world-law-jp-01/'
 if not valid_public_base(base):raise ValueError('Invalid proposed public base')
 verified=False
 if args.base_proof:
  bootstrap=readjson(args.base_proof)
  if bootstrap.get('repository')!='NaNaCompany/'+REPO or bootstrap.get('publicBase')!=base or bootstrap.get('httpBootstrapVerified') is not True or not all(bootstrap.get(k) for k in ['checkedAt','commit','successfulRunId','proofUrl']):raise ValueError('Actual JP01 bootstrap evidence required')
  verified=True
 records=validate_jp_manifest(manifest);jp_paths={r.get('html') or r['oldPath'] for r in records};known_paths={p.relative_to(source).as_posix() for folder in ['world-laws','legacy-laws'] for p in (source/folder).glob('*.html')}
 if any(p.is_symlink() for p in source.rglob('*') if '.git' not in p.parts):raise ValueError('Unexpected source symlink')
 output.mkdir(parents=True);audit=output/'audit';audit.mkdir();site=output/'sites'/REPO;site.mkdir(parents=True);snip=snippets(source);fallbacks=set();output_records=[];conservation=[];transport=[]
 for asset in ['.nojekyll','style.css','jp-structured.css','scripts/publisher-tags.mjs','LICENSE.md']:write(site/asset,(source/asset).read_bytes())
 for r in records:
  local=r.get('html') or r['oldPath'];raw=(source/local).read_bytes();old=raw.decode();before,article,after=splitarticle(old);result=rewrite_phase1_shell(before,ROOT_BASE+local,base,jp_paths,known_paths,fallbacks)+article+rewrite_phase1_shell(after,ROOT_BASE+local,base,jp_paths,known_paths,fallbacks)
  if splitarticle(result)[1]!=article:raise ValueError('Article mutation')
  write(site/local,result);canonical=base+local;rec=dict(catalogs[local]);rec.update(repository=REPO,localPath=local,oldPath=local,oldUrls=[ROOT_BASE+local],canonicalUrl=canonical if verified else None,proposedCanonicalUrl=None if verified else canonical,htmlSha256=sha(result.encode()),sourceHtmlSha256=sha(raw),articleSha256=r['articleSha256'],phase='jp190-only',fullSplitComplete=False);output_records.append(rec)
  conservation.append({'path':local,'sourceHtmlSha256':sha(raw),'outputHtmlSha256':sha(result.encode()),'articleSha256':r['articleSha256'],'sourceSha256':r['sourceSha256'],'textSha256':r['textSha256'],'canonicalUrl':canonical})
  import base64
  utf={'content':result,'encoding':'utf-8','repository_full_name':'NaNaCompany/'+REPO};b64={'content':base64.b64encode(result.encode()).decode(),'encoding':'base64','repository_full_name':'NaNaCompany/'+REPO};u=len(json.dumps(utf,ensure_ascii=False,separators=(',',':')).encode());b=len(json.dumps(b64,separators=(',',':')).encode())
  transport.append({'path':local,'rawBytes':len(result.encode()),'utf8JsonArgumentBytes':u,'base64JsonArgumentBytes':b,'reserveBytes':65536,'limitBytes':16777216,'utf8FitsWithReserve':u+65536<=16777216,'base64FitsWithReserve':b+65536<=16777216})
 for lang,prefix in LANGS.items():
  heading,disclaimer=DISCLAIMERS[lang];content='<h1>'+heading+' · JP190</h1><p class="scope">'+disclaimer+'</p><p>Phase1:190 corrected Japanese documents only. The full multi-repository migration is not complete. Other laws remain at the <a href="'+ROOT_BASE+prefix+'">existing portal</a>.</p><section id="country-JP"><h2 id="JP">JP ·190</h2><ul>'
  content+=''.join('<li><a class="document-link" href="'+html.escape(base+r['html'],quote=True)+'">'+html.escape(r['title'])+'</a> · <a class="official-source" href="'+html.escape(r['sourcePage'],quote=True)+'">Official source</a></li>' for r in output_records)
  content+='</ul></section><footer><a href="'+base+'additions-catalog.json">JP190 provenance</a> · <a href="'+base+'sitemap.xml">Sitemap</a> · <a href="'+base+'collection-scope.json">Partial scope</a></footer>';write(site/(prefix+'index.html'),page(heading+' · JP190',lang,base+prefix,content,snip,base))
 metadata={'schemaVersion':2,'phase':'jp190-only','fullSplitComplete':False,'frozenSourceCommit':commit,'repository':REPO,'publicBase':base if verified else None,'proposedPublicBase':None if verified else base,'baseVerified':verified,'reviewedJpManifestSha256':args.expected_manifest_sha256,'counts':{'localLawDocuments':190,'localNavigationPages':4,'localCanonicalPages':194,'localRedirectPages':0,'localHtmlPages':194,'observedSourceLawDocuments':len(known_paths),'observedSourceAdditionsCatalogDocuments':len(readjson(source/'additions-catalog.json')['documents'])},'operationalLimitBytes':100_000_000,'hubUnchanged':True,'oldPortalRedirectsGenerated':False,'interfaceLanguages':list(LANGS),'sitemap':'sitemap.xml'}
 writejson(site/'site-manifest.json',metadata);writejson(site/'publication.json',metadata);writejson(site/'publisher-status.json',metadata)
 writejson(site/'document-manifest.json',{'schemaVersion':2,'phase':'jp190-only','fullSplitComplete':False,'totalDocuments':190,'documents':output_records})
 writejson(site/'additions-catalog.json',{'schemaVersion':2,'complete':False,'phase':'jp190-only','scope':'local190-record subset; other additions remain at portal','totalDocuments':190,'documents':output_records})
 writejson(site/'catalog.json',{'schemaVersion':2,'complete':False,'scope':'local initial-catalogue subset','totalDocuments':0,'totalFiles':0,'documents':[]})
 writejson(site/'collection-scope.json',{'schemaVersion':2,'phase':'jp190-only','fullSplitComplete':False,'complete':False,'textOnly':True,'imagesProvided':False,'pdfsProvided':False,'countries':[{'country':'JP','status':'partial','localDocuments':190,'scope':'Exactly the independently reviewed corrected190 original-language snapshots. Not a complete or certified-current national corpus.'}],'restOfLibrary':ROOT_BASE})
 write(site/'sitemap.xml',sitemap([base+p for p in LANGS.values()]+[base+r['html'] for r in output_records]))
 write(site/'README.md','# JP190 phase1\n\nOnly the corrected190-document Japanese subset is staged here. Full migration is NOT complete. Other laws remain at the existing portal. No portal file or redirect was changed by this build.\n')
 audit_metadata=dict(metadata);audit_metadata['publicationState']='local-phase1-candidate-not-published'
 writejson(audit/'phase1.json',{**audit_metadata,'sourcePath':str(source),'allKnownSourceLawPaths':sorted(known_paths),'fallbackPortalUrls':sorted(fallbacks),'externalStateWrites':False,'toolRecoveryStatus':'new-explicit-phase1-tool; not a recovered historical artifact'})
 writejson(audit/'article-conservation.json',conservation);writejson(audit/'transport-measurements.json',transport);writejson(audit/'reviewed-jp190-manifest.json',manifest);writejson(audit/'readiness-proof.json',proof)
 if args.base_proof:writejson(audit/'bootstrap-proof.json',bootstrap)
 if git(source,'rev-parse','HEAD')!=commit or git(source,'status','--porcelain'):raise ValueError('Source changed concurrently')
 print(json.dumps({'phase':'jp190-only','fullSplitComplete':False,'built':True,'published':False,'output':str(output)}));return output

def parser():
 p=argparse.ArgumentParser();p.add_argument('--enable-reviewed-phase1',action='store_true');p.add_argument('--source');p.add_argument('--jp-manifest');p.add_argument('--expected-manifest-sha256');p.add_argument('--readiness-proof');p.add_argument('--public-base');p.add_argument('--base-proof');p.add_argument('--output');return p
if __name__=='__main__':build_phase1(parser().parse_args())
