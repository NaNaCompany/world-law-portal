#!/usr/bin/env python3
"""Read-only, fail-closed root JP190 transition verifier. Default: offline only.

Only exact pinned prepared files are references. Never writes a repository or
changes deployment state. Evidence is private and not a public upload artifact.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, Request, build_opener
from xml.etree import ElementTree as ET
sys.dont_write_bytecode = True
import edge_primitives as edge

REPOSITORY = 'NaNaCompany/world-law-portal'
BASE = 'https://nanalab.kr/world-law-portal/'
CHILD_BASE = 'https://nanalab.kr/world-law-jp-01/'
API = 'https://api.github.com/repos/' + REPOSITORY
BASELINE = '6d419490783ca01b2b70d12f8d999021c13734ec'
TARGET_TREE = 'd06e62db7178112f0be493b3c41e033171217938'
FINGERPRINT = 'f0e4fe50631bcb60287deb16231885034bc17f35e54e5437d02a86551960ccc4'
REVIEW_PIN = 'bec82c3a5ce0fa580a1d2dff8facc5efc61776c81ae34a35b72e27507993ca8a'
PLAN_PIN = '091e9e35e9c300f72958641783f784e88859056d283f2ac2d42c979b1872bfe0'
TRANSFER_REVIEW_PIN = '59b37bde67711454ddf90c2dc6f920f8a57420b0bb406db0ba604e9918583875'
NEW35_PIN = 'a506e7f5d569c1d10af385e5164b823f3443a659eccb70804a5d12c5de946aa2'
CANADA = 'legacy-laws/ca-acts-i-3.3.html'
CANADA_SHA256 = '6577e559acde5af045b4613efb1514efcc27f2b839a9a40090beb66887b5eb31'
LOCALES = ['index.html', 'en/index.html', 'zh/index.html', 'es/index.html']
METADATA = ['jp190-routes.json', 'publication.json', 'publisher-status.json',
            'collection-scope.json', 'additions-catalog.json', 'sitemap.xml', 'robots.txt']
COUNTRIES = {'BE': 1, 'CH': 11, 'IT': 2, 'LI': 2, 'US': 19}
sha = edge.sha
require = edge.require
now = edge.now
compact = edge.compact


def public_url(path):
    # Navigation requests use the canonical directory URL, without following
    # filename redirects. Law and metadata URLs keep their exact paths.
    return BASE + (path[:-10] if path.endswith('index.html') else path)


def pinned_json(path, expected):
    raw = path.read_bytes()
    require(sha(raw) == expected, 'Pinned input hash mismatch: ' + path.name)
    return json.loads(raw)


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def validate_live_gate(args):
    """Must run before any network call, including GitHub reads."""
    require(args.run_live, 'Explicit --run-live signal required')
    require(re.fullmatch('[0-9a-f]{40}', args.root_commit or '') is not None,
            'Explicit new root commit required')
    require(args.root_commit not in {BASELINE, '973e5914cc1a7b4887de97b3e22a04bf2586396b',
                                    '36f9a13ea6851e0257927a488a532bf178dd2d29'},
            'Root commit is not a new published root revision')
    require(isinstance(args.pages_run, int) and args.pages_run > 0,
            'Explicit successful root Pages run ID required')


def articles(raw):
    return re.findall(rb'<article\b[^>]*>.*?</article>', raw, re.S)


def check_html(path, raw, expected, snippets):
    """Preserve every article byte; allow only the established edge shell delta."""
    frozen, actual = edge.scan(expected), edge.scan(raw)
    require(len(frozen.canonical) == 1 and actual.canonical == frozen.canonical,
            'Canonical mismatch: ' + path)
    require(actual.ids == frozen.ids, 'Fragment IDs changed: ' + path)
    require(Counter(actual.markers) == Counter(frozen.markers) and len(actual.markers) == 6,
            'Publisher markers changed: ' + path)
    for key, snippet in snippets.items():
        require(raw.count(snippet) == expected.count(snippet) == 1,
                'Publisher snippet mismatch: ' + key)
    require(raw.count(b'https://nanalab.kr/src_cdn/banner/astra.js') == 1,
            'Shared banner missing/duplicated')
    require(b'https://nanalab.kr/apps/' in raw, 'More Apps link missing')
    actual_articles, frozen_articles = articles(raw), articles(expected)
    require(actual_articles == frozen_articles, 'Legal article bytes changed: ' + path)
    expected_shell, existing = edge.shell_normalized(expected)
    actual_shell, added = edge.shell_normalized(raw)
    require(not existing, 'Reference already contains an edge beacon')
    require(len(added) <= 1, 'Duplicate edge beacon')
    require(actual_shell == expected_shell, 'Unexplained HTML shell change: ' + path)
    refs = [r for r in actual.refs if not (r[0] == 'script' and r[1] == 'src'
                                          and edge.approved_beacon(r[2]))]
    require(refs == frozen.refs, 'Reference sequence changed: ' + path)
    return {'path': path, 'canonical': actual.canonical[0], 'wholeFileSha256': sha(raw),
            'wholeFileExact': raw == expected, 'publisherSnippetsExact': True,
            'articleBytesExact': True, 'articleSha256': [sha(x) for x in actual_articles],
            'edgeBeaconScripts': added, 'shellVerified': True}


def redirect_script(raw, route):
    target = route['canonicalUrl']
    require(target == CHILD_BASE + route['oldPath'], 'Unexpected child destination')
    require(edge.scan(raw).canonical == [target], 'JP190 canonical mismatch')
    require(b'<meta name="nana-jp190-redirect" content="true">' in raw,
            'JP190 redirect marker missing')
    require(('<noscript><meta http-equiv="refresh" content="0;url=' + target +
             '"></noscript>').encode() in raw, 'No-script refresh missing')
    require(('<a id="relocated-law" href="' + target + '">').encode() in raw,
            'Visible canonical redirect missing')
    require(not articles(raw), 'Old JP190 path still has a legal article')
    matches = re.findall(rb'<script id="jp190-redirect">(.*?)</script>', raw, re.S)
    require(len(matches) == 1, 'Missing/duplicate JP190 redirect script')
    expected = ('const destination=new URL(' + json.dumps(target) +
                ');destination.search=window.location.search;destination.hash=window.location.hash;'
                'const visible=document.getElementById("relocated-law");'
                'if(visible)visible.href=destination.href;window.location.replace(destination.href);')
    require(matches[0].decode() == expected, 'Redirect query/hash logic changed')
    return {'path': route['oldPath'], 'target': target, 'script': expected}


def check_new_law(raw, row, doc):
    body = articles(raw)
    require(len(body) == 1 and sha(body[0]) == row['articleSha256'], 'New35 article hash mismatch')
    match = re.fullmatch(rb'<article lang="[a-z-]+" data-text-sha256="([a-f0-9]{64})">'
                         rb'<div class="source-page" data-source-page="1">(.*)</div></article>',
                         body[0], re.S)
    require(match is not None, 'Unexpected new35 article shape')
    text = match[2].decode('utf-8').replace('&#39;', "'").replace('&quot;', '"')
    text = text.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
    require(sha(text.encode()) == match[1].decode() == row['textSha256'] == doc['textSha256'],
            'New35 retained text hash mismatch')
    require(len(text.encode('utf-16-le')) // 2 == doc['characters'], 'New35 character count mismatch')
    require(row['sourceSha256'] == doc['sourceSha256'], 'New35 source hash record mismatch')
    for label, value in [('Source', row['sourceSha256']), ('Text', row['textSha256'])]:
        require(('<dt>' + label + ' SHA-256</dt><dd class="hash">' + value + '</dd>').encode()
                in raw, 'New35 visible ' + label + ' hash missing')
    require(not re.search(rb'<(?:img|svg|math|table|object|embed|iframe|script)\b', body[0], re.I),
            'Disallowed element in legal body')
    return {'id': row['id'], 'country': row['country'], 'sourceSha256': row['sourceSha256'],
            'textSha256': row['textSha256'], 'articleSha256': row['articleSha256'],
            'sourceHashScope': 'Published provenance matches pinned source audit; no source-site refetch',
            'retainedTextRecomputed': True, 'characters': doc['characters']}


def check_index(path, raw, routes, new35):
    text = raw.decode('utf-8')
    cards = re.findall(r'<div class="document">.*?</div>', text, re.S)
    selected = []
    for r in routes:
        matching = [c for c in cards if 'href="' + r['canonicalUrl'] + '"' in c]
        require(len(matching) == 1, 'Missing/duplicate JP190 card in ' + path + ': ' + r['id'])
        require('Partial text reproduction' in matching[0] and 'Structural review pending' in matching[0],
                'JP190 partial/review caveat missing in locale card')
        selected.append(r['id'])
    all_child = [r for r in edge.scan(raw).refs if r[0] == 'a' and r[1] == 'href'
                 and r[2].startswith(CHILD_BASE + 'world-laws/')]
    require(len(all_child) == 190, 'Locale child-card count differs')
    links = [urljoin(BASE + path, r[2]) for r in edge.scan(raw).refs if r[:2] == ('a', 'href')]
    for d in new35:
        require(links.count(BASE + d['html']) == 1, 'New35 locale card missing/duplicated')
    return {'path': path, 'jp190Cards': len(selected), 'new35Cards': len(new35),
            'partialAndReviewCaveats': True}


def check_sitemap(raw, routes, new35):
    tree = ET.fromstring(raw)
    urls = [x.text for x in tree.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/'
                                       '{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    require(len(urls) == len(set(urls)) == 2522, 'Root sitemap must have 2522 unique URLs')
    require(all(u.startswith(BASE) for u in urls), 'Child/outside URL in root sitemap')
    require(not set(r['oldUrl'] for r in routes).intersection(urls), 'Old190 redirect remains in sitemap')
    require(all(BASE + d['html'] in urls for d in new35), 'New35 sitemap omission')
    return {'uniqueUrls': 2522, 'old190Excluded': True, 'new35Included': True}


def check_metadata(bodies, routes):
    route = json.loads(bodies['jp190-routes.json'])
    publication = json.loads(bodies['publication.json'])
    status = json.loads(bodies['publisher-status.json'])
    scope = json.loads(bodies['collection-scope.json'])
    catalog = json.loads(bodies['additions-catalog.json'])
    counts = {'localLawDocuments': 2517, 'externalJp190Documents': 190,
              'aggregateLawDocuments': 2707, 'localAdditionsCatalogDocuments': 166,
              'externalAdditionsCatalogDocuments': 190, 'aggregateAdditionsCatalogDocuments': 356,
              'localCanonicalPages': 2522, 'localHtmlPages': 8340,
              'localRedirectPages': 5818, 'koreanRedirects': 5628, 'localNavigationPages': 5}
    require(route['routes'] == routes and route['counts'] == counts, 'Routing metadata mismatch')
    require(route['routingMode'] == 'partial-jp190-external', 'Wrong routing mode')
    require('not an HTTP301' in route['redirectType'], 'Redirect type misrepresented')
    for k, v in counts.items():
        require(publication[k] == v, 'Publication count mismatch: ' + k)
    for obj in (route, publication, status):
        require(obj['fullSplitComplete'] is False, 'Full split improperly claimed')
    require(publication['collectionComplete'] is False and status['complete'] is False
            and scope['complete'] is False, 'Collection completion improperly claimed')
    receipt = route['childDeploymentReceipt']
    require(receipt == publication['jp190ChildDeploymentReceipt'], 'Child receipt inconsistent')
    require(receipt['commit'] == '36f9a13ea6851e0257927a488a532bf178dd2d29'
            and receipt['tree'] == 'b5359ee1b2ca5cd97201da2879fd81d3eb38719f'
            and receipt['runId'] == 42935597218, 'Pinned live child changed')
    require(len(catalog['documents']) == 356 and catalog['localDocuments'] == 166
            and catalog['externalDocuments'] == 190, 'Catalog counts inconsistent')
    return {'partialTransition': True, 'fullSplitComplete': False, 'counts': counts,
            'childCommit': receipt['commit'], 'childPagesRun': receipt['runId']}


def runtime_check(scripts):
    proc = subprocess.run(['node', str(Path(__file__).with_name('test_redirect_runtime.mjs'))],
                          input=json.dumps(scripts), text=True, capture_output=True, timeout=120)
    require(proc.returncode == 0, 'Redirect runtime test failed: ' + proc.stderr[:500])
    result = json.loads(proc.stdout)
    require(result['passed'] and result['redirects'] == len(scripts), 'Runtime count mismatch')
    return result


def validate_tree(tree, expected, sizes=None):
    require(tree.get('truncated') is False, 'Git tree is truncated or lacks truncation status')
    require(tree.get('sha') == TARGET_TREE, 'Wrong remote Git root tree')
    entries = tree.get('tree', [])
    require(len({e['path'] for e in entries}) == len(entries), 'Duplicate remote tree paths')
    require(all(e['type'] in ('blob', 'tree') for e in entries), 'Unexpected submodule/type')
    actual = [{k: e[k] for k in ('path', 'mode', 'type', 'sha')}
              for e in entries if e['type'] == 'blob']
    require(sorted(actual, key=lambda e: e['path']) == sorted(expected, key=lambda e: e['path']),
            'Complete remote blob map differs from prepared target')
    if sizes is not None:
        require({e['path']: e.get('size') for e in entries if e['type'] == 'blob'} == sizes,
                'Remote Git blob byte sizes differ from prepared files')
    required_dirs = {str(p) for e in expected for p in Path(e['path']).parents if str(p) != '.'}
    actual_dirs = {e['path'] for e in entries if e['type'] == 'tree'}
    require(actual_dirs == required_dirs, 'Remote directory map differs')
    require(all(e['mode'] == '040000' for e in entries if e['type'] == 'tree'), 'Wrong directory mode')
    return {'allFilesMatched': len(actual), 'unchangedFilesMatched': 8160,
            'remoteTree': TARGET_TREE, 'truncated': False}


def validate_ref(data, commit):
    require(data.get('ref') == 'refs/heads/main' and data.get('object', {}).get('type') == 'commit'
            and data['object']['sha'] == commit, 'Remote main differs from supplied root commit')


def validate_commit(data, commit):
    require(data.get('sha') == commit and data.get('tree', {}).get('sha') == TARGET_TREE,
            'Root commit/tree binding mismatch')
    require([p['sha'] for p in data.get('parents', [])] == [BASELINE], 'Unexpected root commit parent')


def validate_run(data, commit, run):
    require(data.get('id') == run and data.get('head_sha') == commit and data.get('head_branch') == 'main',
            'Pages run/revision binding mismatch')
    require(data.get('repository', {}).get('full_name') == REPOSITORY, 'Wrong Pages repository')
    require(data.get('status') == 'completed' and data.get('conclusion') == 'success',
            'Pages run did not complete successfully')
    require(data.get('name') == 'pages build and deployment'
            and data.get('path') == 'dynamic/pages/pages-build-deployment', 'Unexpected Pages workflow')


def prepare(args):
    review = pinned_json(args.review, REVIEW_PIN)
    plan = pinned_json(args.plan, PLAN_PIN)
    transfer = pinned_json(args.transfer_review, TRANSFER_REVIEW_PIN)
    new35 = pinned_json(args.new35, NEW35_PIN)
    require(review['passed'] and transfer['passed'] and new35['passed'], 'Independent review failed')
    require(plan['finalTree'] == transfer['finalTree'] == TARGET_TREE, 'Target tree pin mismatch')
    require(transfer['planSha256'] == PLAN_PIN, 'Transfer review does not bind exact plan')
    require(review['fileCount'] == 8367 and review['siteBytes'] == 559970945,
            'Prepared reference counts differ')
    require(new35['countries'] == COUNTRIES and len(new35['documents']) == 35, 'New35 country count differs')
    require(not any(p.is_symlink() for p in args.site.rglob('*')), 'Prepared symlinks forbidden')
    paths = {p.relative_to(args.site).as_posix(): p for p in args.site.rglob('*') if p.is_file()}
    require(set(paths) == set(review['filesSha256']) and len(paths) == 8367, 'Prepared file paths differ')
    hashes, blobs, sizes = {}, {}, {}
    for rel, path in sorted(paths.items()):
        raw = path.read_bytes()
        hashes[rel], blobs[rel], sizes[rel] = sha(raw), git_blob(raw), len(raw)
    require(hashes == review['filesSha256'], 'Prepared full map changed')
    require(sha(compact(hashes)) == review['siteFileManifestSha256'] == FINGERPRINT,
            'Prepared fingerprint changed')
    require(sum(sizes.values()) == 559970945, 'Prepared byte total changed')
    require(len(plan['finalFiles']) == len({e['path'] for e in plan['finalFiles']}) == 8367,
            'Final Git map incomplete/duplicated')
    require({e['path']: e['sha'] for e in plan['finalFiles']} == blobs
            and all(e['mode'] == '100644' and e['type'] == 'blob' for e in plan['finalFiles']),
            'Prepared Git blob map changed')
    require(hashes[CANADA] == CANADA_SHA256, 'Retained large Canada file changed')
    changed = set(review['contentChecks']['changedFiles']) | set(review['contentChecks']['addedFiles'])
    require(len(changed) == 207 and len(set(paths) - changed) == 8160, 'Conservation counts differ')
    route_data = json.loads(paths['jp190-routes.json'].read_bytes())
    routes = route_data['routes']
    require(len(routes) == len({r['oldPath'] for r in routes}) == 190, 'Expected exactly190 routes')
    docs = {d['id']: d for d in json.loads(paths['additions-catalog.json'].read_bytes())['documents']}
    snippets = edge.publisher_snippets(args.site)
    non_target_jp = sorted(p for p in paths if p.startswith('world-laws/jp-')
                           and p not in {r['oldPath'] for r in routes})
    require(len(non_target_jp) == 400, 'Expected 400 unchanged non-target Japanese laws')
    kr = sorted(p for p in paths if p.startswith('kr/laws/') and p.endswith('.html'))
    require(len(kr) == 5628, 'Expected 5628 inherited KR redirects')
    # Includes both KR repository classes, the complete large Canadian body, a
    # second Canadian page, and two non-target Japanese documents.
    kr_samples = []
    for child in ('world-law-kr-acts', 'world-law-kr-orders'):
        found = next(p for p in kr if ('https://nanalab.kr/' + child + '/').encode() in paths[p].read_bytes())
        kr_samples.append(found)
    second_ca = next(p for p in sorted(paths) if p.startswith('legacy-laws/ca-') and p != CANADA)
    samples = kr_samples + [CANADA, second_ca, non_target_jp[0], non_target_jp[-1]]
    require(not set(samples).intersection(changed), 'Unchanged sample is in change set')
    selected = sorted(set([r['oldPath'] for r in routes] + [d['html'] for d in new35['documents']]
                          + LOCALES + METADATA + ['kr/index.html', 'style.css'] + samples))
    require(len(selected) < 260, 'HTTP plan grew unexpectedly')
    bodies = {p: paths[p].read_bytes() for p in selected}
    checked = check_bodies(bodies, bodies, routes, new35['documents'], docs, snippets, samples)
    checked['redirectRuntime'] = runtime_check([redirect_script(bodies[r['oldPath']], r) for r in routes])
    return {'review': review, 'plan': plan, 'routes': routes, 'new35': new35['documents'],
            'docs': docs, 'snippets': snippets, 'samples': samples, 'selected': selected,
            'expected': bodies, 'sizes': sizes, 'offlineChecks': checked,
            'fullMapSummary': {'files': 8367, 'bytes': 559970945, 'fingerprint': FINGERPRINT,
                               'gitTree': TARGET_TREE, 'unchangedFiles': 8160}}


def check_bodies(bodies, expected, routes, new35, docs, snippets, samples):
    html_results = []
    for path in sorted(bodies):
        if path.endswith('.html'):
            html_results.append(check_html(path, bodies[path], expected[path], snippets))
        else:
            require(bodies[path] == expected[path], 'Published non-HTML bytes differ: ' + path)
    redirects = [redirect_script(bodies[r['oldPath']], r) for r in routes]
    laws = [check_new_law(bodies[r['html']], r, docs[r['id']]) for r in new35]
    indexes = [check_index(p, bodies[p], routes, new35) for p in LOCALES]
    return {'html': html_results, 'jp190Redirects': len(redirects), 'redirectKind': 'HTML, not HTTP301',
            'newlyExposed35': laws, 'localeIndexes': indexes,
            'sitemap': check_sitemap(bodies['sitemap.xml'], routes, new35),
            'metadata': check_metadata(bodies, routes), 'unchangedHttpSamples': samples,
            'browserVisualQa': False, 'analyticsRequestsExecuted': False}


def output_dir(name):
    require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*', name) is not None, 'Unsafe evidence directory name')
    root = Path(__file__).resolve().parent
    target = root / name
    require(not target.exists() and not target.is_symlink(), 'Evidence directory already exists')
    target.mkdir(mode=0o700)
    return target


def write_json(path, value):
    with path.open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write('\n')


def get_and_save(url, relative, root, allowed, timeout=45, max_bytes=32 * 1024 * 1024):
    require(url in allowed and urlsplit(url).scheme == 'https', 'URL outside exact GET allowlist')
    context = ssl.create_default_context()
    require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED, 'TLS verification disabled')
    opener = build_opener(HTTPSHandler(context=context), edge.NoRedirect())
    started = now()
    receipt = {'url': url, 'method': 'GET', 'startedAt': started, 'freshNetworkRequest': True,
               'defaultTlsValidationConfigured': True, 'defaultTlsVerified': False, 'redirectsFollowed': 0}
    try:
        request = Request(url, headers={'User-Agent': 'NaNaRoot190Verifier/1.0', 'Accept-Encoding': 'identity',
                                        'Accept': 'application/json' if url.startswith(API) else '*/*'})
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(max_bytes + 1)
            receipt.update(status=response.code, finalUrl=response.url, checkedAt=now(), defaultTlsVerified=True,
                           completedAt=now(), bytes=len(raw), responseSha256=sha(raw),
                           contentType=response.headers.get('Content-Type'), etag=response.headers.get('ETag'),
                           lastModified=response.headers.get('Last-Modified'), cacheAge=response.headers.get('Age'),
                           cacheStatus=response.headers.get('CF-Cache-Status'),
                           contentEncoding=response.headers.get('Content-Encoding', 'identity'),
                           overByteLimit=len(raw) > max_bytes)
        receipt.update(edge.save_response_body(root, relative, raw))
        write_json(root / (relative + '.receipt.json'), receipt)
        require(receipt['status'] == 200, 'HTTP status ' + str(receipt['status']) + ': ' + url)
        require(receipt['finalUrl'] == url and not receipt['overByteLimit'], 'Unexpected URL/oversize response')
        require(receipt['contentEncoding'].lower() == 'identity', 'Unexpected content encoding')
        return raw, receipt
    except Exception as exc:
        failure = {**receipt, 'checkedAt': now(), 'failure': str(exc)}
        error_path = root / (relative + '.error.json')
        error_path.parent.mkdir(parents=True, exist_ok=True)
        if not error_path.exists():
            write_json(error_path, failure)
        raise


def live(args, prepared, out):
    validate_live_gate(args)
    github = {'ref-before': API + '/git/ref/heads/main',
              'commit': API + '/git/commits/' + args.root_commit,
              'tree': API + '/git/trees/' + TARGET_TREE + '?recursive=1',
              'pages-run': API + '/actions/runs/' + str(args.pages_run)}
    allowed = set(github.values()) | {public_url(p) for p in prepared['selected']}
    observations = {}
    for key, url in github.items():
        raw, receipt = get_and_save(url, 'github/' + key + '.json', out, allowed)
        data = json.loads(raw)
        observations[key] = receipt
        if key == 'ref-before': validate_ref(data, args.root_commit)
        elif key == 'commit': validate_commit(data, args.root_commit)
        elif key == 'tree': observations['treeCheck'] = validate_tree(data, prepared['plan']['finalFiles'], prepared['sizes'])
        elif key == 'pages-run': validate_run(data, args.root_commit, args.pages_run)
    # No public-site request happens before exact commit/tree/Pages success binding.
    bodies, receipts, errors = {}, {}, []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(get_and_save, public_url(p), 'http/' + p, out, allowed): p
                   for p in prepared['selected']}
        for future in as_completed(pending):
            path = pending[future]
            try:
                bodies[path], receipts[path] = future.result()
            except Exception as exc:
                errors.append({'path': path, 'error': str(exc)})
    write_json(out / 'http-observations.json', {'receipts': receipts, 'errors': errors})
    require(not errors, 'HTTP GET failures; exact bodies/receipts retained in this evidence directory')
    checks = check_bodies(bodies, prepared['expected'], prepared['routes'], prepared['new35'],
                          prepared['docs'], prepared['snippets'], prepared['samples'])
    checks['redirectRuntime'] = runtime_check([redirect_script(bodies[r['oldPath']], r)
                                             for r in prepared['routes']])
    raw, receipt = get_and_save(github['ref-before'], 'github/ref-after.json', out, allowed)
    validate_ref(json.loads(raw), args.root_commit)
    observations['ref-after'] = receipt
    write_json(out / 'github-observations.json', observations)
    return {'passed': True, 'mode': 'live-actual-GET', 'checkedAt': now(), 'rootCommit': args.root_commit,
            'rootTree': TARGET_TREE, 'pagesRun': args.pages_run,
            'pagesRunUrl': 'https://github.com/' + REPOSITORY + '/actions/runs/' + str(args.pages_run),
            'fullMap': prepared['fullMapSummary'], 'freshHttpGetCount': len(receipts),
            'githubSnapshotCount': 5, 'checks': checks, 'externalWrites': False,
            'scope': 'JP190 relocation/correction and separate new35 publication; not a completed full split'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--transfer-review', type=Path, required=True)
    p.add_argument('--new35', type=Path, required=True)
    p.add_argument('--output', required=True, help='New private evidence subdirectory name next to checker')
    p.add_argument('--run-live', action='store_true', help='Explicit post-publication signal; never inferred')
    p.add_argument('--root-commit')
    p.add_argument('--pages-run', type=int)
    p.add_argument('--workers', type=int, default=4, choices=range(1, 9))
    return p


def main():
    args = parser().parse_args()
    out = None
    try:
        if args.run_live: validate_live_gate(args)
        prepared = prepare(args)
        out = output_dir(args.output)
        write_json(out / 'request-plan.json', {'mode': 'live' if args.run_live else 'offline',
                   'publicBase': BASE, 'paths': prepared['selected'],
                   'urlsByPath': {p: public_url(p) for p in prepared['selected']},
                   'httpGetCount': len(prepared['selected']), 'allGitFiles': 8367,
                   'unchangedGitFiles': 8160, 'fullMap': prepared['fullMapSummary']})
        if args.run_live:
            result = live(args, prepared, out)
        else:
            result = {'passed': True, 'mode': 'offline-only', 'checkedAt': now(),
                      'networkRequests': 0, 'externalWrites': False,
                      'rootCommit': None, 'pagesRun': None, 'rootDeployed': False,
                      'fullMap': prepared['fullMapSummary'], 'plannedHttpGetCount': len(prepared['selected']),
                      'checks': prepared['offlineChecks']}
        write_json(out / 'report.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))
        return 0
    except Exception as exc:
        failure = {'passed': False, 'checkedAt': now(), 'mode': 'live' if args.run_live else 'offline',
                   'error': str(exc), 'externalWrites': False}
        if out is not None and not (out / 'failure.json').exists(): write_json(out / 'failure.json', failure)
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
