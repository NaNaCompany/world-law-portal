"""Hermetic synthetic tests only. No real source, network, or external writes."""
import argparse,json,subprocess,tempfile,unittest
from pathlib import Path
from build_release import ROOT_BASE,LANGS,sha,write,writejson,page,splitarticle,files_digest,git,valid_public_base,git_blob,assert_build_ready
from phase1_jp01 import build_phase1,rewrite_phase1_shell,validate_jp_manifest,REPO
from validate_phase1_jp01 import validate_phase1
from pack_phase1_jp01 import pack_phase1
from freeze_phase1_jp01 import freeze
from prepare_tree_packages import prepare,pure_tree,INITIAL_TREE,EMPTY_TREE_STEP,OLD_README,EMPTY_BLOB,encode
TEST_ROOT=Path(__file__).resolve().parent/'.selftest'

def fixture(root):
 source=root/'synthetic-source';source.mkdir()
 snip={'publisherHead':''.join('<script data-nana-publisher="'+m+'">/* synthetic inert fixture */</script>' for m in ['adsense','gtm','ga4-loader','ga4-config']),'publisherBodyStart':'<noscript data-nana-publisher="gtm-noscript">synthetic</noscript>','publisherFooter':'<script data-nana-publisher="cloudflare-fallback">/* synthetic */</script>'}
 write(source/'scripts/publisher-tags.mjs','\n'.join('export const '+k+'='+json.dumps(v)+';' for k,v in snip.items()))
 for name,text in [('.nojekyll',''),('style.css','body{}'),('jp-structured.css','.jp-article{}'),('LICENSE.md','Synthetic test data only')]:write(source/name,text)
 for lang,prefix in LANGS.items():write(source/(prefix+'index.html'),'<html><p id="country-JP">Synthetic portal</p></html>')
 records=[];manifest=[]
 for i in range(190):
  local='world-laws/jp-synthetic-'+str(i).zfill(3)+'.html';source_hash=sha(('source'+str(i)).encode());text_hash=sha(('text'+str(i)).encode());official='https://laws.e-gov.go.jp/law/synthetic'+str(i)
  before='<h1>模擬法文'+str(i)+'</h1><p class="scope">Synthetic partial test only. No real law.</p><p>'+source_hash+' '+text_hash+'</p><a class="official-source" href="'+official+'">Official source</a>'
  article='<article id="original-text" lang="ja" data-source-sha256="'+source_hash+'" data-text-sha256="'+text_hash+'"><p id="article-1">模擬テスト '+str(i)+'\r\n文</p></article>'
  prev='https://nanalab.kr/world-law-europe-01/fi-constitution.html' if i==0 else 'jp-synthetic-'+str(i-1).zfill(3)+'.html';nxt='jp-synthetic-'+str((i+1)%190).zfill(3)+'.html';after='<nav class="document-pagination"><a rel="prev" href="'+prev+'">Previous</a><a rel="next" href="'+nxt+'">Next</a></nav><a href="'+ROOT_BASE+'#country-JP">Country</a>'
  text=page('Synthetic '+str(i),'ja',ROOT_BASE+local,before+article+after,snip,ROOT_BASE);write(source/local,text)
  records.append({'id':Path(local).stem,'country':'JP','title':'模擬法文'+str(i),'html':local,'sourcePage':official,'sourceSha256':source_hash,'textSha256':text_hash,'rights':'Synthetic fixture, not real legislation','omissions':{'Table':1,'ArithFormula':1,'Fig':1}});manifest.append({'country':'JP','html':local,'htmlSha256':sha(text.encode()),'articleSha256':sha(article.encode()),'sourceSha256':source_hash,'textSha256':text_hash})
 for local,country in [('world-laws/fi-constitution.html','FI'),('world-laws/us-test.html','US')]:write(source/local,'<!doctype html><html><head><title>Synthetic '+country+'</title><link rel="canonical" href="'+ROOT_BASE+local+'"></head><body><article><p>Mock only</p></article></body></html>')
 writejson(source/'catalog.json',{'documents':[]});writejson(source/'additions-catalog.json',{'documents':records});subprocess.run(['git','init','-q',str(source)],check=True);subprocess.run(['git','-C',str(source),'add','--all'],check=True);subprocess.run(['git','-C',str(source),'-c','user.name=Synthetic Test','-c','user.email=synthetic@example.invalid','commit','-qm','synthetic fixture only'],check=True);commit=git(source,'rev-parse','HEAD');writejson(root/'input.json',{'frozenCommit':commit,'documents':manifest});writejson(root/'proof.json',{'frozenCommit':commit,'jp190StructureRestorationPassed':True,'omissionReceiptsVerified':True,'independentJp190ReviewPassed':True,'evidenceLocation':'SYNTHETIC SELFTEST ONLY, NOT REAL REVIEW'});return source

