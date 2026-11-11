#!/usr/bin/env python3
"""Local-only SMALL tree requests plus whole-file create_blob requests.
No network calls. Prior 7 MiB inline transport is deliberately not reused.
Recovered Git hashing logic; new small-request strategy. Historical code identity unverified.
"""
import argparse,base64,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
REPO='NaNaCompany/world-law-jp-01'
INITIAL_TREE='c4b02b26d2f47273d696c7ab7ed7aa46d7b87b15'
EMPTY_TREE_STEP='f33a28d1889e86069cabe7439403b3cb51f5298e'
OLD_README='53a2e95fdda864473cc87ca7d95f37929aa688f1'
EMPTY_BLOB='e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
REUSE_PATH='world-laws/jp-egov-325ac0000000226_20261101_508ac0000000002.html'
REUSE_BLOB='d7acec76a41a7ea408da34b5c489fe3411a8faad'
OLD_FINAL_TREE='07d4c80e2e62ec2fd1f92e2f10c16aecd697f7e5'
OLD_SITE_FP='16e825c0328410cbec6248966c22c99caed8dccd712df411e58696c6c0c8ff0b'
RESERVE=65536
PLUGIN_LIMIT=16*1024*1024

def sha(raw):return hashlib.sha256(raw).hexdigest()
def objsha(kind,raw):return hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def encode(o,ascii_only=False):return json.dumps(o,ensure_ascii=ascii_only,separators=(',',':')).encode()
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(encode(o)+b'\n')
def trie(files):
 root={}
 for path,value in files.items():
  parts=path.split('/')
  if any(not x or x in {'.','..'} or '\0' in x for x in parts):raise ValueError('Unsafe path')
  node=root
  for part in parts[:-1]:
   node=node.setdefault(part,{})
   if not isinstance(node,dict):raise ValueError('Path collision')
  if parts[-1] in node:raise ValueError('Duplicate path')
  node[parts[-1]]=value
 return root

def pure_tree(files):
 def walk(n):
  entries=[]
  for name,v in n.items():
   directory=isinstance(v,dict);target=walk(v) if directory else v;mode=b'40000' if directory else b'100644';key=name.encode()+(b'/' if directory else b'');entries.append((key,mode+b' '+name.encode()+b'\0'+bytes.fromhex(target)))
  return objsha('tree',b''.join(x[1] for x in sorted(entries)))
 return walk(trie(files))

def git_tree(files,bare):
 def walk(n):
  lines=[]
  for name,v in n.items():
   directory=isinstance(v,dict);target=walk(v) if directory else v;mode='040000' if directory else '100644';kind='tree' if directory else 'blob';lines.append(f'{mode} {kind} {target}\t{name}\0'.encode())
  return subprocess.check_output(['git','--git-dir',str(bare),'mktree','--missing','-z'],input=b''.join(lines)).decode().strip()
 return walk(trie(files))

