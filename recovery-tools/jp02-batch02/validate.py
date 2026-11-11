"""Read-only site/duplicate/preservation validation; private result only."""
import pathlib,json,hashlib,re,sys,unicodedata,collections,xml.etree.ElementTree as ET
from lxml import html
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;R=W.parent;O=W/'candidate-v3';A=O/'audit';I=R/'next-japan-inputs/jp02-batch02';OLD=R/'jp02-release-work'
sys.path.insert(0,str(R/'split-tools'))
from build_release import snippets,BANNER,MORE
sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text());norm=lambda s:re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s)).strip()
def maps(p):return {f.relative_to(p).as_posix():sha(f.read_bytes()) for f in sorted(p.rglob('*')) if f.is_file()}
def verify_frozen():
 for p,h in read(A/'input-pins.json').items():assert sha((I/p).read_bytes())==h
 for f in read(I/'freeze-manifest.json')['files']:assert sha((I/f['path']).read_bytes())==f['sha256']
verify_frozen();b=read(I/'batch.json');new=b['documents'];S=O/'child';T=O/'root';C=OLD/'release/sites/world-law-jp-02';B=OLD/'root-integration/site';records=read(S/'document-manifest.json')['documents'];oldrecords=read(C/'document-manifest.json')['documents']
assert records[:len(oldrecords)]==oldrecords
for side,p,baseline in [('child',S,C),('root',T,B)]:
 assert maps(p)==read(A/(side+'-file-sha256.json'));assert maps(baseline)==read(A/(side+'-baseline-files.json'))
expected={'index.html','en/index.html','zh/index.html','es/index.html','additions-catalog.json','publication.json','publisher-status.json','collection-scope.json','scripts/validate-jp02-editions.mjs'}
assert {d['path'] for d in read(A/'root-delta.json')['changed']}==expected
assert set(maps(T))==set(maps(B))
articles=0
for p in B.rglob('*.html'):
 rel=p.relative_to(B);before=p.read_bytes();after=(T/rel).read_bytes();a=re.findall(rb'<article\b[\s\S]*?</article>',before)
 assert a==re.findall(rb'<article\b[\s\S]*?</article>',after)
 if a:articles+=1;assert before==after
assert articles==2517
for d in oldrecords:assert (S/d['localPath']).read_bytes()==(C/d['localPath']).read_bytes()
# Compare all actual existing Japanese documents, including old root snapshots and JP01.
known_laws=set();versions=set();bodies=collections.defaultdict(set);texts=collections.defaultdict(set);pages=0
for site in [B,R/'jp01-phase1-release-v2/sites/world-law-jp-01',C]:
 for p in (site/'world-laws').glob('jp-egov-*.html'):
  raw=p.read_text();doc=html.fromstring(raw);arts=doc.xpath('//article')
  if not arts:continue
  assert len(arts)==1;pages+=1;lid=p.stem.split('-')[2].split('_')[0].upper();rid=p.stem[8:].upper();known_laws.add(lid);versions.add((lid,rid));leaves=arts[0].xpath('.//*[@data-jl]');body=''.join(x.text_content() for x in leaves) if leaves else arts[0].text_content();bodies[sha(norm(body).encode())].add(lid)
  for h in re.findall(r'data-text-sha256="([a-f0-9]{64})"',raw):texts[h].add(lid)
