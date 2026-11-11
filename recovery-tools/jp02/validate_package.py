"""Local candidate validation/packaging; does not authorize publication."""
import pathlib,json,hashlib,re,xml.etree.ElementTree as E,sys,tarfile
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;R=W.parent;S=W/'release/sites/world-law-jp-02';A=W/'release/audit';sys.path.insert(0,str(R/'split-tools'))
from build_release import snippets,BANNER,MORE
from pack_release import deterministic_archive
sha=lambda b:hashlib.sha256(b).hexdigest()
snip=snippets(R/'root190-prepared/sites/world-law-portal');b=json.loads((R/'next-japan-inputs/jp02-batch01/batch.json').read_text());files=json.loads((A/'file-sha256.json').read_text());urls=[]
for p,h in files.items():
 raw=(S/p).read_bytes();assert sha(raw)==h
 assert not any(x in pathlib.PurePosixPath(p).parts for x in ['audit','raw','receipts','review'])
 if p.endswith('.html'):
  s=raw.decode();u=re.findall(r'<link rel="canonical" href="([^"]+)"',s);assert len(u)==1;urls+=u
  for v in [*snip.values(),BANNER,MORE]:assert s.count(v)==1,(p,'snippet')
 for term in ['localRawSource','fragmentFile','/workspace/','freeze-manifest.json','"raw/']:assert term not in raw.decode(),(p,term)
locs=[x.text for x in E.parse(S/'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')];assert len(locs)==33 and len(set(locs))==33 and set(locs)==set(urls)
for d in b['documents']:
 s=(S/'world-laws'/str(d['id']+'.html')).read_text();fragment=(R/'next-japan-inputs/jp02-batch01'/d['fragmentFile']).read_text();assert fragment in s
 if d.get('lineage'):assert d['lineage']['previousCanonicalUrl'] in s.split('<article')[0]
 if d['officialSourceExcerpt']:assert s.index('Official source excerpt')<s.index(d['versionLabel'])
report={'passed':True,'publicationEligible':False,'pending':'Independent complete-site approval, fresh remote lease and actual publication/live proof','checks':['47 public file hashes','33 canonical URLs equal sitemap','exact publisher/banner/footer snippets','29 frozen fragments retained','10 reciprocal prior-edition links outside article','official excerpt notice before edition explanation','private artifact exclusions'],'fileManifestSha256':sha((A/'file-sha256.json').read_bytes())}
(A/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
target=W/'release/artifacts/world-law-jp-02.tar.gz';deterministic_archive(S,target)
with tarfile.open(target) as t:assert {m.name for m in t.getmembers()}==set(files)
T=W/'release/transfer';T.mkdir(exist_ok=True);records=[]
for n,(p,h) in enumerate(files.items(),1):
 raw=(S/p).read_bytes();args={'repository_full_name':'NaNaCompany/world-law-jp-02','content':raw.decode(),'encoding':'utf-8'};packed=json.dumps(args,ensure_ascii=False,separators=(',',':')).encode();assert len(packed)+65536<=16777216
 name=f'blob-{n:03}.json';(T/name).write_bytes(packed);records.append({'path':p,'requestFile':name,'requestSha256':sha(packed),'expectedGitBlobSha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
(T/'transfer-plan.json').write_text(json.dumps({'state':'local-reviewed-source-candidate-awaiting-final-site-review','externalWrites':False,'expectedHead':'0ca4d7ee9057dc441504a53703789b98bc8f393e','expectedTree':'32b1f4e0044e7c3b81eac5aa47b13a46263299d8','wholeFileBlobRequests':records,'treeRequest':'../audit/tree-request.json','requirements':['Re-read main; halt on lease mismatch','Require final independent complete-site approval and unchanged file manifest','Send each whole-file blob; verify returned Git SHA','Create SHA-only complete tree and verify every approved path/hash','One final commit and one leased main update; no partial main updates','Verify exact workflow and live site before root references']},indent=2)+'\n')
(A/'package.json').write_text(json.dumps({'archiveSha256':sha(target.read_bytes()),'archiveBytes':target.stat().st_size,'publicFiles':len(files),'rawBytes':sum((S/p).stat().st_size for p in files),'transferRequests':len(records),'published':False},indent=2)+'\n')
print(json.dumps(report));print('Packed',target.stat().st_size,'bytes;',len(records),'whole-file blob requests')
