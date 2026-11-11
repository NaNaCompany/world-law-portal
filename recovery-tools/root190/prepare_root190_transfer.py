#!/usr/bin/env python3
"""Plan only exact changed root files on a verified existing tree. No network writes."""
import argparse,base64,json,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
from root190_common import *
from check_root190_gates import check_gates
REPO='NaNaCompany/world-law-portal';RESERVE=65536;CAP=16777216;BUDGET=512000
COMPLETION={'index.html','en/index.html','zh/index.html','es/index.html','additions-catalog.json','sitemap.xml','publication.json','publisher-status.json','collection-scope.json','jp190-routes.json'}
def encode(x,ascii=False):return json.dumps(x,ensure_ascii=ascii,separators=(',',':')).encode()
def standard_tree(mapping,bare):
 tree={}
 for p,h in mapping.items():
  node=tree
  for part in p.split('/')[:-1]:node=node.setdefault(part,{})
  node[p.split('/')[-1]]=h
 def walk(node):
  raw=b''
  for name,value in node.items():
   directory=isinstance(value,dict);target=walk(value) if directory else value;raw+=f'{"040000" if directory else "100644"} {"tree" if directory else "blob"} {target}\t{name}\0'.encode()
  return subprocess.check_output(['git','--git-dir',str(bare),'mktree','--missing','-z'],input=raw).decode().strip()
 return walk(tree)
def baseline_map(source):
 result={};raw=subprocess.check_output(['git','-C',str(source),'ls-tree','-rz','--full-tree','HEAD'])
 for item in raw.split(b'\0'):
  if not item:continue
  fields,path=item.split(b'\t',1);mode,kind,h=fields.decode().split();path=path.decode()
  if mode!='100644' or kind!='blob' or path in result:raise ValueError('Unexpected baseline mode/type/path')
  result[path]=h
 return result

def delta_inputs(release,source,independent_review):
 release=Path(release);source=Path(source);site=release/'sites/world-law-portal';build=readjson(release/'audit/build.json');validation=readjson(release/'audit/root190-validation.json');ind=readjson(independent_review);current,fp=fingerprint(site)
 if not validation.get('passed') or validation.get('siteFileManifestSha256')!=fp or validation.get('filesSha256')!=current or not ind.get('passed') or ind.get('siteFileManifestSha256')!=fp or ind.get('filesSha256')!=current:raise ValueError('Current full local and independent root maps required')
 if git(source,'rev-parse','HEAD')!=build['sourceRootCommit'] or git(source,'status','--porcelain'):raise ValueError('Clean pinned baseline required')
 original,original_fp=fingerprint(source);base_receipt=readjson(release/'audit/baseline-files.json')
 if original!=base_receipt['filesSha256'] or original_fp!=base_receipt['fingerprint']:raise ValueError('Baseline whole-file receipts changed')
 baseline=baseline_map(source)
 if set(baseline)!=set(original) or len(baseline)!=8364:raise ValueError('Complete8364-file baseline required')
 base=git(source,'rev-parse','HEAD^{tree}')
 if git_tree_entries(baseline)[0]!=base:raise ValueError('Baseline full tree differs')
 routes=readjson(site/'jp190-routes.json')['routes'];selected={x['oldPath'] for x in routes};allowed=selected|set(NAV)|{'additions-catalog.json','sitemap.xml','publication.json','publisher-status.json','collection-scope.json'}|{'scripts/'+p for p in MUTATORS+LEGACY_VALIDATORS};added={'jp190-routes.json','scripts/root190-route-guard.mjs','scripts/validate-jp190-transition.mjs'};changed={p for p,h in original.items() if current.get(p)!=h}
 if changed!=allowed or set(current)-set(original)!=added or set(original)-set(current) or len(current)!=8367 or len(changed)!=204:raise ValueError('Exact204 changed and3 added files required')
 paths=sorted(changed|added);raws={p:(site/p).read_bytes() for p in paths};target=dict(baseline)
 for p,raw in raws.items():
  if sha(raw)!=current[p]:raise ValueError('Public file changed while reading')
  raw.decode('utf-8');target[p]=blob(raw)
 ca='legacy-laws/ca-acts-i-3.3.html'
 if ca in raws or target[ca]!=baseline[ca] or target[ca]!='c8ebe983b56cf1a1b151fb18a32f19643b2c37c6':raise ValueError('Large Canada file must stay as existing baseline blob')
 return build,fp,base,baseline,target,raws

