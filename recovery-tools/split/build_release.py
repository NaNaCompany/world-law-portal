#!/usr/bin/env python3
"""Recovered phase1 shared primitives only. The full split builder is NOT restored.
Byte identity to the lost tools is unverified. Direct full-release invocation fails closed.
"""
import hashlib,html,json,os,re,subprocess,sys
from pathlib import Path
from urllib.parse import urljoin,urlsplit
sys.dont_write_bytecode=True
HUB='world-law-portal'
ROOT_BASE='https://nanalab.kr/world-law-portal/'
LANGS={'ko':'','en':'en/','zh':'zh/','es':'es/'}
NAV=['index.html','en/index.html','zh/index.html','es/index.html','kr/index.html']
PUBLISHERS=['adsense','gtm','ga4-loader','ga4-config','gtm-noscript','cloudflare-fallback']
SITEMAP_NS='http://www.sitemaps.org/schemas/sitemap/0.9'
ARTICLE=re.compile(r'<article\b[\s\S]*?</article>')
ATTR=re.compile(r'\b(href|src)=("|\')([^"\']*)\2')
TAG=re.compile(r'<(?:a|link|script|iframe)\b[^>]*>',re.I)
BANNER='<!-- NaNa shared book banner --><script defer src="https://nanalab.kr/src_cdn/banner/astra.js"></script><!-- /NaNa shared book banner -->'
MORE='<a class="more-apps" href="https://nanalab.kr/apps/" lang="en">More Apps</a>'
DISCLAIMERS={
'ko':('법령 자료실','일부만 수집한 비공식 원문 자료실입니다. 국가 전체 법령이나 최신 현행법 전수를 제공하지 않습니다. 판본과 법적 효력은 공식 출처에서 확인하세요. 그림·수식·표 등 제외된 내용은 각 문서의 고지를 확인하세요. 화면 언어만 바뀌며 법령은 번역하지 않습니다.'),
'en':('Law collection','Partial, unofficial original-language snapshots, not a complete national corpus or a certification of current legal force. Check the official source and each document’s edition and omission notices, including omitted figures, formulas and tables. Interface languages do not translate the law.'),
'zh':('法律资料库','非官方的部分原文快照，不代表完整的国家法律库，也不保证现行效力。请核对官方来源、版本及每份文件的删节说明，包括省略的图片、公式和表格。界面语言不会翻译法律正文。'),
'es':('Colección de legislación','Instantáneas parciales y no oficiales en su idioma original. No constituyen un corpus nacional completo ni certifican la vigencia. Consulte la fuente oficial, la edición y los avisos de omisiones, incluidas figuras, fórmulas y tablas. El idioma de la interfaz no traduce las leyes.')}
def sha(data):return hashlib.sha256(data).hexdigest()
def git_blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def readjson(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,data):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode('utf-8') if isinstance(data,str) else data)
def writejson(path,value):write(path,json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
def git(source,*args):return subprocess.check_output(['git','-C',str(source),*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode().strip()
def canonical(base,path):return urljoin(base,path[:-10] if path.endswith('index.html') else path)
def splitarticle(text):
 m=ARTICLE.search(text)
 if not m or ARTICLE.search(text,m.end()):raise ValueError('Expected exactly one article')
 return text[:m.start()],m.group(),text[m.end():]
def snippets(source):
 text=(Path(source)/'scripts/publisher-tags.mjs').read_text(encoding='utf-8')
 return {key:json.loads(re.search('export const '+key+r'=("(?:[^"\\]|\\.)*");',text).group(1)) for key in ['publisherHead','publisherBodyStart','publisherFooter']}
def sitemap(urls,index=False):
 kind='sitemapindex' if index else 'urlset';child='sitemap' if index else 'url'
 return '<?xml version="1.0" encoding="UTF-8"?>\n<'+kind+' xmlns="'+SITEMAP_NS+'">'+''.join('<'+child+'><loc>'+html.escape(url)+'</loc></'+child+'>' for url in urls)+'</'+kind+'>\n'
def valid_public_base(base):
 if not isinstance(base,str) or any(ord(c)<33 for c in base):return False
 try:p=urlsplit(base);port=p.port
 except ValueError:return False
 return bool(p.scheme=='https' and p.hostname and re.fullmatch(r'[A-Za-z0-9.-]+',p.hostname) and not p.username and not p.password and not port and not p.query and not p.fragment and re.fullmatch(r'/[A-Za-z0-9._~/-]+/',p.path) and '//' not in p.path and not any(x in ['.','..'] for x in p.path.split('/')) and p.netloc==p.hostname)
def files_digest(sites):
 root=Path(sites);hashes={p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
 return hashes,sha(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode())
def page(title,lang,url,content,snip,base):
 alternates=''.join('<link rel="alternate" hreflang="'+l+'" href="'+base+p+'">' for l,p in LANGS.items()) if url in [base+p for p in LANGS.values()] else ''
 labels={'ko':'한국어','en':'English','zh':'中文','es':'Español'}
 nav=' · '.join('<a lang="'+l+'" href="'+base+p+'">'+labels[l]+'</a>' for l,p in LANGS.items())
 return '<!doctype html><html lang="'+lang+'"><head>'+BANNER+'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><link rel="canonical" href="'+html.escape(url,quote=True)+'">'+alternates+'<link rel="stylesheet" href="'+base+'style.css">'+snip['publisherHead']+'</head><body>'+snip['publisherBodyStart']+'<header><a class="brand" href="'+base+'">NaNa Law Library</a><nav>'+nav+'</nav></header><main>'+content+'</main>'+MORE+snip['publisherFooter']+'</body></html>\n'
def assert_build_ready(*args,**kwargs):raise ValueError('Full split remains PAUSED; full builder and 2749/398 corpus are not restored')
if __name__=='__main__':raise SystemExit('PAUSED: only phase1 shared primitives recovered; no full split generation permitted')
