"""New recovery evidence from pinned archive bytes and baseline HTML; not a historical audit."""
import argparse,collections,datetime,hashlib,html,json,re,subprocess
from pathlib import Path
H=lambda b:hashlib.sha256(b if isinstance(b,bytes) else b.encode()).hexdigest()
J=lambda o:json.dumps(o,ensure_ascii=False,separators=(',',':'))
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--sources',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 baseline=a.baseline.resolve();sources=a.sources.resolve();out=a.out.resolve()
 assert subprocess.check_output(['git','-C',str(baseline),'rev-parse','HEAD'],text=True).strip()=='6d419490783ca01b2b70d12f8d999021c13734ec'
 assert not subprocess.check_output(['git','-C',str(baseline),'status','--porcelain'],text=True)
 catraw=(baseline/'additions-catalog.json').read_bytes();cat=json.loads(catraw);jp={d['id']:d for d in cat['documents'] if d['country']=='JP'}
 prov=json.loads((sources/'provenance.json').read_text())['documents'];assert len(prov)==len(jp)==190 and {d['id'] for d in prov}==set(jp)
 assert len({d['revisionIdentifier'] for d in prov})==190
 when=datetime.datetime.now(datetime.timezone.utc).isoformat();laws=[];maps=[];totals=collections.Counter();checks=[]
 for d in prov:
  b=jp[d['id']]
  for k in ['sourceSha256','lawIdentifier','revisionIdentifier','sourceData','sourcePage','publisher','retrievedAt','rights','rightsUrl','reuseConditions']:assert d[k]==b[k],(d['id'],k)
  rp=sources/'raw'/(d['revisionIdentifier']+'.json');raw=rp.read_bytes();assert H(raw)==d['sourceSha256'];obj=json.loads(raw.decode('utf-8',errors='strict'));assert obj['law_info']['law_id']==d['lawIdentifier'] and obj['revision_info']['law_revision_id']==d['revisionIdentifier']
  oldraw=(baseline/b['html']).read_bytes();oldpage=oldraw.decode('utf-8');m=re.search(r'<article lang="ja" data-text-sha256="([a-f0-9]{64})"><div class="source-page" data-source-page="1">([\s\S]*?)</div></article>',oldpage);assert m,(d['id'],'old article');oldtext=html.unescape(m[2]);assert m[1]==b['textSha256']==H(oldtext)
  tree=obj['law_full_text'];assert tree['tag']=='Law';nodes=[];leaves=[];kept=[];omits=[];counts=collections.Counter();keptcounts=collections.Counter();attributes=0;keptattrs=0
  def visit(n,path='/law_full_text',parent=None,excluded=False):
   nonlocal attributes,keptattrs
   if isinstance(n,str):
    leaves.append(n)
    if not excluded:kept.append(n)
    return
   idx=len(nodes);tag=n['tag'];attrs=n['attr'];nodes.append([idx,parent,tag,attrs]);counts[tag]+=1;attributes+=len(attrs);startleaf=len(leaves);startnode=idx;omit=tag in {'Table','Fig','ArithFormula'}
   if not excluded and not omit:keptcounts[tag]+=1;keptattrs+=len(attrs)
   for i,c in enumerate(n['children']):visit(c,path+'/children/'+str(i),idx,excluded or omit)
   if omit and not excluded:
    block=nodes[startnode:];ol=leaves[startleaf:]
    omits.append({'sourceNode':idx,'parent':parent,'tag':tag,'path':path,'attributes':attrs,'subtreeSha256':H(J(n)),'sourceNodeCount':len(block),'firstSourceLeaf':startleaf,'sourceLeafCount':len(ol),'sourceLeafSequenceSha256':H(J(ol)),'nestedNodeCounts':dict(collections.Counter(x[2] for x in block))})
  visit(tree);omits.sort(key=lambda x:x['sourceNode']);structure={'id':d['id'],'sourceSha256':H(raw),'sourceTreeSha256':H(J(tree)),'sourceNodes':nodes,'sourceLeafCount':len(leaves),'sourceLeafSequenceSha256':H(J(leaves))};sp=out/'structures'/(d['id']+'.json');save(sp,structure)
  law={**b,'rawSourceFile':str(rp),'oldHtmlSha256':H(oldraw),'sourceTreeSha256':H(J(tree)),'sourceLeafCount':len(leaves),'sourceLeafSequenceSha256':H(J(leaves)),'retainedLeafCount':len(kept),'retainedTextSha256':H(''.join(kept)),'retainedLeafSequenceSha256':H(J(kept)),'sourceNodeCount':len(nodes),'sourceAttributeCount':attributes,'retainedNodeCount':sum(keptcounts.values()),'retainedAttributeCount':keptattrs,'structureCounts':dict(counts),'retainedStructureCounts':dict(keptcounts),'structureAuditFile':str(sp),'structureAuditSha256':H(sp.read_bytes())}
  laws.append(law);maps.append({'id':d['id'],'sourceSha256':H(raw),'retainedSourceLeafSha256':law['retainedTextSha256'],'retainedLeafSequenceSha256':law['retainedLeafSequenceSha256'],'omissions':omits})
  totals.update({'sourceNodes':len(nodes),'retainedNodes':sum(keptcounts.values()),'sourceLeaves':len(leaves),'retainedLeaves':len(kept),'omittedLeaves':len(leaves)-len(kept),'sourceAttributes':attributes,'retainedAttributes':keptattrs,'omissions':len(omits),'omissionDocuments':bool(omits),'retainedRemarks':keptcounts['Remarks']})
  checks.append({'id':d['id'],'sourceSha256':H(raw),'rawBytes':len(raw),'oldTextSha256':H(oldtext),'oldHtmlSha256':H(oldraw),'passed':True})
 save(out/'source-structure-audit.json',{'passed':True,'newRecoveryAudit':True,'verifiedAt':when,'baselineCommit':'6d419490783ca01b2b70d12f8d999021c13734ec','baselineCatalogueSha256':H(catraw),'laws':laws,'totals':dict(totals)})
 save(out/'omission-map.json',{'newRecoveryAudit':True,'verifiedAt':when,'records':maps,'totals':dict(totals)})
 save(out/'offline-verification.json',{'passed':True,'newRecoveryAudit':True,'verifiedAt':when,'documents':190,'originalSourceAndOldBodyPinsVerified':True,'provenanceUnchanged':True,'results':checks})
 print(json.dumps({'passed':True,'documents':190,'totals':dict(totals)}))
if __name__=='__main__':main()
