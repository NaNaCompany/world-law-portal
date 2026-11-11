"""Create explicit code-only snapshot. No repository or network operations."""
import pathlib,json,hashlib,shutil,sys
sys.dont_write_bytecode=True
W=pathlib.Path(__file__).resolve().parent;O=W/'code-checkpoint-v4';assert not O.exists();C=O/'code';C.mkdir(parents=True)
allow=['build_child.py','build_root_integration.py','check_child_live.py','prepare_historical_delta.py','prepare_inventory_adapter.py','root-inventory-adapter.mjs','root_adapter.test.mjs','upgrade_public_validator.py','validate_package.py','validate_root.mjs','package_code_checkpoint.py','prepare_root_transfer.py','check_root_live.py','test_root_live_gates.py']
for name in allow:shutil.copyfile(W/name,C/name)
for name in ['validate-jp190-transition.mjs','validate-jp02-editions.mjs']:
 p=C/'root-public-scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(W/'root-integration/site/scripts'/name,p)
(C/'.gitignore').write_text('release/\nroot-integration/\nroot-history-draft/\n*checkpoint*/\n__pycache__/\n*.pyc\n*.json\n*.html\n*.tar.gz\n')
(C/'README.md').write_text('''# JP02 edition release code checkpoint

Code-only snapshot of local preparation and read-only verification tools. This package contains no legislative source files, rendered law pages, response bodies, audit reports, proof files, credentials or conversation. Public validator scripts contain only the reviewed edition identifiers and preservation hash pins required to validate this bounded release.

The source working directory sits beside split-tools, root190-tools, root190-live-checks, route-aware-additions, root190-prepared, jp01-phase1-release-v2, next-japan-inputs and jp-tools. Those dependencies and separately reviewed private inputs are required to run the tools. This code checkpoint alone is deliberately not a self-contained law dataset or a publication grant. Restore the scripts to an isolated jp02-release-work directory in that layout, never to protected source trees.

build_child.py validates exact source/review/freeze/planner pins and wraps the approved structured fragments without changing legal text. validate_package.py validates and packages the child and prepares whole-file Git arguments locally. prepare_historical_delta.py inserts reversible outside-article notices only. build_root_integration.py creates a separate full root draft. upgrade_public_validator.py adds the read-only JP02 validator companion while retaining the existing190 route and166 local-addition checks. validate_root.mjs checks measured counts and complete-file preservation. root_adapter.test.mjs reads externally supplied private fixture IDs and metadata and creates eight in-memory ownership/provenance/count/routing mutation tests. The fixtures are actual preparation outputs, not fully synthetic fixtures. prepare_root_transfer.py prepares the bounded20-file root delta after rechecking saved child evidence and candidate hashes; independent transfer and live gate review still control publication.

check_child_live.py is read-only on the network. It requires fresh saved GitHub ref/commit/tree/workflow responses, verifies47Git blobs and46HTTP resources, explicitly excludes the .nojekyll build-control file from HTTP, and saves responses and headers privately. The approved edge primitive checks shell/canonical/snippets/references; JP02 article bytes and source/text markers are checked separately. No broad script removal is permitted. check_root_live.py applies the same narrow-edge approach to the final root, verifies all8368Git blobs and the complete8376entry tree, checks217root HTTP resources plus29JP02 targets, and retains the distinction between full Git verification and sampled unchanged HTTP pages. test_root_live_gates.py runs nine fully synthetic identity/tree mutation tests against the actual checker gate functions.

No tool in this snapshot writes GitHub, changes repository/Pages/security settings, or authorizes a main update. Parent publication control must verify independent review, exact expected tree, a fresh main lease and live evidence. Child first, then root links. Root retains all previous editions and self-canonicals. Mutator guards are unchanged.

Freeze this allowlist by SHA before any code checkpoint. Outputs and private prerequisites are never recursively included. If reviewer changes code later, create a new versioned checkpoint rather than silently changing this packet.
''')
sha=lambda b:hashlib.sha256(b).hexdigest();files=[]
for p in sorted(C.rglob('*')):
 if not p.is_file():continue
 name=p.relative_to(C).as_posix();raw=p.read_bytes();assert p.suffix not in ['.json','.html','.xml','.gz'];assert (b'/workspace/'+b'scratch/') not in raw
 files.append({'path':name,'bytes':len(raw),'sha256':sha(raw),'gitBlobSha1':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
manifest={'scope':'Only enumerated code/docs. No raw source, rendered laws, HTTP bodies, receipts, audits, proof or conversation. No external writes.','state':'prepared-code-only-checkpoint-pending-final-review','files':files}
(O/'PUBLIC-CODE-FILES.json').write_text(json.dumps(manifest,indent=2)+'\n');(O/'TREE-ENTRIES.json').write_text(json.dumps([{'path':x['path'],'mode':'100644','type':'blob','sha':x['gitBlobSha1']} for x in files],indent=2)+'\n')
requests=O/'blob-content';requests.mkdir()
for n,x in enumerate(files,1):
 payload={'content':(C/x['path']).read_text(),'encoding':'utf-8'};raw=json.dumps(payload,ensure_ascii=False).encode();assert len(raw)+65536<16777216;(requests/f'{n:03}.json').write_bytes(raw)
print(json.dumps({'codeFiles':len(files),'totalBytes':sum(x['bytes'] for x in files),'allowlistSha256':sha((O/'PUBLIC-CODE-FILES.json').read_bytes()),'treeEntriesBytes':(O/'TREE-ENTRIES.json').stat().st_size,'repositoryTargetUnassigned':True,'externalWrites':False}))
