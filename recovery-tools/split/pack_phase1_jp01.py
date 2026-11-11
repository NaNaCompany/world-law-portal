#!/usr/bin/env python3
"""Pack validated JP190-only artifact locally; never marks full migration complete."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from build_release import readjson,writejson,sha,files_digest
from pack_release import deterministic_archive
from phase1_jp01 import REPO
def pack_phase1(release):
 root=Path(release);v=readjson(root/'audit/phase1-validation.json');files,digest=files_digest(root/'sites')
 if v.get('phase')!='jp190-only' or v.get('fullSplitComplete') is not False or not v['passed'] or digest!=v.get('siteFileManifestSha256'):raise ValueError('Current explicit phase1 validation required')
 target=root/'artifacts'/(REPO+'.tar.gz');deterministic_archive(root/'sites'/REPO,target);result={'phase':'jp190-only','fullSplitComplete':False,'repository':REPO,'artifact':str(target.relative_to(root)),'sha256':sha(target.read_bytes()),'compressedBytes':target.stat().st_size,'uncompressedBytes':sum(p.stat().st_size for p in (root/'sites'/REPO).rglob('*') if p.is_file()),'state':'local-phase1-candidate-not-known-good-live'};writejson(root/'audit/file-sha256.json',files);writejson(root/'audit/phase1-artifact.json',result);print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);a=p.parse_args();pack_phase1(a.release)
