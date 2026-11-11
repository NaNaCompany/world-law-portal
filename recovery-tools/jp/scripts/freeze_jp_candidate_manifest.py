"""Freeze hash receipts for a dirty candidate; commit/publication are deliberately external."""
import argparse,base64,hashlib,json,subprocess
from pathlib import Path
H=lambda b:hashlib.sha256(b if isinstance(b,bytes) else b.encode()).hexdigest()
J=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();root=a.root.resolve();repo=root/'repo';audit=root/'audit';m=json.loads((audit/'migration-applied.json').read_text());assert m['passed'] and m['applied']
 expected={r['path']:r for r in m['changedFiles']};assert len(expected)==len(m['changedFiles'])==199
 actual=set(subprocess.check_output(['git','-C',str(repo),'diff','--name-only'],text=True).splitlines())|set(subprocess.check_output(['git','-C',str(repo),'ls-files','--others','--exclude-standard'],text=True).splitlines());assert actual==set(expected)
 for path,r in expected.items():b=(repo/path).read_bytes();assert len(b)==r['bytes'] and H(b)==r['sha256']
 assert json.loads((audit/'validate-additions.json').read_text())['passed'] and json.loads((audit/'validate-published.json').read_text())['passed']
 fingerprint=H(J(m['changedFiles']));save(audit/'candidate-files.json',{'baselineCommit':m['baselineCommit'],'files':m['changedFiles'],'candidateContentFingerprint':fingerprint,'historicalCandidateByteIdentityClaimed':False})
 transport=[]
 for d in m['documents']:
  b=(repo/d['html']).read_bytes();assert H(b)==d['htmlSha256'];enc=base64.b64encode(b).decode();payload=J({'repository_full_name':'NaNaCompany/world-law-portal','encoding':'base64','content':enc}).encode();n=len(payload);assert n+65536<16*1024*1024
  transport.append({'id':d['id'],'rawBytes':len(b),'base64Bytes':len(enc),'jsonRequestBytes':n,'requestWith64KiBReserve':n+65536,'remainingBytes':16*1024*1024-n-65536})
 big=max(transport,key=lambda d:d['jsonRequestBytes']);golden=repo/'world-laws/jp-egov-325ac0000000226_20261101_508ac0000000002.html';assert H(golden.read_bytes())=='98e201bea9375c4074d719eb082737126cca331b9688cf4a7dca65c84b5eb767'
 save(audit/'transport-sizes.json',{'passed':True,'documents':190,'limitBytes':16*1024*1024,'reserveBytes':65536,'largest':big,'results':transport,'goldenFullRootSha256':H(golden.read_bytes())})
 evidence={'structure':str(audit/'renderer-verification.json'),'omission':str(audit/'omission-map.json'),'provenance':str(audit/'offline-verification.json'),'candidateFiles':str(audit/'candidate-files.json')}
 handoff={'baselineCommit':m['baselineCommit'],'frozenCommit':None,'candidateRoot':str(repo),'candidateContentFingerprint':fingerprint,'noNewLawCollection':True,'documents':m['documents'],'evidenceLocation':evidence}
 ready={'frozenCommit':None,'jp190StructureRestorationPassed':True,'omissionReceiptsVerified':True,'independentJp190ReviewPassed':False,'evidenceLocation':evidence,'candidateContentFingerprint':fingerprint,'status':'Fresh independent candidate review and parent commit freeze are still required.'}
 save(root/'phase1-input.json',handoff);save(root/'phase1-readiness.json',ready);print(json.dumps({'passed':True,'fingerprint':fingerprint,'largest':big}))
if __name__=='__main__':main()