def prepare(release,output,expected_head,base_tree=INITIAL_TREE,tree_budget=500*1024,inline_limit=128*1024):
 release=Path(release);out=Path(output);site=release/'sites/world-law-jp-01'
 if out.exists() or site.resolve() in out.resolve().parents:raise ValueError('New output outside public site required')
 if not 128*1024<=tree_budget<=500*1024:raise ValueError('Tree budget must stay at most500KiB')
 if not 0<inline_limit<tree_budget-RESERVE:raise ValueError('Invalid small-inline threshold')
 if len(expected_head)!=40 or any(c not in '0123456789abcdef' for c in expected_head):raise ValueError('Expected remote HEAD required')
 manifest_raw=(release/'audit/public-files-manifest.json').read_bytes();manifest=json.loads(manifest_raw);freeze=json.loads((release/'audit/freeze-receipt.json').read_bytes())
 if sha(manifest_raw)!=freeze['publicFilesManifestSha256'] or manifest.get('phase')!='jp190-only' or manifest.get('fullSplitComplete') is not False:raise ValueError('Reviewed explicit phase1 freeze required')
 expected={r['path']:r for r in manifest['files']};paths={p.relative_to(site).as_posix():p for p in site.rglob('*') if p.is_file()}
 if len(paths)!=208 or set(paths)!=set(expected) or any(p.is_symlink() for p in site.rglob('*')):raise ValueError('Exact208 regular frozen public files required')
 raws={path:p.read_bytes() for path,p in sorted(paths.items())};blobs={}
 for path,raw in raws.items():
  r=expected[path];blob=objsha('blob',raw)
  if sha(raw)!=r['sha256'] or len(raw)!=r['bytes'] or blob!=r['gitBlobSha1']:raise ValueError('Frozen file mismatch: '+path)
  raw.decode('utf-8');blobs[path]=blob
 prefixes={'world-law-jp-01/'+p:sha(raw) for p,raw in raws.items()};fp=sha(json.dumps(prefixes,sort_keys=True,separators=(',',':')).encode())
 if fp!=freeze['siteFileManifestSha256']:raise ValueError('Frozen file fingerprint mismatch')
 initial={'README.md':OLD_README}
 if base_tree==EMPTY_TREE_STEP:initial['.nojekyll']=EMPTY_BLOB
 elif base_tree!=INITIAL_TREE:raise ValueError('Unreviewed baseline tree')
 if pure_tree(initial)!=base_tree:raise ValueError('Baseline tree differs')
 out.mkdir(parents=True);operations=[];entries=[];new_blobs=[]
 def store_request(kind,args,extra):
  disk=encode(args,True);wire=encode(args);number=len(operations)+1;path=f'requests/{number:03d}-{kind}.json'
  if len(wire)+RESERVE>PLUGIN_LIMIT or len(disk)+RESERVE>PLUGIN_LIMIT:raise ValueError('Plugin request cap; never truncate or split HTML')
  if kind=='create-tree' and len(wire)+RESERVE>tree_budget:raise ValueError('Small tree request cap')
  target=out/path;target.parent.mkdir(exist_ok=True);target.write_bytes(disk);record={'step':number,'kind':kind,'tool':'mcp__codex_apps__github_'+kind.replace('-','_'),'requestPath':path,'requestSha256':sha(disk),'requestFileBytes':len(disk),'utf8WireBytes':len(wire),'wireSha256':sha(wire),'reserveBytes':RESERVE,'storageEncoding':'ascii-json',**extra};operations.append(record);return record
 ordered=([REUSE_PATH] if REUSE_PATH in raws else [])+['README.md']+[p for p in sorted(raws) if p not in {REUSE_PATH,'README.md'}]
 for path in ordered:
  raw=raws[path];entry={'path':path,'mode':'100644','type':'blob'}
  reuse=path==REUSE_PATH and blobs[path]==REUSE_BLOB
  inline_entry={**entry,'content':raw.decode('utf-8')}
  if reuse:entry['sha']=REUSE_BLOB
  elif len(encode(inline_entry))>inline_limit:
   args={'content':base64.b64encode(raw).decode(),'encoding':'base64','repository_full_name':REPO}
   if base64.b64decode(args['content'])!=raw:raise ValueError('Base64 roundtrip mismatch')
   store_request('create-blob',args,{'path':path,'expectedBlobSha':blobs[path],'sourceBytes':len(raw),'sourceSha256':sha(raw),'wholeFileUnsplit':True});entry['sha']=blobs[path];new_blobs.append(blobs[path])
  else:entry=inline_entry
  entries.append(entry)
 def tree_args(base,items):return {'base_tree_sha':base,'repository_full_name':REPO,'tree_elements':items}
 batches=[];batch=[]
 for e in entries:
  if batch and len(encode(tree_args(base_tree,batch+[e])))+RESERVE>tree_budget:batches.append(batch);batch=[]
  batch.append(e)
 if batch:batches.append(batch)
 state=dict(initial);base=base_tree
 with tempfile.TemporaryDirectory(prefix='.git-check-',dir=out) as tmp:
  bare=Path(tmp)/'objects.git';subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
  for path,raw in raws.items():
   if subprocess.check_output(['git','--git-dir',str(bare),'hash-object','--no-filters','--stdin'],input=raw).decode().strip()!=blobs[path]:raise ValueError('Independent Git blob mismatch')
  if git_tree(initial,bare)!=base:raise ValueError('Git baseline mismatch')
  for batch in batches:
   args=tree_args(base,batch)
   for e in batch:
    blob=e.get('sha') or objsha('blob',e['content'].encode())
    if blob!=blobs[e['path']]:raise ValueError('Tree entry blob mismatch')
    state[e['path']]=blob
   result=pure_tree(state)
   if result!=git_tree(state,bare):raise ValueError('Independent Git intermediate tree mismatch')
   store_request('create-tree',args,{'expectedBaseTree':base,'expectedResultTree':result,'resultingFileCount':len(state),'entryCount':len(batch),'paths':[e['path'] for e in batch],'requiresPriorBlobSuccess':sorted({e['sha'] for e in batch if e.get('sha') in new_blobs})});base=result
  if state!=blobs or len(state)!=208 or base!=git_tree(blobs,bare):raise ValueError('Final208 tree mismatch')
 plan={'schemaVersion':2,'strategy':'small-trees-plus-separate-whole-file-base64-blobs','phase':'jp190-only','fullSplitComplete':False,'repository':REPO,'expectedRemoteHead':expected_head,'initialTree':base_tree,'finalTree':base,'finalFileCount':208,'siteFileManifestSha256':fp,'historicalComparison':{'previousFinalTree':OLD_FINAL_TREE,'treeMatches':base==OLD_FINAL_TREE,'previousSiteFingerprint':OLD_SITE_FP,'siteFingerprintMatches':fp==OLD_SITE_FP,'differenceIsNotAutomaticallyFailure':'Different reviewed source commit/manifest metadata may change public metadata; investigate and obtain current review, never falsify hashes'},'treeWireBudgetBytes':tree_budget,'inlineEntryLimitBytes':inline_limit,'requestCount':len(operations),'blobRequests':sum(x['kind']=='create-blob' for x in operations),'treeRequests':len(batches),'requests':operations,'largestOldBlobReused':REUSE_PATH in blobs and blobs[REUSE_PATH]==REUSE_BLOB,'externalWritesPerformed':False,'published':False,'originalLargeTreeStrategyNotUsed':True,'initialFiles':initial,'finalFiles':[{'path':p,'mode':'100644','type':'blob','gitBlobSha1':blobs[p],'sha256':sha(raws[p]),'bytes':len(raws[p])} for p in sorted(blobs)],'verification':{'all208GitHashObject':True,'everyTreeGitMktree':True,'noRawArchiveOrAuditUploaded':True,'allFilesWholeAndUnchanged':True},'executionGates':['Confirm API health before any sequence; stop on errors, denial or uncertain outcome','Verify each create_blob SHA before any tree references it','Check every returned tree SHA against expectedResultTree before continuing','On uncertain outcome read the expected object before any retry; never change routes or tools to bypass a denial','Recheck current HEAD before separately authorized final commit/ref CAS','No partial batch is a live release; verify final208 tree then exact Pages/live/browser checks']}
 save(out/'plan.json',plan);return plan
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--enable-reviewed-transfer-plan',action='store_true');p.add_argument('--release');p.add_argument('--output');p.add_argument('--expected-head');p.add_argument('--base-tree',default=INITIAL_TREE);p.add_argument('--tree-budget',type=int,default=500*1024);p.add_argument('--inline-limit',type=int,default=128*1024);a=p.parse_args()
 if not a.enable_reviewed_transfer_plan:raise SystemExit('PAUSED: actual reviewed208-file freeze required; no requests generated')
 result=prepare(a.release,a.output,a.expected_head,a.base_tree,a.tree_budget,a.inline_limit);print(json.dumps({k:result[k] for k in ['strategy','requestCount','blobRequests','treeRequests','finalTree','historicalComparison','externalWritesPerformed']},indent=2))
