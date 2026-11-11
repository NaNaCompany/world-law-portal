#!/usr/bin/env python3
"""Read-only HTTP verification of a reviewed static legal-text release.

Offline validation is the default. --live requires explicit deployment evidence.
No Git writes, browser execution, analytics requests, or remote state changes.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
import sys
from urllib.parse import unquote, urldefrag, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from xml.etree import ElementTree as ET


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def article(raw):
    matches = list(re.finditer(rb'<article\b[^>]*>.*?</article>', raw, re.S))
    require(len(matches) == 1, 'Expected exactly one statutory article')
    return matches[0].group()


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []
        self.canonical = []
        self.ids = []
        self.markers = []
        self.scripts = []
        self.duplicate_script_attrs = False

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and len(attrs) != len({k for k, _ in attrs}):
            self.duplicate_script_attrs = True
        attrs = dict(attrs)
        if tag == 'script':
            self.scripts.append(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-nana-publisher' in attrs:
            self.markers.append(attrs['data-nana-publisher'])
        if tag in {'a', 'link', 'script', 'iframe', 'img', 'source'}:
            for key in ('href', 'src'):
                if key in attrs:
                    self.refs.append((tag, key, attrs[key]))
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical.append(attrs.get('href'))


def scan(raw):
    result = Scan()
    result.feed(raw.decode('utf-8', errors='strict'))
    result.close()
    return result


def canonical_for(base, path):
    return base + (path[:-10] if path.endswith('index.html') else path)


APPROVED_EDGE_BEACON = {
    'type': 'module',
    'src': 'https://static.cloudflareinsights.com/beacon.min.js/vce701823e78c4301a35b7e07294d87301792088814092',
    'integrity': 'sha512-UKNk8GbxkABxKcXYuLkO16EleLGUkcvJWtpSNmExE0Too3ZaFAxTscNWEc1OdAv5/BikHawapSCaiD2XCmp+Bw==',
    'data-cf-beacon': '{"version":"2024.11.0","token":"9f3423bb0d034d91bbe1a12afeff2429","r":1,"spa":2}',
    'crossorigin': 'anonymous',
}


def approved_beacon(src):
    return src == APPROVED_EDGE_BEACON['src']


def shell_normalized(raw):
    """Allow only an additional external Cloudflare beacon and tag whitespace.

    Exact article bytes and publisher snippets are checked separately. This does
    not allow arbitrary third-party scripts, changed tags, text, or attributes.
    """
    allowed = []
    def remove(match):
        opening = match.group().split(b'>', 1)[0] + b'>'
        parsed = scan(opening)
        refs = [v for t, k, v in parsed.refs if t == 'script' and k == 'src']
        content = match.group().split(b'>', 1)[1].rsplit(b'</script>', 1)[0]
        if (len(refs) == 1 and approved_beacon(refs[0]) and not content.strip()
                and len(parsed.scripts) == 1
                and not parsed.duplicate_script_attrs
                and parsed.scripts[0] == APPROVED_EDGE_BEACON):
            allowed.append({'url': refs[0], 'sha256': sha(match.group())})
            return b''
        return match.group()
    raw = re.sub(rb'<script\b[^>]*>.*?</script>', remove, raw, flags=re.S)
    raw = re.sub(rb'<article\b[^>]*>.*?</article>', b'<article>EXACT-ARTICLE</article>', raw, flags=re.S)
    return re.sub(rb'>[\t\r\n ]+<', b'><', raw).strip(), allowed


def publisher_snippets(site):
    text = (site / 'scripts/publisher-tags.mjs').read_text('utf-8')
    result = {}
    for key in ('publisherHead', 'publisherBodyStart', 'publisherFooter'):
        matches = re.findall(r'export const ' + key + r'=("(?:[^"\\]|\\.)*");', text)
        require(len(matches) == 1, 'Publisher helper format differs: ' + key)
        result[key] = json.loads(matches[0]).encode()
    return result


def check_html(path, raw, expected, base, snippets, doc):
    actual = scan(raw)
    frozen = scan(expected)
    require(actual.canonical == [canonical_for(base, path)], 'Canonical mismatch')
    require(actual.ids == frozen.ids, 'Document fragment IDs changed')
    require(Counter(actual.markers) == Counter(frozen.markers)
            and len(actual.markers) == 6, 'Publisher marker mismatch')
    for key, snippet in snippets.items():
        require(raw.count(snippet) == 1, 'Publisher snippet changed: ' + key)
    require(raw.count(b'https://nanalab.kr/src_cdn/banner/astra.js') == 1,
            'Shared banner reference missing or duplicated')
    require(b'https://nanalab.kr/apps/' in raw, 'More Apps link missing')
    expected_shell, existing_beacons = shell_normalized(expected)
    actual_shell, injected = shell_normalized(raw)
    require(not existing_beacons, 'Reference unexpectedly already has an edge beacon')
    require(len(injected) <= 1, 'Multiple unexpected edge beacon scripts')
    require(actual_shell == expected_shell, 'Unexplained page shell change')
    filtered_refs = [r for r in actual.refs
                     if not (r[0] == 'script' and r[1] == 'src' and approved_beacon(r[2]))]
    require(filtered_refs == frozen.refs, 'Link or asset reference changed')
    result = {'path': path, 'canonical': actual.canonical[0],
              'wholeFileSha256': sha(raw), 'wholeFileExact': raw == expected,
              'canonicalVerified': True, 'publisherSnippetsExact': True,
              'shellVerified': True, 'edgeBeaconScripts': injected,
              'referenceCount': len(filtered_refs)}
    if doc is not None:
        body = article(raw)
        require(body == article(expected), 'Statutory article bytes changed')
        require(sha(body) == doc['articleSha256'], 'Article catalogue hash mismatch')
        match = re.match(rb'<article lang="ja" data-text-sha256="([a-f0-9]{64})">', body)
        require(match and match[1].decode() == doc['textSha256'], 'Retained text hash marker changed')
        require(b'not a complete-law or current-force certification' in raw,
                'Partial reproduction caveat missing')
        result.update(articleSha256=sha(body), statutoryArticleExact=True,
                      rightsProvenanceAndOmissionsExact=True,
                      retainedTextSha256=doc['textSha256'])
    return result, actual


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_https(url, timeout, max_bytes):
    require(urlsplit(url).scheme == 'https', 'HTTPS required')
    context = ssl.create_default_context()
    require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED,
            'Default TLS verification unavailable')
    opener = build_opener(HTTPSHandler(context=context), NoRedirect())
    request = Request(url, headers={'User-Agent': 'StaticReleaseVerifier/1.0',
                                   'Accept-Encoding': 'identity'})
    started = now()
    with opener.open(request, timeout=timeout) as response:
        require(response.status == 200, 'HTTP status ' + str(response.status))
        require(response.url == url, 'Unexpected response URL')
        require(response.headers.get('Content-Encoding', 'identity').lower() == 'identity',
                'Unexpected compressed transport despite identity request')
        body = response.read(max_bytes + 1)
        require(len(body) <= max_bytes, 'Response exceeded byte limit')
        receipt = {'url': url, 'status': response.status, 'finalUrl': response.url,
                   'startedAt': started, 'completedAt': now(), 'bytes': len(body),
                   'responseSha256': sha(body), 'defaultTlsVerified': True,
                   'redirectsFollowed': 0,
                   'contentType': response.headers.get('Content-Type'),
                   'etag': response.headers.get('ETag'),
                   'lastModified': response.headers.get('Last-Modified'),
                   'cacheStatus': response.headers.get('CF-Cache-Status'),
                   'cacheAge': response.headers.get('Age')}
        return body, receipt


def save_response_body(proof_dir, relative, raw):
    root = proof_dir.resolve()
    rel = Path(relative)
    require(not rel.is_absolute() and rel.parts and all(x not in ('.', '..') for x in rel.parts),
            'Unsafe response body path')
    target = root / rel
    require(target.resolve().is_relative_to(root), 'Response body path escapes proof directory')
    require(not any(p.is_symlink() for p in (target, *target.parents) if p == root or root in p.parents),
            'Symlink in response evidence path')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        output.write(raw)
    require(target.read_bytes() == raw, 'Saved response bytes differ')
    return {'bodyFile': rel.as_posix(), 'bodySha256': sha(raw)}


def public_files(site):
    require(not any(p.is_symlink() for p in site.rglob('*')), 'Symlinks unsupported')
    return {p.relative_to(site).as_posix(): sha(p.read_bytes())
            for p in sorted(site.rglob('*')) if p.is_file()}


def fallback_path(url, base):
    require(url.startswith(base), 'Fallback outside configured portal')
    path = unquote(urlsplit(url).path[len(urlsplit(base).path):])
    path += 'index.html' if not path or path.endswith('/') else ''
    require('..' not in Path(path).parts and not path.startswith('/'), 'Unsafe fallback path')
    return path


def run(args):
    started = now()
    proof_bytes = args.review.read_bytes()
    proof = json.loads(proof_bytes)
    require(proof['passed'] and proof['lawDocuments'] == 190 and proof['htmlPages'] == 194,
            'Independent reference proof incomplete')
    hashes = public_files(args.site)
    require(hashes == proof['filesSha256'] and len(hashes) == 208, 'Frozen public files changed')
    fingerprint = sha(compact(hashes))
    require(fingerprint == proof['siteRelativeFileManifestSha256'], 'Reference fingerprint changed')
    base = json.loads((args.site / 'site-manifest.json').read_bytes())['publicBase']
    require(urlsplit(base).scheme == 'https' and base.endswith('/'), 'Invalid HTTPS public base')
    catalogue = json.loads((args.site / 'additions-catalog.json').read_bytes())
    docs = {d['html']: d for d in catalogue['documents']}
    require(len(docs) == 190, 'Expected 190 unique law paths')
    html_paths = {p for p in hashes if p.endswith('.html')}
    require(len(html_paths) == 194 and set(docs) <= html_paths, 'Expected 194 HTML files')
    snippets = publisher_snippets(args.site)
    fallback_urls = sorted({urldefrag(u)[0] for u in proof['portalFallbackUrls']})
    fallback_base = args.fallback_base
    require(len(fallback_urls) == 8, 'Expected eight unique existing portal fallback URLs')
    for url in fallback_urls:
        require((args.fallback_source / fallback_path(url, fallback_base)).is_file(),
                'Missing fallback reference')
    if args.live:
        require(args.deployment_confirmed and re.fullmatch('[a-f0-9]{40}', args.deployed_commit or ''),
                '--live requires confirmed final main commit')
        run_url = urlsplit(args.pages_run_url or '')
        require(run_url.scheme == 'https' and run_url.netloc == 'github.com'
                and re.fullmatch(r'/[^/]+/[^/]+/actions/runs/[0-9]+', run_url.path),
                '--live requires successful Pages run URL supplied by deployment operator')
    # .nojekyll is a repository/build-control file, not a required HTTP resource.
    jobs = [('site', p, canonical_for(base, p) if p in html_paths else base + p)
            for p in sorted(hashes) if p != '.nojekyll']
    jobs += [('fallback', fallback_path(u, fallback_base), u) for u in fallback_urls]
    rows, scans, failures, response_map = [], {}, [], {}
    receipts = {}
    fallback_hashes = {u: sha((args.fallback_source / fallback_path(u, fallback_base)).read_bytes())
                       for u in fallback_urls}
    def work(job):
        kind, path, url = job
        expected = ((args.site if kind == 'site' else args.fallback_source) / path).read_bytes()
        if args.live:
            raw, receipt = fetch_https(url, args.timeout, max(16 * 1024 * 1024, len(expected) * 2))
        else:
            raw = expected
            receipt = {'url': url, 'offlineFixture': True, 'bytes': len(raw),
                       'responseSha256': sha(raw), 'defaultTlsVerified': False}
        if args.live and args.proof_dir is not None:
            receipt.update(save_response_body(args.proof_dir, 'bodies/' + kind + '/' + path, raw))
            receipt.update(defaultTlsValidation=receipt['defaultTlsVerified'], checkedAt=receipt['completedAt'])
        receipts[url] = receipt
        if kind == 'site' and path in html_paths:
            if args.live:
                require('text/html' in (receipt.get('contentType') or '').lower(), 'Unexpected HTML MIME')
            checks, parsed = check_html(path, raw, expected, base, snippets, docs.get(path))
        elif kind == 'site':
            require(raw == expected, 'Public non-HTML file bytes changed')
            checks = {'path': path, 'wholeFileExact': True, 'wholeFileSha256': sha(raw)}
            parsed = None
            if path.endswith('.json'):
                require(json.loads(raw) == json.loads(expected), 'JSON metadata differs')
        else:
            parsed = scan(raw)
            checks = {'path': path, 'fallbackVerified': True}
            if path.startswith(('world-laws/', 'legacy-laws/')):
                require(article(raw) == article(expected), 'Cross-country fallback article changed')
                checks.update(articleSha256=sha(article(raw)), statutoryArticleExact=True)
            for linked in proof['portalFallbackUrls']:
                if urldefrag(linked)[0] == url and urlsplit(linked).fragment:
                    require(unquote(urlsplit(linked).fragment) in parsed.ids, 'Fallback fragment missing')
        return kind, path, url, receipt, checks, parsed, raw if path == 'sitemap.xml' else None
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(work, job): job for job in jobs}
        for future in as_completed(pending):
            job = pending[future]
            try:
                kind, path, url, receipt, checks, parsed, raw = future.result()
                rows.append({'kind': kind, **receipt, **checks})
                response_map[url] = True
                if parsed is not None:
                    scans[url] = parsed
                if raw is not None:
                    sitemap = ET.fromstring(raw)
                    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
                    locs = [x.text for x in sitemap.findall(namespace + 'url/' + namespace + 'loc')]
                    require(sitemap.tag == namespace + 'urlset'
                            and len(locs) == len(set(locs)) == 194
                            and set(locs) == {canonical_for(base, p) for p in html_paths},
                            'Sitemap does not contain exact 194 canonicals')
            except Exception as exc:
                failures.append({'kind': job[0], 'path': job[1], 'url': job[2],
                                 'error': type(exc).__name__ + ': ' + str(exc),
                                 'httpStatus': getattr(exc, 'code', None),
                                 'receipt': receipts.get(job[2])})
    graph_errors = []
    for path in sorted(html_paths):
        url = canonical_for(base, path)
        if url not in scans:
            continue
        for _, _, ref in scans[url].refs:
            target = urljoin(url, ref)
            bare, fragment = urldefrag(target)
            if target.startswith(base):
                rel = fallback_path(target, base)
                canonical = canonical_for(base, rel)
                if rel not in hashes or not response_map.get(canonical):
                    graph_errors.append({'page': path, 'target': target, 'error': 'Local target not verified'})
                elif fragment and (canonical not in scans or unquote(fragment) not in scans[canonical].ids):
                    graph_errors.append({'page': path, 'target': target, 'error': 'Local fragment not verified'})
            elif target.startswith(fallback_base):
                if not response_map.get(bare):
                    graph_errors.append({'page': path, 'target': target, 'error': 'Fallback not verified'})
                elif fragment and unquote(fragment) not in scans[bare].ids:
                    graph_errors.append({'page': path, 'target': target, 'error': 'Fallback fragment not verified'})
    require(public_files(args.site) == hashes, 'Reference site changed during verification')
    require(args.review.read_bytes() == proof_bytes, 'Reference review changed during verification')
    require(all(sha((args.fallback_source / fallback_path(u, fallback_base)).read_bytes()) == h
                for u, h in fallback_hashes.items()), 'Fallback reference changed during verification')
    live = args.live
    html_rows = [r for r in rows if r['kind'] == 'site' and r['path'] in html_paths]
    law_rows = [r for r in html_rows if r['path'] in docs]
    fallback_rows = [r for r in rows if r['kind'] == 'fallback']
    result = {
        'passed': not failures and not graph_errors and len(rows) == len(jobs),
        'mode': 'live-read-only-https' if live else 'offline-fixture-no-network',
        'startedAt': started, 'completedAt': now(), 'httpRequestsAttempted': len(jobs) if live else 0,
        'siteRelativeFileManifestSha256': fingerprint, 'referenceReviewSha256': sha(proof_bytes),
        'checkerSha256': sha(Path(__file__).read_bytes()), 'frozenLocalReferenceFiles': len(hashes),
        'expectedHttpResources': len(jobs), 'verifiedResources': len(rows),
        'canonicalHtmlPagesVerified': len(html_rows), 'statutoryArticlesExact': len(law_rows),
        'nonHtmlPublicResourcesExact': len([r for r in rows if r['kind'] == 'site' and r['path'] not in html_paths]),
        'fallbackPagesVerified': len(fallback_rows),
        'fallbackStatutoryArticlesExact': len([r for r in fallback_rows if r.get('statutoryArticleExact')]),
        'wholeHtmlFilesExact': sum(r['wholeFileExact'] for r in html_rows),
        'htmlWithAllowedEdgeDifferences': [r['path'] for r in html_rows if not r['wholeFileExact']],
        'defaultTlsVerificationUsed': live, 'redirectsFollowed': 0,
        'allExpectedLocalAssetLinksAndFragmentsVerified': not graph_errors,
        'failures': sorted(failures, key=lambda r: r['url']), 'graphErrors': graph_errors,
        'deploymentEvidenceSupplied': {'finalMainCommit': args.deployed_commit,
                                       'successfulPagesRun': args.pages_run_url} if live else None,
        'deploymentEvidenceIndependentlyQueriedByThisProgram': False,
        'browserVisualQa': False, 'analyticsExecutionTested': False,
        'officialSourceRemoteAvailabilityTested': False,
        'notHttpTested': ['.nojekyll (repository build-control file)',
                         'Third-party scripts and official-source endpoints; links and original snippets are checked only'],
        'frozenPublicationState': json.loads((args.site / 'publication.json').read_bytes()).get('publicationState'),
        'localReferenceUnchanged': True, 'remoteWrites': False,
        'responseBodiesSaved': bool(live and args.proof_dir is not None),
        'responses': sorted(rows, key=lambda r: (r['kind'], r['url']))}
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'responses'}, ensure_ascii=False, indent=2))
    print('REPORT_SHA256', sha(args.report.read_bytes()))
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--fallback-source', type=Path, required=True)
    parser.add_argument('--fallback-base', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--proof-dir', type=Path, help='Local-only directory for exact observed HTTP response bytes')
    parser.add_argument('--live', action='store_true', help='Enable read-only HTTPS requests')
    parser.add_argument('--deployment-confirmed', action='store_true')
    parser.add_argument('--deployed-commit')
    parser.add_argument('--pages-run-url')
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    require(1 <= args.workers <= 4, 'Concurrency must be one to four')
    require(0 < args.timeout <= 180, 'Timeout must be positive and at most 180 seconds')
    require(urlsplit(args.fallback_base).scheme == 'https' and args.fallback_base.endswith('/'),
            'Fallback base must be HTTPS ending in /')
    report = args.report.resolve()
    for frozen in (args.site, args.fallback_source):
        require(not report.is_relative_to(frozen.resolve()), 'Report cannot be written inside a reference tree')
    require(report != args.review.resolve(), 'Report cannot overwrite its input proof')
    if args.proof_dir is not None:
        require(args.live, 'Response evidence persistence is only for actual live observations')
        root = args.proof_dir.resolve()
        require(report.parent == root, 'Report must be directly inside the response proof directory')
        for frozen in (args.site, args.fallback_source):
            require(not root.is_relative_to(frozen.resolve()) and not frozen.resolve().is_relative_to(root),
                    'Response evidence cannot overlap reference trees')
        args.proof_dir.mkdir(parents=True, exist_ok=True)
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
