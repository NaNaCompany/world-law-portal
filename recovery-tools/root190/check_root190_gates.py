#!/usr/bin/env python3
"""Fail-closed root preparation/CAS eligibility check. Performs no remote action."""
import argparse,json,re,sys
from pathlib import Path
sys.dont_write_bytecode=True
from root190_common import *

def check_gates(release,child_release,live_proof,independent_review,root_head_evidence):
 root=Path(release);site=root/'sites/world-law-portal';build=readjson(root/'audit/build.json')
 if build.get('draft') is not False:raise ValueError('Draft is not eligible; rebuild in a new directory with actual live child evidence')
 if not all([live_proof,independent_review,root_head_evidence]):raise ValueError('Actual live child, independent current root review and fresh root HEAD evidence required')
 current,fp=fingerprint(site);validation=readjson(root/'audit/root190-validation.json');review=readjson(independent_review)
 if validation.get('passed') is not True or validation.get('siteFileManifestSha256')!=fp or validation.get('filesSha256')!=current:raise ValueError('Current successful root validation required')
 if review.get('passed') is not True or review.get('siteFileManifestSha256')!=fp or review.get('filesSha256')!=current:raise ValueError('Current independent full root file map required')
 routes=readjson(site/'jp190-routes.json');baseline=readjson(root/'audit/baseline-files.json')
 if routes.get('sourceRootCommit')!=build.get('sourceRootCommit') or baseline.get('commit')!=build.get('sourceRootCommit'):raise ValueError('Public root source pin differs from private baseline')
 _,child_fp=fingerprint(Path(child_release)/'sites')
 if child_fp!=build.get('childSiteFingerprint') or child_fp!=routes.get('childSiteFileManifestSha256') or child_fp!=readjson(Path(child_release)/'audit/freeze-receipt.json').get('siteFileManifestSha256'):raise ValueError('Exact frozen child generation required')
 live=validate_child_proof(live_proof,Path(child_release)/'sites/world-law-jp-01')
 if routes.get('childDeploymentReceipt')!=live:raise ValueError('Prepared root is not bound to supplied actual child deployment proof')
 row=readjson(root_head_evidence);snapshot=json.loads(evidence_body(root_head_evidence,row,'https://api.github.com/repos/NaNaCompany/world-law-portal/git/ref/heads/main'))
 if snapshot.get('ref')!='refs/heads/main' or snapshot.get('object',{}).get('type')!='commit' or snapshot.get('object',{}).get('sha')!=build['sourceRootCommit']:raise ValueError('Fresh root HEAD differs from approved source baseline; reconcile before CAS')
 return {'localPreparationGatesPassed':True,'siteFileManifestSha256':fp,'expectedRootHead':build['sourceRootCommit'],'actualChildDeployment':live,'independentReviewSha256':sha(Path(independent_review).read_bytes()),'rootHeadEvidenceSha256':sha(Path(root_head_evidence).read_bytes()),'externalWrites':False,'rootDeployed':False,'casPerformed':False,'remainingGates':['Recheck root main immediately before separately authorized compare-and-swap','Verify exact root Pages revision and old190 redirects live after publication','Do not infer timeout resolution from smaller size']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--child-release',required=True);p.add_argument('--live-proof');p.add_argument('--independent-review');p.add_argument('--root-head-evidence');p.add_argument('--report');a=p.parse_args()
 try:r=check_gates(a.release,a.child_release,a.live_proof,a.independent_review,a.root_head_evidence)
 except (ValueError,KeyError,FileNotFoundError) as e:r={'localPreparationGatesPassed':False,'externalWrites':False,'rootDeployed':False,'casPerformed':False,'blocker':str(e)}
 if a.report:writejson(a.report,r)
 print(json.dumps(r,indent=2));sys.exit(0 if r['localPreparationGatesPassed'] else 1)
