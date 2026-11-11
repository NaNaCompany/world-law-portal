"""Prepare only ten historical-page shell deltas. Not a root publication package."""
import pathlib,json,hashlib,re,html
W=pathlib.Path(__file__).resolve().parent;R=W.parent;I=R/'next-japan-inputs/jp02-batch01';root=R/'root190-prepared/sites/world-law-portal';out=W/'root-history-draft';assert not out.exists()
sha=lambda b:hashlib.sha256(b).hexdigest()
pin=I/'review/old10-preservation-pins.json';assert sha(pin.read_bytes())=='332ca1ab907986aef7316b1f16831f7a04f5cd1b631901614c645b9d39867183'
b=json.loads((I/'batch.json').read_text());assert sha((I/'batch.json').read_bytes())=='45dace91d4a1fdbbf25af9689fe02fcc369e9710b586bb4a51d2525c2e983b68'
docs={d['lawIdentifier']:d for d in b['documents']};manifest=[]
for p in json.loads(pin.read_text()):
 raw=(root/p['path']).read_bytes();assert sha(raw)==p['baselineHTMLSha256'];matches=list(re.finditer(rb'<article\b[\s\S]*?</article>',raw));assert len(matches)==1;article=matches[0].group();assert sha(article)==p['baselineArticleSha256']
 assert b'jp02-historical-edition-notice' not in raw
 d=docs[p['lawIdentifier']];url=b['publicBase']+'world-laws/'+d['id']+'.html'
 notice=('<!-- jp02-historical-edition-notice --><aside class="scope edition-history">Earlier collected edition retained as a historical snapshot. This does not mean the law is repealed. <a href="'+html.escape(url,quote=True)+'">Compare the additional newer edition observed in the official source as of '+html.escape(d['scopeAsOf'])+'</a>. Original text and source provenance below are retained.</aside><!-- /jp02-historical-edition-notice -->').encode()
 pos=matches[0].start();new=raw[:pos]+notice+raw[pos:];assert new[:pos]+new[pos+len(notice):]==raw;assert re.findall(rb'<article\b[\s\S]*?</article>',new)==[article]
 oldcanon=re.findall(rb'<link\b[^>]*rel="canonical"[^>]*>',raw);assert len(oldcanon)==1 and p['previousCanonicalUrl'].encode() in oldcanon[0];assert re.findall(rb'<link\b[^>]*rel="canonical"[^>]*>',new)==oldcanon
 target=out/'delta'/p['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(new)
 manifest.append({**p,'candidateHTMLSha256':sha(new),'insertionOffset':pos,'insertedBytes':len(notice),'noticeSha256':sha(notice),'newEditionUrl':url,'reversibleToOriginalBytes':True})
(out/'preservation.json').write_text(json.dumps({'publicationEligible':False,'reason':'Child live proof and complete root integration/independent review required','rootBaselineCommit':'7293901a2e905e2c72a0f4b5f422121e97d1f8d8','files':manifest},indent=2)+'\n')
print('PASS: ten shell-only candidates; removing recorded insertion restores every original byte; original article/canonical/provenance retained; publication ineligible')
