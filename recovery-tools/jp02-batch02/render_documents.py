"""Reviewed batch01 page shell reused verbatim; receives approved fragments, never runs renderer."""
import html,hashlib
from build_release import page,splitarticle
sha=lambda b:hashlib.sha256(b).hexdigest()
e=lambda v:html.escape(str(v),quote=True)
def render_documents(b,I,S,snip,put):
 base=b['publicBase'];records=[];checks=[]
 for d in b['documents']:
  fragment=(I/d['fragmentFile']).read_bytes();assert sha(fragment)==d['fragmentSha256'];assert sha(d['text'].encode())==d['textSha256']
  path='world-laws/'+d['id']+'.html';url=base+path
  warning='<p class="scope official-excerpt">Official source excerpt: e-Gov marks MainProvision Extract=true. This source itself is an excerpt, not the complete main provisions.</p>' if d['officialSourceExcerpt'] else ''
  content='<h1>'+e(d['title'])+'</h1>'+warning+'<p class="scope">'+e(d['versionLabel'])+'</p>'
  content+='<dl>'+''.join('<dt>'+e(k)+'</dt><dd>'+e(v)+'</dd>' for k,v in [('Law ID',d['lawIdentifier']),('Revision ID',d['revisionIdentifier']),('Revision amendment effective date',d['effectiveDate']),('Effective-date meaning',d['effectiveDateMeaning']),('Original promulgation date',d['promulgationDate']),('Amendment promulgation date',d['amendmentPromulgationDate']),('Retrieved at',d['retrievedAt']),('Current revision observed at',d['scopeAsOf']),('Scope',d['scopeDefinition'])])+'</dl>'
  content+='<p><a href="'+e(d['sourcePage'])+'">Official source</a> · <a href="'+e(d['sourceData'])+'">Exact revision source data</a> · <a href="'+e(b['coverageEvidence']['officialSource'])+'">Dated current-revision census source</a></p>'
  if d.get('lineage'):content+='<aside class="scope edition-history">Additional newer edition. The previous page is retained unchanged: <a href="'+e(d['lineage']['previousCanonicalUrl'])+'">Previous collected edition</a>. A previous edition does not mean the law is repealed.</aside>'
  content+='<p class="scope">Unofficial processed original-language text snapshot. Tables, figures and formulas are omitted with source-location notices. No translation or certification of legal force or completeness. Census metadata and revision source data were observed separately.</p>'
  article='<article lang="ja" data-source-sha256="'+d['sourceSha256']+'" data-text-sha256="'+d['textSha256']+'">'+fragment.decode()+'</article>'
  content+=article+'<section class="source-provenance"><h2>Source, processing and reuse</h2><p>'+e(d['publisher'])+'</p><p>'+e(d['rights'])+' <a href="'+e(d['rightsUrl'])+'">Rights basis</a></p><ul>'+''.join('<li>'+e(v)+'</li>' for v in d['reuseConditions'])+'</ul><p>'+e(d['extraction'])+'</p><p>Source SHA-256: '+d['sourceSha256']+'<br>Retained text SHA-256: '+d['textSha256']+'</p></section>'
  rendered=page(d['title'],'ja',url,content,snip,base).replace('<link rel="stylesheet" href="'+base+'style.css">','<link rel="stylesheet" href="'+base+'style.css"><link rel="stylesheet" href="'+base+'jp-structured.css">')
  assert splitarticle(rendered)[1]==article
  put(S/path,rendered)
  public={k:v for k,v in d.items() if k not in ['text','fragmentFile','localRawSource','officialRevisionMetadata']}
  public.update(html=path,localPath=path,repository='world-law-jp-02',canonicalUrl=url,htmlSha256=sha(rendered.encode()),articleSha256=sha(article.encode()),sourceFragmentSha256=d['fragmentSha256'])
  records.append(public);checks.append({'path':path,'fragmentSha256':sha(fragment),'articleSha256':public['articleSha256'],'htmlSha256':public['htmlSha256']})
 return records,checks
