#!/usr/bin/env python3
"""Read-only conservation review of a JP190 root draft. No publication approval."""
import argparse,json,re,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
from root190_common import *
from build_root190 import counts,transform_catalogue

def validate(release,source,candidate,child_release,run_node=True):
 root=Path(release);site=root/'sites/world-law-portal';source=Path(source);candidate=Path(candidate);child=Path(child_release)/'sites/world-law-jp-01';build=readjson(root/'audit/build.json');base=readjson(root/'audit/baseline-files.json');errors=[]
 def check(ok,msg):
  if not ok:errors.append(msg)
 source_hash,source_fp=fingerprint(source);current,current_fp=fingerprint(site);child_hash,child_fp=fingerprint(Path(child_release)/'sites');docs=readjson(child/'document-manifest.json')['documents'];selected={d['html'] for d in docs};snip=snippets(source)
 check(source_hash==base['filesSha256'] and source_fp==base['fingerprint'],'Exact original baseline file inventory')
 check(git(source,'rev-parse','HEAD')==build['sourceRootCommit']==base['commit'] and not git(source,'status','--porcelain'),'Clean pinned root source')
 check(git(candidate,'rev-parse','HEAD')==build['candidateCommit'] and not git(candidate,'status','--porcelain'),'Clean pinned corrected candidate')
 check(child_fp==build['childSiteFingerprint']==readjson(Path(child_release)/'audit/freeze-receipt.json')['siteFileManifestSha256'],'Exact frozen child files')
 check(len(docs)==190 and len(selected)==190 and len(child_hash)==208,'Exact child190/208')
 allowed=selected|set(NAV)|{'additions-catalog.json','sitemap.xml','publication.json','publisher-status.json','collection-scope.json'}|{'scripts/'+p for p in MUTATORS+LEGACY_VALIDATORS};added={'jp190-routes.json','scripts/root190-route-guard.mjs','scripts/validate-jp190-transition.mjs'}
 changed={p for p,h in source_hash.items() if current.get(p)!=h};check(changed==allowed and set(current)-set(source_hash)==added and not set(source_hash)-set(current),'Exact changed204/added3 allowlist')
 check(not any(p.is_symlink() for p in site.rglob('*')),'No public symlinks')
 laws={p for p in source_hash if re.fullmatch(r'(?:world-laws|legacy-laws)/[^/]+\.html',p)};kr={p for p in source_hash if p.startswith('kr/laws/') and p.endswith('.html')}
 check(len(laws-selected)==2517 and all(current.get(p)==source_hash[p] for p in laws-selected),'2517 other law whole files unchanged')
 check(len(kr)==5628 and all(current.get(p)==source_hash[p] for p in kr),'5628 Korean redirects unchanged')
 ca='legacy-laws/ca-acts-i-3.3.html';check(current.get(ca)==source_hash.get(ca)=='6577e559acde5af045b4613efb1514efcc27f2b839a9a40090beb66887b5eb31','Exact retained large Canada file')
 redirects={d['html']:redirect_page(d,(source/d['html']).read_text(),snip) for d in docs}
 routes=readjson(site/'jp190-routes.json');route={d['oldPath']:d for d in routes['routes']};check(set(route)==selected and len(routes['routes'])==190,'Exact unique route map')
 for d in docs:
  p=d['html'];row=route.get(p,{});check((site/p).read_bytes()==redirects[p].encode(),'Exact safe redirect '+p);check(row.get('rootRedirectHtmlSha256')==current[p] and row.get('originalRootHtmlSha256')==source_hash[p],'Root old/new receipt '+p)
  check(row.get('canonicalUrl')==d['canonicalUrl']==CHILD+p and row.get('localPath')==p and row.get('repository')=='world-law-jp-01','Fixed child route '+p)
  check(sha((child/p).read_bytes())==row.get('childHtmlSha256')==d['htmlSha256'] and sha(article((child/p).read_bytes().decode()).encode())==row.get('childArticleSha256')==d['articleSha256'],'Child current receipt '+p)
  check(sha((candidate/p).read_bytes())==row.get('correctedSourceHtmlSha256')==d['sourceHtmlSha256'],'Corrected source receipt '+p)
  for k,v in snip.items():check((site/p).read_text().count(v)==1,'Exact publisher '+p+' '+k)
 for p in NAV:check((site/p).read_bytes()==rewrite_index((source/p).read_text(),p,docs).encode(),'Only selected190 index cards change '+p)
 check((site/'sitemap.xml').read_bytes()==rewrite_sitemap((source/'sitemap.xml').read_text(),selected).encode(),'Only190 root sitemap removals')
 expected=transform_catalogue(readjson(source/'additions-catalog.json'),docs,source,redirects)
 for d in expected['documents']:
  if d['html'] in selected:d['originalRootSnapshot']['rootCommit']=build['sourceRootCommit']
 check(readjson(site/'additions-catalog.json')==expected,'Exact190 corrected metadata bridges;166 records unchanged')
 check(routes['counts']==counts() and routes['fullSplitComplete'] is False,'Honest local/aggregate route counts')
 check(all(k not in routes for k in ['published','publicationReady','publicationState','draft']),'Static route metadata is deployment neutral')
 before_scope=readjson(source/'collection-scope.json');after_scope=readjson(site/'collection-scope.json');check([x for x in before_scope['countries'] if x.get('country')!='JP']==[x for x in after_scope['countries'] if x.get('country')!='JP'],'Other country scopes unchanged')
 for p in MUTATORS:
  check((site/'scripts'/p).read_text().endswith((source/'scripts'/p).read_text()),'Original importer code retained '+p)
  result=subprocess.run(['node',str((site/'scripts'/p).resolve())],capture_output=True,text=True);check(result.returncode!=0 and 'disabled before writes' in result.stderr,'Importer fails closed before writes '+p)
 check(fingerprint(site)[0]==current,'Guard tests do not mutate output')
 node=[]
 if run_node:
  for name in ['validate-jp190-transition.mjs','validate-additions.mjs','validate-published.mjs']:
   result=subprocess.run(['node',str((site/'scripts'/name).resolve())],capture_output=True,text=True);check(result.returncode==0,'Node '+name+': '+result.stderr[-1500:]);node.append({'script':name,'passed':result.returncode==0,'output':result.stdout[-3000:],'error':result.stderr[-3000:]})
 total=sum(p.stat().st_size for p in files(site).values());check(total<1_000_000_000,'Conservative1GB public-site ceiling')
 return {'passed':not errors,'phase':'jp190-root-transition','draft':build['draft'],'publicationReady':False,'siteFileManifestSha256':current_fp,'filesSha256':current,'changedFiles':len(changed),'addedFiles':len(added),'counts':counts(),'siteBytes':total,'baselineBytes':sum(p.stat().st_size for p in files(source).values()),'previousSuccessfulBatchBytes':590863983,'belowPreviousSuccessfulBatchByBytes':590863983-total,'timeoutResolutionGuaranteed':False,'nodeChecks':node,'errors':errors,'externalWrites':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--source',required=True);p.add_argument('--candidate-source',required=True);p.add_argument('--child-release',required=True);p.add_argument('--report',required=True);a=p.parse_args();v=validate(a.release,a.source,a.candidate_source,a.child_release);writejson(a.report,v);print(json.dumps({k:v for k,v in v.items() if k not in ['filesSha256','nodeChecks']},indent=2));sys.exit(0 if v['passed'] else 1)
