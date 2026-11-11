"""Synthetic-only tests; no network or real legislation writes."""
import copy,datetime,json,re,shutil,subprocess,tempfile,unittest
from pathlib import Path
from root190_common import *
from check_root190_gates import check_gates
HERE=Path(__file__).resolve().parent

def fixture(root):
 site=root/'child';site.mkdir();now=datetime.datetime.now(datetime.timezone.utc).isoformat();snip={'publisherHead':''.join('<script data-nana-publisher="'+m+'">/* mock */</script>' for m in MARKERS[:4]),'publisherBodyStart':'<noscript data-nana-publisher="gtm-noscript">mock</noscript>','publisherFooter':'<script data-nana-publisher="cloudflare-fallback">/* mock */</script>'};write(site/'scripts/publisher-tags.mjs','\n'.join('export const '+k+'='+json.dumps(v)+';' for k,v in snip.items()));docs=[]
 def page(url,body):return '<html><head><link rel="canonical" href="'+url+'">'+snip['publisherHead']+'</head><body>'+snip['publisherBodyStart']+body+snip['publisherFooter']+'</body></html>'
 for i in range(190):
  p='world-laws/jp-test-'+str(i)+'.html';body='<article><p>Synthetic '+str(i)+' '+'a'*64+' '+'b'*64+'</p></article>';write(site/p,page(CHILD+p,body));docs.append({'html':p,'canonicalUrl':CHILD+p,'articleSha256':sha(body.encode()),'sourceSha256':'a'*64,'textSha256':'b'*64})
 for p in NAV:write(site/p,page(CHILD+p[:-10],'<p>Synthetic index</p>'))
 writejson(site/'document-manifest.json',{'documents':docs})
 for p in ['style.css','.nojekyll']+['extra'+str(i)+'.txt' for i in range(10)]:write(site/p,'synthetic')
 assert len(files(site))==208
 tree,entries=git_tree_entries({p:blob(f.read_bytes()) for p,f in files(site).items()});commit='c'*40;proof={'schemaVersion':1,'repository':REPOSITORY,'publicBase':CHILD,'checkedAt':now,'commit':commit,'ref':{'ref':'refs/heads/main','object':{'sha':commit,'type':'commit'}},'gitCommit':{'sha':commit,'tree':{'sha':tree}},'gitTree':{'sha':tree,'truncated':False,'tree':entries},'deployment':{'name':'pages build and deployment','head_sha':commit,'head_branch':'main','status':'completed','conclusion':'success','id':123,'html_url':'https://github.com/'+REPOSITORY+'/actions/runs/123'}};path=root/'proof.json'
 def receipt(name,url,raw):
  rel='evidence/'+name;write(root/rel,raw);return {'url':url,'finalUrl':url,'status':200,'defaultTlsValidation':True,'checkedAt':now,'bodyFile':rel,'bodySha256':sha(raw)}
 api='https://api.github.com/repos/'+REPOSITORY;ends={'ref':'/git/ref/heads/main','gitCommit':'/git/commits/'+commit,'gitTree':'/git/trees/'+tree+'?recursive=1','deployment':'/actions/runs/123'};proof['githubReads']={k:receipt(k+'.json',api+ends[k],json.dumps(proof[k]).encode()) for k in ends};proof['pages']=[receipt('page'+str(i)+'.html',CHILD+(p[:-10] if p.endswith('index.html') else p),f.read_bytes()) for i,(p,f) in enumerate(files(site).items()) if p.endswith('.html')];xml='<urlset>'+''.join('<url><loc>'+x['url']+'</loc></url>' for x in proof['pages'])+'</urlset>';proof['sitemap']=receipt('sitemap.xml',CHILD+'sitemap.xml',xml.encode());writejson(path,proof);return site,path,proof