class UnitTests(unittest.TestCase):
 def test_partial_article_exact(self):self.assertEqual(splitarticle('<head>x</head><article><p>文\r\n字</p></article><footer>x</footer>')[1],'<article><p>文\r\n字</p></article>')
 def test_multiple_articles_reject(self):
  with self.assertRaises(ValueError):splitarticle('<article>a</article><article>b</article>')
 def test_missing_receipts(self):
  with self.assertRaises(ValueError):validate_jp_manifest({'documents':[]})
 def test_full_split_locked(self):
  with self.assertRaises(ValueError):assert_build_ready()
 def test_phase1_default_off(self):
  with self.assertRaises(SystemExit):build_phase1(argparse.Namespace(enable_reviewed_phase1=False))
 def test_invalid_bases(self):
  for s in ['http://nanalab.kr/x/','https://bad@example.com/x/','https://nanalab.kr/x/?a=1','https://nanalab.kr/x/</script>/','https://nanalab.kr/x/../x/']:
   self.assertFalse(valid_public_base(s),s)
 def test_valid_base(self):self.assertTrue(valid_public_base('https://nanalab.kr/world-law-jp-01/'))
 def test_old_initial_tree(self):self.assertEqual(pure_tree({'README.md':OLD_README}),INITIAL_TREE)
 def test_new_initial_tree(self):self.assertEqual(pure_tree({'README.md':OLD_README,'.nojekyll':EMPTY_BLOB}),EMPTY_TREE_STEP)
 def test_unsafe_tree_path(self):
  with self.assertRaises(ValueError):pure_tree({'../x':EMPTY_BLOB})
 def test_jp_link_direct(self):
  p={'world-laws/jp-test.html'};s=rewrite_phase1_shell('<a href="jp-test.html#p">x</a>',ROOT_BASE+'world-laws/jp-x.html','https://nanalab.kr/world-law-jp-01/',p,p);self.assertIn('/world-law-jp-01/world-laws/jp-test.html#p',s)
 def test_four_finnish_fallback(self):
  s='<a href="https://nanalab.kr/world-law-europe-01/fi-constitution.html">x</a>'*4;r=rewrite_phase1_shell(s,ROOT_BASE+'world-laws/jp-x.html','https://nanalab.kr/world-law-jp-01/',set(),{'world-laws/fi-constitution.html'});self.assertEqual(r.count(ROOT_BASE+'world-laws/fi-constitution.html'),4)
 def test_unknown_future_link_reject(self):
  with self.assertRaises(ValueError):rewrite_phase1_shell('<a href="https://nanalab.kr/world-law-europe-01/missing.html">x</a>',ROOT_BASE+'world-laws/jp-x.html','https://nanalab.kr/world-law-jp-01/',set(),set())
 def test_official_links_unchanged(self):
  s='<a href="https://laws.e-gov.go.jp/law/123">x</a>';self.assertEqual(rewrite_phase1_shell(s,ROOT_BASE+'world-laws/jp-x.html','https://nanalab.kr/world-law-jp-01/',set(),set()),s)
 def test_empty_blob_hash(self):self.assertEqual(git_blob(b''),EMPTY_BLOB)

class IntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):TEST_ROOT.mkdir(exist_ok=True)
 def test_mock190_build_validate_pack_freeze_small_transfer_and_negative(self):
  with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
   root=Path(tmp);source=fixture(root);source_before,_=files_digest(source);args=argparse.Namespace(enable_reviewed_phase1=True,source=str(source),output=str(root/'release'),jp_manifest=str(root/'input.json'),expected_manifest_sha256=sha((root/'input.json').read_bytes()),readiness_proof=str(root/'proof.json'),public_base=None,base_proof=None);release=build_phase1(args);v=validate_phase1(release,source);self.assertTrue(v['passed'],v['errors']);self.assertEqual(v['htmlPages'],194);writejson(release/'audit/phase1-validation.json',v);pack_phase1(release)
   files,_=files_digest(release/'sites'/REPO);review={'passed':True,'filesSha256':files,'siteRelativeFileManifestSha256':sha(json.dumps(files,sort_keys=True,separators=(',',':')).encode())};writejson(root/'review.json',review);f=freeze(release,source,root/'review.json','a'*40);self.assertEqual(f['files'],208)
   # Force whole-file blob path with small threshold, never split a file.
   plan=prepare(release,root/'transfer','a'*40,EMPTY_TREE_STEP,250*1024,1024);self.assertGreater(plan['blobRequests'],0);self.assertGreater(plan['treeRequests'],0);self.assertFalse(plan['externalWritesPerformed']);self.assertFalse(plan['historicalComparison']['treeMatches']);self.assertEqual(plan['finalFileCount'],208)
   for step in plan['requests']:
    payload=(root/'transfer'/step['requestPath']).read_bytes();self.assertTrue(payload.isascii());self.assertEqual(sha(payload),step['requestSha256']);obj=json.loads(payload);wire=encode(obj);self.assertEqual(len(wire),step['utf8WireBytes'])
    if step['kind']=='create-tree':self.assertLessEqual(len(wire)+65536,250*1024)
   self.assertEqual(files_digest(source)[0],source_before);self.assertFalse(git(source,'status','--porcelain'))
   bad=dict(review);bad['siteRelativeFileManifestSha256']='0'*64;writejson(root/'review.json',bad)
   with self.assertRaisesRegex(ValueError,'Independent review'):freeze(release,source,root/'review.json','a'*40)
   pagepath=release/'sites'/REPO/'en/index.html';write(pagepath,pagepath.read_bytes()+b'<a href="https://nanalab.kr/world-law-europe-01/missing.html">bad</a>');invalid=validate_phase1(release,source);self.assertFalse(invalid['passed']);self.assertTrue(any('unprovisioned child' in e for e in invalid['errors']))
   with self.assertRaisesRegex(ValueError,'validation'):pack_phase1(release)
   with self.assertRaisesRegex(ValueError,'Frozen file mismatch'):prepare(release,root/'invalid-transfer','a'*40)
if __name__=='__main__':unittest.main()
