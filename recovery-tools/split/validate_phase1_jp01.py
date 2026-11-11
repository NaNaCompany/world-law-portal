#!/usr/bin/env python3
"""Recovered JP190-only local validator. No live/deployment claim."""
import argparse,html,json,re,sys
from pathlib import Path
from urllib.parse import urljoin,urlsplit,unquote
from xml.etree import ElementTree as ET
sys.dont_write_bytecode=True
from build_release import ROOT_BASE,LANGS,TAG,ATTR,PUBLISHERS,SITEMAP_NS,sha,readjson,writejson,splitarticle,snippets,canonical,files_digest,git
from phase1_jp01 import REPO,KR_EXISTING,rewrite_phase1_shell

def public_metadata_has_no_deployment_claims(value):
 # Static build metadata cannot certify a current deployment state.
 if isinstance(value,dict):return not ({'publicationState','published'} & set(value)) and all(public_metadata_has_no_deployment_claims(v) for v in value.values())
 if isinstance(value,list):return all(public_metadata_has_no_deployment_claims(v) for v in value)
 return True

def validate_phase1(release,source=None):
 root=Path(release);site=root/'sites'/REPO;audit=root/'audit';errors=[]
 def check(ok,message):
  if not ok:errors.append(message)
 phase=readjson(audit/'phase1.json');meta=readjson(site/'site-manifest.json');base=meta.get('publicBase') or meta.get('proposedPublicBase');records=readjson(site/'document-manifest.json')['documents'];paths={r['html'] for r in records};known=set(phase['allKnownSourceLawPaths']);receipts={r['path']:r for r in readjson(audit/'article-conservation.json')};source=Path(source) if source else None;snip=snippets(source if source else site)
 check(set(p.name for p in (root/'sites').iterdir() if p.is_dir())=={REPO},'Phase1 must stage JP01 only; no hub or other child')
 check(meta.get('phase')=='jp190-only' and meta.get('fullSplitComplete') is False and meta.get('hubUnchanged') is True and meta.get('oldPortalRedirectsGenerated') is False,'Explicit partial-phase status')
 check(len(records)==190 and len(paths)==190 and all(r.get('country')=='JP' for r in records),'Exactly190 JP records')
 files={p.relative_to(site).as_posix():p for p in site.rglob('*') if p.is_file()};total=sum(p.stat().st_size for p in files.values());check(total<100_000_000,'JP01 operational100MB cap');check('.nojekyll' in files and 'CNAME' not in files,'Nojekyll/no domain changes');check(not any(p.is_symlink() for p in site.rglob('*')),'No symlinks in published tree')
 for local in files:
  if local.endswith('.json'):check(public_metadata_has_no_deployment_claims(readjson(files[local])),local+': static public metadata must not claim current deployment status')
 html_files={p for p in files if p.endswith('.html')};check(len(html_files)==194 and html_files==paths|{p+'index.html' for p in LANGS.values()},'Exactly190 laws plus four indexes');ids={};links=[];canonicals=set()
 for local in sorted(html_files):
  text=files[local].read_bytes().decode();matches=re.findall(r'<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"',text);expected=canonical(base,local);check(len(matches)==1 and html.unescape(matches[0])==expected,local+': unique self canonical');canonicals.add(expected);check('http-equiv="refresh"' not in text,local+': child must not be a redirect')
  for marker in PUBLISHERS:check(text.count('data-nana-publisher="'+marker+'"')==1,local+': publisher '+marker)
  for key,value in snip.items():check(value in text,local+': exact publisher snippet '+key)
  check(text.count('https://nanalab.kr/src_cdn/banner/astra.js')==1 and 'https://nanalab.kr/apps/' in text,local+': banner/More Apps');check(not re.search(r'<(?:img|svg|picture|object|embed|video|audio|canvas|table|math)\b',text,re.I),local+': excluded non-text media/table/math')
  ids[local]={html.unescape(v) for pair in re.findall(r'\bid=(?:"([^"]*)"|\'([^\']*)\')',text) for v in pair if v}
  for tag in TAG.findall(text):
   for key,quote,value in ATTR.findall(tag):
    value=html.unescape(value)
    if value.startswith(('mailto:','tel:','javascript:','data:')):continue
    resolved=urljoin(base+local,value);links.append((local,resolved));parts=urlsplit(resolved)
    if parts.hostname in {'nanalab.kr','nanacompany.github.io'} and parts.path.startswith('/world-law-'):
     repo=parts.path.strip('/').split('/')[0];check(repo in {REPO,'world-law-portal'}|KR_EXISTING,local+': unprovisioned child link '+resolved)
 fallback_urls=set()
 for local,url in links:
  if url.startswith(base):
   parts=urlsplit(url);target=unquote(parts.path[len(urlsplit(base).path):]);target=target+'index.html' if not target or target.endswith('/') else target;check(target in files,local+': missing local target '+target)
   if parts.fragment and target in ids:check(unquote(parts.fragment) in ids[target],local+': missing local fragment')
  elif url.startswith(ROOT_BASE):
   parts=urlsplit(url);relative=unquote(parts.path[len(urlsplit(ROOT_BASE).path):]);fallback_urls.add(url)
   if relative.startswith(('world-laws/','legacy-laws/')):check(relative in known and relative not in paths,local+': invalid/non-direct JP portal fallback '+relative)
   if source:
    target=relative+'index.html' if not relative or relative.endswith('/') else relative;check((source/target).is_file(),local+': portal fallback absent from source '+target)
    if parts.fragment and (source/target).is_file():check(re.search(r'\bid=["\']'+re.escape(unquote(parts.fragment))+r'["\']',(source/target).read_text()) is not None,local+': portal fallback fragment absent')
 xml=ET.fromstring((site/'sitemap.xml').read_bytes());check(xml.tag=='{'+SITEMAP_NS+'}urlset','Own sitemap urlset required');locs=[x.text for x in xml.findall('{'+SITEMAP_NS+'}url/{'+SITEMAP_NS+'}loc')];check(len(locs)==194 and len(set(locs))==194 and set(locs)==canonicals,'Exact194 self-canonical sitemap URLs')
 for r in records:
  local=r['html'];raw=files[local].read_bytes();text=raw.decode();before,body,after=splitarticle(text);receipt=receipts.get(local,{})
  check(bool(r.get('htmlSha256')) and sha(raw)==r.get('htmlSha256')==receipt.get('outputHtmlSha256'),local+': HTML receipt');check(bool(r.get('articleSha256')) and sha(body.encode())==r.get('articleSha256')==receipt.get('articleSha256'),local+': article receipt');check(r['sourceSha256'] in text and r['textSha256'] in text and (r['sourcePage'] in text or html.escape(r['sourcePage'],quote=True) in text),local+': provenance/source link');check(not re.search(r'<script\b|<[^>]+\son[a-z]+\s*=',body,re.I),local+': active article')
  for lang,prefix in LANGS.items():check(html.escape(base+local,quote=True) in files[prefix+'index.html'].read_text(),local+': locale card '+lang)
  if source:
   original=(source/local).read_bytes().decode();a,b,c=splitarticle(original);expected=rewrite_phase1_shell(a,ROOT_BASE+local,base,paths,known)+b+rewrite_phase1_shell(c,ROOT_BASE+local,base,paths,known);check(text==expected and body==b,local+': exact source article/shell conservation');check(sha(original.encode())==receipt.get('sourceHtmlSha256'),local+': reviewed corrected source HTML')
 check(readjson(site/'additions-catalog.json')['documents']==records,'Exact local provenance subset');check(meta['counts']['localCanonicalPages']==194 and meta['counts']['localLawDocuments']==190 and meta['counts']['localRedirectPages']==0,'Phase1 local counts');check(all(x['utf8FitsWithReserve'] or x['base64FitsWithReserve'] for x in readjson(audit/'transport-measurements.json')),'Every unchanged file must fit a measured transfer representation')
 if source:check(git(source,'rev-parse','HEAD')==meta['frozenSourceCommit'] and not git(source,'status','--porcelain'),'Frozen clean source HEAD')
 _,digest=files_digest(root/'sites')
 return {'passed':not errors,'phase':'jp190-only','fullSplitComplete':False,'localLawDocuments':190,'canonicalPages':194,'htmlPages':len(html_files),'bytes':total,'siteFileManifestSha256':digest,'portalFallbackUrlsForExternalHttpVerification':sorted(fallback_urls),'graphLinksChecked':len(links),'errors':errors,'liveDeploymentClaim':False,'externalGatesPassed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--source');p.add_argument('--report',required=True);a=p.parse_args();result=validate_phase1(a.release,a.source);writejson(a.report,result);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['passed'] else 1)