class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):(HERE/'.selftest').mkdir(exist_ok=True)
 def test_git_tree_matches_standard_git(self):
  with tempfile.TemporaryDirectory(dir=HERE/'.selftest') as tmp:
   bare=Path(tmp)/'bare';subprocess.run(['git','init','--bare','-q',str(bare)],check=True);h='53a2e95fdda864473cc87ca7d95f37929aa688f1';tree,_=git_tree_entries({'README.md':h});actual=subprocess.check_output(['git','--git-dir',str(bare),'mktree','--missing'],input=('100644 blob '+h+'\tREADME.md\n').encode()).decode().strip();self.assertEqual(tree,actual);self.assertEqual(tree,'c4b02b26d2f47273d696c7ab7ed7aa46d7b87b15')
 def test_script_escaping(self):
  v='</script><script>&\u2028\u2029';s=js(v);self.assertNotIn('<',s);self.assertNotIn('>',s);self.assertNotIn('&',s);self.assertEqual(json.loads(s),v)
 def test_redirect_query_fragment(self):
  d={'html':'world-laws/jp-test.html','canonicalUrl':CHILD+'world-laws/jp-test.html','title':'Test','sourcePage':'https://example.invalid/source','rightsUrl':'https://example.invalid/rights'};s=redirect_page(d,'<html lang="ja"><title>Test</title>',{'publisherHead':'','publisherBodyStart':'','publisherFooter':''});script=re.search(r'<script id="jp190-redirect">([\s\S]*?)</script>',s)[1];h='const out={};const document={getElementById:()=>out};const window={location:{search:"?x=a%26b",hash:"#article-1",replace:u=>{if(u!=="'+d['canonicalUrl']+'?x=a%26b#article-1"||out.href!==u)throw Error(u)}}};'+script;subprocess.run(['node','-e',h],check=True);self.assertIn('<noscript><meta http-equiv="refresh"',s);self.assertIn('static fallback uses the canonical URL',s);self.assertNotIn('HTTP301',s)
 def test_importer_guard_absent_and_malformed(self):
  with tempfile.TemporaryDirectory(dir=HERE/'.selftest') as tmp:
   marker=Path(tmp)/'marker.json';h="import {blockLegacyMutation} from "+json.dumps((HERE/'root190-route-guard.mjs').as_uri())+";await blockLegacyMutation("+json.dumps(str(marker))+",'mock');";self.assertEqual(subprocess.run(['node','--input-type=module','-e',h],capture_output=True).returncode,0);write(marker,'not json');r=subprocess.run(['node','--input-type=module','-e',h],capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('disabled before writes',r.stderr)
 def test_live_proof_positive_and_negative(self):
  with tempfile.TemporaryDirectory(dir=HERE/'.selftest') as tmp:
   root=Path(tmp);site,path,p=fixture(root);self.assertEqual(validate_child_proof(path,site)['pages'],194);cases=[]
   for field in ['checkedAt']:
    q=copy.deepcopy(p);q[field]='2000-01-01T00:00:00Z';cases.append(q)
   q=copy.deepcopy(p);q['githubReads']['ref']['checkedAt']='2000-01-01T00:00:00Z';cases.append(q)
   q=copy.deepcopy(p);q['gitTree']['sha']='0'*40;q['gitCommit']['tree']['sha']='0'*40;cases.append(q)
   q=copy.deepcopy(p);q['gitTree']['tree'].append({'path':'submodule','mode':'160000','type':'commit','sha':'a'*40});cases.append(q)
   q=copy.deepcopy(p);q['gitTree']['tree'].append(q['gitTree']['tree'][0]);cases.append(q)
   q=copy.deepcopy(p);q['ref']['object']['sha']='d'*40;cases.append(q)
   q=copy.deepcopy(p);q['deployment']['head_sha']='d'*40;cases.append(q)
   q=copy.deepcopy(p);q['pages'].pop();cases.append(q)
   q=copy.deepcopy(p);q['pages'][0]['status']=404;cases.append(q)
   q=copy.deepcopy(p);q['pages'][0]['bodySha256']='0'*64;cases.append(q)
   q=copy.deepcopy(p);q['pages'][0]['bodyFile']='../outside.html';cases.append(q)
   for q in cases:
    writejson(path,q)
    with self.assertRaises(ValueError):validate_child_proof(path,site)
   (root/'linked').symlink_to(root/'evidence',target_is_directory=True);q=copy.deepcopy(p);q['pages'][0]['bodyFile']='linked/'+Path(q['pages'][0]['bodyFile']).name;writejson(path,q)
   with self.assertRaises(ValueError):validate_child_proof(path,site)
   writejson(path,p);body=root/p['pages'][0]['bodyFile'];write(body,body.read_bytes()+b'corrupt')
   with self.assertRaises(ValueError):validate_child_proof(path,site)
 def test_draft_gate_closed(self):
  with tempfile.TemporaryDirectory(dir=HERE/'.selftest') as tmp:
   root=Path(tmp);writejson(root/'audit/build.json',{'draft':True})
   with self.assertRaisesRegex(ValueError,'Draft is not eligible'):check_gates(root,root/'child',None,None,None)
 def test_prepared_gate_binding_and_stale_root(self):
  with tempfile.TemporaryDirectory(dir=HERE/'.selftest') as tmp:
   r=Path(tmp);site,proof,p=fixture(r);child_release=r/'child-release';(child_release/'sites').mkdir(parents=True);shutil.move(str(site),child_release/'sites/world-law-jp-01');site=child_release/'sites/world-law-jp-01';_,child_fp=fingerprint(child_release/'sites');writejson(child_release/'audit/freeze-receipt.json',{'siteFileManifestSha256':child_fp});live=validate_child_proof(proof,site);release=r/'root';public=release/'sites/world-law-portal';root_commit='d'*40
   writejson(public/'jp190-routes.json',{'sourceRootCommit':root_commit,'childSiteFileManifestSha256':child_fp,'childDeploymentReceipt':live});writejson(release/'audit/build.json',{'draft':False,'sourceRootCommit':root_commit,'childSiteFingerprint':child_fp});writejson(release/'audit/baseline-files.json',{'commit':root_commit});mapping,fp=fingerprint(public);receipt={'passed':True,'siteFileManifestSha256':fp,'filesSha256':mapping};writejson(release/'audit/root190-validation.json',receipt);review=r/'independent.json';writejson(review,receipt)
   snapshot={'ref':'refs/heads/main','object':{'sha':root_commit,'type':'commit'}};raw=json.dumps(snapshot).encode();write(r/'evidence/root-ref.json',raw);row={'status':200,'checkedAt':p['checkedAt'],'url':'https://api.github.com/repos/NaNaCompany/world-law-portal/git/ref/heads/main','bodyFile':'evidence/root-ref.json','bodySha256':sha(raw)};root_proof=r/'root-head.json';writejson(root_proof,row);self.assertTrue(check_gates(release,child_release,proof,review,root_proof)['localPreparationGatesPassed'])
   stale={**row,'checkedAt':'2000-01-01T00:00:00Z'};writejson(root_proof,stale)
   with self.assertRaises(ValueError):check_gates(release,child_release,proof,review,root_proof)
   writejson(root_proof,row);build=readjson(release/'audit/build.json');build['sourceRootCommit']='e'*40;writejson(release/'audit/build.json',build)
   with self.assertRaisesRegex(ValueError,'Public root source pin'):check_gates(release,child_release,proof,review,root_proof)
   build['sourceRootCommit']=root_commit;writejson(release/'audit/build.json',build);write(public/'changed.txt','mutant')
   with self.assertRaisesRegex(ValueError,'Current successful root validation'):check_gates(release,child_release,proof,review,root_proof)
 def test_sitemap_exact190(self):
  ps={'world-laws/jp-'+str(i)+'.html' for i in range(190)};s='<urlset><url><loc>'+ROOT+'</loc></url>'+''.join('<url><loc>'+ROOT+p+'</loc></url>' for p in sorted(ps))+'</urlset>';self.assertEqual(rewrite_sitemap(s,ps),'<urlset><url><loc>'+ROOT+'</loc></url></urlset>')
  with self.assertRaises(ValueError):rewrite_sitemap(s,set())
if __name__=='__main__':unittest.main()
