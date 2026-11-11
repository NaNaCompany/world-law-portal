#!/usr/bin/env python3
"""Prepare only the JP190 partial root transition in a new local directory.
No remote writes. Missing verified live child proof permits an explicit draft only.
"""
import argparse,copy,datetime,html,json,re,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
from root190_common import *
HERE=Path(__file__).resolve().parent

def counts():return {'localLawDocuments':2517,'externalJp190Documents':190,'aggregateLawDocuments':2707,'localAdditionsCatalogDocuments':166,'externalAdditionsCatalogDocuments':190,'aggregateAdditionsCatalogDocuments':356,'localCanonicalPages':2522,'localHtmlPages':8340,'localRedirectPages':5818,'koreanRedirects':5628,'localNavigationPages':5}
def transform_catalogue(old,child_records,source,redirects):
 out=copy.deepcopy(old);mapped={r['id']:r for r in child_records};changed=[]
 for i,prior in enumerate(out['documents']):
  if prior['id'] not in mapped:continue
  d=copy.deepcopy(mapped[prior['id']]);path=prior['html'];original=(Path(source)/path).read_bytes()
  for key in ['id','html','sourceSha256','sourcePage','sourceData','rights','rightsUrl','lawIdentifier','revisionIdentifier','retrievedAt']:
   if d.get(key)!=prior.get(key):raise ValueError('Original source identity/rights changed: '+key+' '+prior['id'])
  if d['structuredRendering']['originalTextSha256']!=prior['textSha256']:raise ValueError('Original/retained text bridge differs')
  if d['repository']!='world-law-jp-01' or d['localPath']!=path or d['canonicalUrl']!=CHILD+path:raise ValueError('Canonical namespace mismatch')
  d['htmlRole']='relative canonical-child path; the same legacy root path is a redirect'
  d['htmlHashScope']='canonical child HTML; rootRedirect.htmlSha256 describes the root redirect'
  d['rootRedirect']={'html':path,'canonicalUrl':d['canonicalUrl'],'htmlSha256':sha(redirects[path].encode()),'type':'html-client-redirect','javascriptPreservesQueryAndFragment':True,'staticFallbackUsesCanonicalUrl':True}
  d['originalRootSnapshot']={'rootCommit':None,'htmlSha256':sha(original),'textSha256':prior['textSha256'],'sourceSha256':prior['sourceSha256']}
  out['documents'][i]=d;changed.append(d['id'])
 if len(changed)!=190 or len(set(changed))!=190:raise ValueError('Exactly selected190 catalogue entries required')
 out.update(totalDocuments=356,localDocuments=166,externalDocuments=190,aggregateDocuments=356,complete=False,routingManifest='jp190-routes.json')
 return out