def compile_plan(baseline,raws,base_tree,tree_budget=BUDGET,inline_limit=131072,max_entries=20):
 if tree_budget>BUDGET or tree_budget<=RESERVE or not 1<=max_entries<=50:raise ValueError('Unsafe tree request budget')
 if git_tree_entries(baseline)[0]!=base_tree:raise ValueError('Incorrect starting tree')
 target={**baseline,**{p:blob(v) for p,v in raws.items()}};completion=sorted(set(raws)&COMPLETION);early=sorted(set(raws)-COMPLETION);entries=[];blob_args={}
 for p in early+completion:
  raw=raws[p];entry={'path':p,'mode':'100644','type':'blob'};inline={**entry,'content':raw.decode('utf-8')}
  if p in COMPLETION or len(encode(inline))>inline_limit:entry['sha']=blob(raw);blob_args[p]={'repository_full_name':REPO,'encoding':'base64','content':base64.b64encode(raw).decode()}
  else:entry=inline
  entries.append(entry)
 def tree_args(base,batch):return {'base_tree_sha':base,'repository_full_name':REPO,'tree_elements':batch}
 batches=[];batch=[]
 for e in [x for x in entries if x['path'] not in COMPLETION]:
  if batch and (len(batch)>=max_entries or len(encode(tree_args(base_tree,batch+[e])))+RESERVE>tree_budget):batches.append(batch);batch=[]
  batch.append(e)
 if batch:batches.append(batch)
 if completion:batches.append([x for x in entries if x['path'] in COMPLETION])
 state=dict(baseline);base=base_tree;operations=[]
 def add(kind,args,extra):
  disk=encode(args,True);wire=encode(args)
  if max(len(disk),len(wire))+RESERVE>CAP or kind=='create-tree' and len(wire)+RESERVE>tree_budget:raise ValueError('Request too large; never split statute HTML')
  n=len(operations)+1;operations.append({'step':n,'kind':kind,'args':args,'requestPath':f'requests/{n:03d}-{kind}.json','requestSha256':sha(disk),'requestFileBytes':len(disk),'wireSha256':sha(wire),'utf8WireBytes':len(wire),'reserveBytes':RESERVE,**extra})
 for batch in batches:
  for e in batch:
   p=e['path']
   if p in blob_args:add('create-blob',blob_args[p],{'path':p,'sourceBytes':len(raws[p]),'sourceSha256':sha(raws[p]),'expectedBlobSha':target[p],'wholeFileUnsplit':True})
  for e in batch:state[e['path']]=target[e['path']]
  result=git_tree_entries(state)[0];add('create-tree',tree_args(base,batch),{'expectedBaseTree':base,'expectedResultTree':result,'resultingFileCount':len(state),'paths':[e['path'] for e in batch],'entryCount':len(batch),'completeTarget':state==target,'mainRefMustNotMoveUnlessFinal':True,'requiredPriorBlobShas':[e['sha'] for e in batch if e['path'] in blob_args]});base=result
 if state!=target:raise ValueError('Incomplete target tree')
 return operations,target