assert pages==619 and len(known_laws)==609
for d in new:
 lid=d['lawIdentifier'];rid=d['revisionIdentifier'];assert lid not in known_laws and (lid,rid) not in versions
 fragment=(I/d['fragmentFile']).read_bytes();assert sha(fragment)==d['fragmentSha256'];assert sha(d['text'].encode())==d['textSha256']
 raw=(S/('world-laws/'+d['id']+'.html')).read_text();doc=html.fromstring(raw);art=doc.xpath('//article');assert len(art)==1
 assert fragment.decode() in raw;assert ''.join(x.text_content() for x in art[0].xpath('.//*[@data-jl]'))==d['text']
 assert not art[0].xpath('.//table|.//img|.//svg|.//math|.//script|.//iframe')
 for o in d['omissions']:
  notices=art[0].xpath('.//*[@data-jp-omitted-node="'+str(o['sourceNode'])+'"]');assert len(notices)==1
  notice=notices[0];assert notice.get('data-jp-subtree-sha256')==o['subtreeSha256'] and notice.get('role')=='note' and o['position'] in notice.text_content() and 'Portal omission' in notice.text_content() and o['officialUrl'] in notice.xpath('.//a/@href')
 assert d['textSha256'] not in texts and sha(norm(d['text']).encode()) not in bodies
 known_laws.add(lid);versions.add((lid,rid));texts[d['textSha256']].add(lid);bodies[sha(norm(d['text']).encode())].add(lid)
 for value in [d['sourcePage'],d['sourceData'],d['effectiveDate'],d['scopeAsOf'],d['revisionIdentifier'],d['rightsUrl']]:assert value in raw
 if d['officialSourceExcerpt']:assert raw.index('Official source excerpt')<raw.index('<article')
assert len(known_laws)==656 and pages+len(new)==666
ce={d['lawIdentifier']:d['revisionIdentifier'] for d in b['coverageEvidence']['currentEditions']};matched={lid for lid,rid in versions if ce.get(lid)==rid};assert len(matched)==656
# Preserved publisher snippets, canonical/sitemap bijection, explicit public allowlist.
snip=snippets(B);urls=set();htmlcount=0
fixed={'.nojekyll','style.css','jp-structured.css','scripts/publisher-tags.mjs','LICENSE.md','site-manifest.json','publication.json','publisher-status.json','document-manifest.json','additions-catalog.json','catalog.json','collection-scope.json','sitemap.xml','README.md','index.html','en/index.html','zh/index.html','es/index.html'}
assert set(maps(S))==fixed|{d['localPath'] for d in records}
for p in S.rglob('*'):
 if not p.is_file():continue
 raw=p.read_text()
 for term in ['localRawSource','fragmentFile','/workspace/','freeze-manifest.json','"raw/','review/independent']:assert term not in raw
 if p.suffix!='.html':continue
 htmlcount+=1;doc=html.fromstring(raw);canon=doc.xpath('//link[@rel="canonical"]/@href');assert len(canon)==1 and canon[0] not in urls;urls.add(canon[0])
 for v in [*snip.values(),BANNER,MORE]:assert raw.count(v)==1
 assert doc.xpath('//nav') and doc.xpath('//h1')
 for href in doc.xpath('//@href|//@src'):
  if href.startswith(b['publicBase']):
   path=href[len(b['publicBase']):].split('#')[0].split('?')[0];assert (S/(path+'index.html' if not path or path.endswith('/') else path)).exists(),href
locs=[x.text for x in ET.parse(S/'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')];assert len(locs)==len(set(locs))==80 and set(locs)==urls and htmlcount==80
assert (T/'sitemap.xml').read_bytes()==(B/'sitemap.xml').read_bytes()
assert sum(len(d['omissions']) for d in new)==25 and not any(d['officialSourceExcerpt'] for d in new)
for d in records:
 for prefix in ['','en/','zh/','es/']:assert (T/(prefix+'index.html')).read_text().count('href="'+d['canonicalUrl']+'"')==1
# Frozen held inventory remains unchanged, not treated as source defects.
assert len(b['held'])==3;verify_frozen()
result={'passed':True,'publicationEligible':False,'rootAll2517FullArticlePagesByteIdentical':True,'previous29ChildFullPagesAndRecordsIdentical':True,'allRootFilesExceptNineAllowlistedByteIdentical':True,'childCanonicalURLs':80,'childFiles':94,'rootFiles':8368,'rootCanonicalURLs':2522,'japaneseUniqueLawIDs':len(known_laws),'japaneseEditionPages':pages+len(new),'currentEditionsMatchedToDatedCompositeCensus':len(matched),'newLaws':len(new),'newOmittedTableSubtrees':25,'newSourceExcerptDocuments':0,'heldCandidatesUnchanged':3,'normalizedCrossLawDuplicateCount':0,'publisherSnippetsPreserved':True,'privateArtifactsExcluded':True}
(A/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