def build(args):
 source=Path(args.source).resolve();candidate=Path(args.candidate_source).resolve();child_release=Path(args.child_release).resolve();child=child_release/'sites/world-law-jp-01';out=Path(args.output).resolve()
 if out.exists() or any(out==p or p in out.parents or out in p.parents for p in [source,candidate,child_release]):raise ValueError('New isolated output outside every protected input required')
 if any(p.is_symlink() for p in source.rglob('*') if '.git' not in p.relative_to(source).parts):raise ValueError('Source symlinks forbidden')
 commit=git(source,'rev-parse','HEAD')
 if commit!=args.expected_source_commit or git(source,'status','--porcelain'):raise ValueError('Exact clean root baseline required')
 child_manifest=readjson(child/'document-manifest.json');docs=child_manifest['documents'];child_meta=readjson(child/'site-manifest.json');freeze=readjson(child_release/'audit/freeze-receipt.json')
 if git(candidate,'rev-parse','HEAD')!=child_meta['frozenSourceCommit'] or git(candidate,'status','--porcelain'):raise ValueError('Clean corrected candidate changed')
 child_hashes={('world-law-jp-01/'+p):sha(f.read_bytes()) for p,f in files(child).items()};child_fp=sha(json.dumps(child_hashes,sort_keys=True,separators=(',',':')).encode())
 if child_fp!=freeze['siteFileManifestSha256'] or len(child_hashes)!=208 or len(docs)!=190 or len({d['html'] for d in docs})!=190:raise ValueError('Exact reviewed child208 freeze required')
 v=readjson(child_release/'audit/phase1-validation.json');ind=readjson(args.child_independent_review)
 if not v['passed'] or v['siteFileManifestSha256']!=child_fp or not ind['passed'] or ind['filesSha256']!={p:sha(f.read_bytes()) for p,f in files(child).items()}:raise ValueError('Current local and independent child reviews required')
 old=readjson(source/'additions-catalog.json');old_jp={d['html'] for d in old['documents'] if d.get('country')=='JP'}
 if old_jp!={d['html'] for d in docs} or len(old['documents'])!=356:raise ValueError('Baseline JP190 set differs')
 for d in docs:
  if sha((child/d['html']).read_bytes())!=d['htmlSha256'] or sha(article((child/d['html']).read_text()).encode())!=d['articleSha256'] or sha((candidate/d['html']).read_bytes())!=d['sourceHtmlSha256']:raise ValueError('Child/candidate receipt differs '+d['id'])
 source_hashes,source_fp=fingerprint(source);sf=files(source);laws={p for p in sf if re.fullmatch(r'(?:world-laws|legacy-laws)/[^/]+\.html',p)};kr={p for p in sf if p.startswith('kr/laws/') and p.endswith('.html')}
 if len(sf)!=8364 or len(laws)!=2707 or len(kr)!=5628 or sum(p.endswith('.html') for p in sf)!=8340:raise ValueError('Unexpected frozen baseline counts')
 live=None
 if args.live_proof:live=validate_child_proof(args.live_proof,child)
 elif not args.draft:raise ValueError('Verified actual child live proof required; otherwise explicit --draft only')
 if args.draft and live:raise ValueError('Choose explicit draft without live proof or verified prepared output')
 out.mkdir(parents=True);audit=out/'audit';audit.mkdir();site=out/'sites/world-law-portal';shutil.copytree(source,site,ignore=shutil.ignore_patterns('.git'))
 snip=snippets(source);redirects={d['html']:redirect_page(d,(source/d['html']).read_text(),snip) for d in docs}
 for p,t in redirects.items():write(site/p,t)
 for p in NAV:write(site/p,rewrite_index((source/p).read_text(),p,docs))
 registry=transform_catalogue(old,docs,source,redirects)
 for d in registry['documents']:
  if d['id'] in {r['id'] for r in docs}:d['originalRootSnapshot']['rootCommit']=commit
 writejson(site/'additions-catalog.json',registry);write(site/'sitemap.xml',rewrite_sitemap((source/'sitemap.xml').read_text(),set(redirects)))
 common=counts();state='draft-not-ready' if not live else 'prepared-root-cutover-not-published';route_rows=[];old_by_id={d['id']:d for d in old['documents']}
 for d in docs:
  prior=old_by_id[d['id']];route_rows.append({'id':d['id'],'oldPath':d['html'],'oldUrl':ROOT+d['html'],'repository':'world-law-jp-01','localPath':d['localPath'],'canonicalUrl':d['canonicalUrl'],'rootRedirectHtmlSha256':sha(redirects[d['html']].encode()),'originalRootHtmlSha256':source_hashes[d['html']],'originalTextSha256':prior['textSha256'],'correctedTextSha256':d['textSha256'],'sourceSha256':d['sourceSha256'],'correctedSourceHtmlSha256':d['sourceHtmlSha256'],'childHtmlSha256':d['htmlSha256'],'childArticleSha256':d['articleSha256']})
 public={'schemaVersion':1,'phase':'jp190-root-transition','fullSplitComplete':False,'routingMode':'partial-jp190-external','sourceRootCommit':commit,'childRepository':'world-law-jp-01','childBase':CHILD,'childSiteFileManifestSha256':child_fp,'childDeploymentReceipt':live,'counts':common,'redirectType':'HTML JavaScript/noscript/visible-link redirect; not an HTTP301','queryFragmentPolicy':'JavaScript preserves browser location.search and location.hash; static no-script fallback uses the canonical URL','routes':route_rows};writejson(site/'jp190-routes.json',public)
 pub=readjson(source/'publication.json');pub.update(sitemapUrls=2522,additionalForeignDocuments=2483,aggregateAdditionalForeignDocuments=2673,**common);pub.update(jp190CanonicalRepository='world-law-jp-01',jp190CanonicalSitemap=CHILD+'sitemap.xml',routingManifest='jp190-routes.json',jp190RoutingMode='partial-jp190-external',jp190ChildDeploymentReceipt=live,fullSplitComplete=False,collectionComplete=False);writejson(site/'publication.json',pub)
 ps=readjson(source/'publisher-status.json');ps.update(additionalForeignDocuments=2483,aggregateAdditionalForeignDocuments=2673,localLawDocuments=2517,aggregateLawDocuments=2707,localPublisherTagPages=8340,localKoreanLawDocuments=0,koreanDocumentsScope='aggregate inventory, locally represented by unchanged redirects',jp190RedirectPages=190,routingManifest='jp190-routes.json',fullSplitComplete=False);writejson(site/'publisher-status.json',ps)
 scope=readjson(source/'collection-scope.json');jp=[x for x in scope['countries'] if x.get('country')=='JP']
 if len(jp)!=1:raise ValueError('Expected one existing JP scope row')
 jp[0].update(status='partial',localLawDocuments=400,externalLawDocuments=190,aggregateLawDocuments=590,localAddedDocuments=0,externalAddedDocuments=190,addedDocumentScope='The selected190 corrected partial-text snapshots have canonical pages in world-law-jp-01. The other400 existing Japanese snapshots retain their portal URLs. No complete/current-law certification.',canonicalRepositories=['world-law-portal','world-law-jp-01'],routingManifest='jp190-routes.json');scope['jp190Transition']={'routingMode':'partial-jp190-external','routingManifest':'jp190-routes.json','fullSplitComplete':False};writejson(site/'collection-scope.json',scope)
 for p in ['root190-route-guard.mjs','validate-jp190-transition.mjs']:write(site/'scripts'/p,(HERE/p).read_bytes())
 for p in MUTATORS:
  prefix="import {blockLegacyMutation} from './root190-route-guard.mjs';\nawait blockLegacyMutation(new URL('../jp190-routes.json',import.meta.url),"+json.dumps(p)+");\n";write(site/'scripts'/p,prefix+(source/'scripts'/p).read_text())
 for p in LEGACY_VALIDATORS:
  prefix="import {isPartialRoot} from './root190-route-guard.mjs';\nif(await isPartialRoot(new URL('../jp190-routes.json',import.meta.url))){const module=await import('./validate-jp190-transition.mjs');await module.validateRoot190();process.exit(0);}\n";write(site/'scripts'/p,prefix+(source/'scripts'/p).read_text())
 allowed=set(redirects)|set(NAV)|{'additions-catalog.json','sitemap.xml','publication.json','publisher-status.json','collection-scope.json'}|{'scripts/'+p for p in MUTATORS+LEGACY_VALIDATORS};added={'jp190-routes.json','scripts/root190-route-guard.mjs','scripts/validate-jp190-transition.mjs'}
 output_hashes,output_fp=fingerprint(site);changed={p for p,h in source_hashes.items() if output_hashes.get(p)!=h}
 if changed!=allowed or set(output_hashes)-set(source_hashes)!=added or set(source_hashes)-set(output_hashes):raise ValueError('Output modifications exceed exact allowlist')
 writejson(audit/'baseline-files.json',{'commit':commit,'fingerprint':source_fp,'filesSha256':source_hashes,'bytes':sum(p.stat().st_size for p in sf.values())});writejson(audit/'build.json',{'draft':not bool(live),'publicationReady':False,'sourceRootCommit':commit,'candidateCommit':child_meta['frozenSourceCommit'],'childReleasePath':str(child_release),'childIndependentReviewPath':str(Path(args.child_independent_review).resolve()),'childIndependentReviewSha256':sha(Path(args.child_independent_review).read_bytes()),'childSiteFingerprint':child_fp,'childLiveProofPath':str(Path(args.live_proof).resolve()) if args.live_proof else None,'rootSiteFingerprint':output_fp,'allowedChanged':sorted(allowed),'allowedAdded':sorted(added),'counts':common,'originalBytes':596151193,'afterRemovingOld190BodiesBeforeRedirects':557102905,'actualRootBytes':sum(p.stat().st_size for p in files(site).values()),'timeoutResolutionGuaranteed':False,'fullSplit75MBTargetMet':False,'externalWrites':False})
 if fingerprint(source)[0]!=source_hashes or git(source,'status','--porcelain') or git(candidate,'status','--porcelain'):raise ValueError('Protected source changed')
 print(json.dumps({'draft':not bool(live),'publicationReady':False,'output':str(out),'rootFingerprint':output_fp,'changedFiles':len(changed),'addedFiles':len(added),'bytes':sum(p.stat().st_size for p in files(site).values()),'externalWrites':False},indent=2));return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--candidate-source',required=True);p.add_argument('--child-release',required=True);p.add_argument('--child-independent-review',required=True);p.add_argument('--expected-source-commit',required=True);p.add_argument('--output',required=True);p.add_argument('--draft',action='store_true');p.add_argument('--live-proof');build(p.parse_args())