def prepare(args):
 release=Path(args.release).resolve();source=Path(args.source).resolve();out=Path(args.output).resolve()
 protected=[release,source,Path(args.child_release).resolve()]
 if out.exists() or any(out==p or p in out.parents or out in p.parents for p in protected):raise ValueError('New isolated output required')
 build,fp,base,baseline,target,raws=delta_inputs(release,source,args.independent_review);gate=None
 if args.draft_estimate:
  if build.get('draft') is not True:raise ValueError('Draft estimate accepts a draft only')
 else:gate=check_gates(release,args.child_release,args.live_proof,args.independent_review,args.root_head_evidence)
 operations,computed=compile_plan(baseline,raws,base)
 if computed!=target:raise ValueError('Target map mismatch')
 out.mkdir(parents=True)
 with tempfile.TemporaryDirectory(dir=out,prefix='.git-check-') as tmp:
  bare=Path(tmp)/'objects.git';subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
  if standard_tree(baseline,bare)!=base:raise ValueError('Standard Git baseline differs')
  state=dict(baseline)
  for op in operations:
   if op['kind']=='create-blob':
    raw=base64.b64decode(op['args']['content']);actual=subprocess.check_output(['git','--git-dir',str(bare),'hash-object','--no-filters','--stdin'],input=raw).decode().strip()
    if actual!=op['expectedBlobSha']:raise ValueError('Standard Git blob differs')
   else:
    for e in op['args']['tree_elements']:state[e['path']]=e.get('sha') or blob(e['content'].encode())
    if standard_tree(state,bare)!=op['expectedResultTree']:raise ValueError('Standard Git intermediate tree differs')
 if fingerprint(release/'sites/world-law-portal')[1]!=fp or git(source,'status','--porcelain'):raise ValueError('Input changed during planning')
 rows=[]
 for op in operations:
  if not args.draft_estimate:write(out/op['requestPath'],encode(op['args'],True))
  rows.append({k:v for k,v in op.items() if k!='args'})
 report={'schemaVersion':1,'phase':'jp190-root-transition','draftEstimateOnly':args.draft_estimate,'executableRequestsWritten':not args.draft_estimate,'preparationGates':gate,'repository':REPO,'expectedRemoteHead':build['sourceRootCommit'],'baseTree':base,'finalTree':git_tree_entries(target)[0],'siteFileManifestSha256':fp,'baselineFiles':8364,'targetFiles':8367,'changedFiles':204,'addedFiles':3,'transferredFiles':len(raws),'transferredRawBytes':sum(map(len,raws.values())),'unchangedFilesNotReuploaded':8160,'retainedCanadaBlob':target['legacy-laws/ca-acts-i-3.3.html'],'requestCount':len(rows),'blobRequests':sum(o['kind']=='create-blob' for o in rows),'treeRequests':sum(o['kind']=='create-tree' for o in rows),'totalUtf8WireBytes':sum(o['utf8WireBytes'] for o in rows),'maxTreeUtf8WireBytes':max(o['utf8WireBytes'] for o in rows if o['kind']=='create-tree'),'maxBlobUtf8WireBytes':max((o['utf8WireBytes'] for o in rows if o['kind']=='create-blob'),default=0),'treeBudgetIncludingReserveBytes':BUDGET,'pluginLimitIncludingReserveBytes':CAP,'reserveBytes':RESERVE,'requests':rows,'deltaFiles':[{'path':p,'bytes':len(v),'sha256':sha(v),'gitBlobSha1':blob(v),'previousBlobSha1':baseline.get(p)} for p,v in sorted(raws.items())],'finalFiles':[{'path':p,'mode':'100644','type':'blob','sha':h} for p,h in sorted(target.items())],'standardGitEveryTreeVerified':True,'externalWrites':False,'commitCreated':False,'mainCasPerformed':False,'publicationReady':False,'executionGates':['No execution of a draft estimate','Check actual returned SHA after each call; stop on errors/denials/uncertainty and verify uncertain results before retry','No intermediate main or Pages update; only complete8367-file tree can proceed','Recheck current root main immediately before separately authorized final commit/CAS','Verify exact root Pages run and live redirect/body/sitemap/browser checks afterward','No public raw archive, audit, source corpus or tooling uploads']}
 writejson(out/('draft-estimate.json' if args.draft_estimate else 'plan.json'),report);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--draft-estimate',action='store_true');g.add_argument('--enable-reviewed-transfer-plan',action='store_true');p.add_argument('--release',required=True);p.add_argument('--source',required=True);p.add_argument('--child-release',required=True);p.add_argument('--independent-review',required=True);p.add_argument('--live-proof');p.add_argument('--root-head-evidence');p.add_argument('--output',required=True);a=p.parse_args();r=prepare(a);print(json.dumps({k:r[k] for k in ['draftEstimateOnly','executableRequestsWritten','baseTree','finalTree','transferredFiles','transferredRawBytes','requestCount','blobRequests','treeRequests','totalUtf8WireBytes','maxTreeUtf8WireBytes','maxBlobUtf8WireBytes','externalWrites']},indent=2))
