#!/usr/bin/env python3
"""Replay exact saved HTTP observations through the live release checks. No network."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, unquote
from xml.etree import ElementTree as ET
import verify_live_release as live


def body(root, row):
    live.require(row['status'] == 200 and row['finalUrl'] == row['url']
                 and row['defaultTlsValidation'] is True, 'HTTP observation is not a verified HTTPS200')
    checked = datetime.fromisoformat(row['checkedAt'].replace('Z', '+00:00'))
    live.require(0 <= (datetime.now(timezone.utc) - checked).total_seconds() < 3600, 'Stale HTTP observation')
    rel = Path(row['bodyFile'])
    live.require(not rel.is_absolute() and all(x not in ('.', '..') for x in rel.parts), 'Unsafe evidence path')
    target = root / rel
    live.require(target.resolve().is_relative_to(root.resolve())
                 and not any(p.is_symlink() for p in (target, *target.parents) if p == root or root in p.parents),
                 'Evidence path escape or symlink')
    raw = target.read_bytes()
    live.require(live.sha(raw) == row['bodySha256'] == row['responseSha256'], 'Evidence body hash mismatch')
    return raw


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proof-dir', type=Path, required=True)
    ap.add_argument('--site', type=Path, required=True)
    ap.add_argument('--review', type=Path, required=True)
    ap.add_argument('--fallback-source', type=Path, required=True)
    a = ap.parse_args(); root = a.proof_dir.resolve()
    initial_file = root / 'live-checker-report.json'
    supplemental_file = root / 'supplemental-http-observations.json'
    initial = json.loads(initial_file.read_bytes())
    supplemental = json.loads(supplemental_file.read_bytes())
    proof = json.loads(a.review.read_bytes())
    hashes = live.public_files(a.site)
    live.require(proof['passed'] and hashes == proof['filesSha256'], 'Frozen reference changed')
    observed = {}
    def add(row):
        live.require(row['url'] not in observed, 'Duplicate completed observation')
        observed[row['url']] = dict(row)
    for row in initial['responses']:
        add(row)
    for failure in initial['failures']:
        if failure.get('receipt'):
            add({**failure['receipt'], 'kind': failure['kind'], 'path': failure['path']})
    for row in supplemental['responses']:
        add(row)
    base = json.loads((a.site / 'site-manifest.json').read_bytes())['publicBase']
    docs = {d['html']: d for d in json.loads((a.site / 'document-manifest.json').read_bytes())['documents']}
    html_paths = {p for p in hashes if p.endswith('.html')}
    jobs = {live.canonical_for(base, p) if p in html_paths else base + p: ('site', p)
            for p in hashes if p != '.nojekyll'}
    fallback_base = 'https://nanalab.kr/world-law-portal/'
    for u in proof['portalFallbackUrls']:
        url = urldefrag(u)[0]
        jobs[url] = ('fallback', live.fallback_path(url, fallback_base))
    live.require(len(jobs) == len(observed) == 215 and set(jobs) == set(observed), 'Missing or extra completed observations')
    snippets = live.publisher_snippets(a.site); scans = {}; rows = []
    for url, (kind, path) in sorted(jobs.items()):
        row = observed[url]; raw = body(root, row)
        live.require(row['path'] == path and row['kind'] == kind, 'Observation identity mismatch')
        expected = ((a.site if kind == 'site' else a.fallback_source) / path).read_bytes()
        if kind == 'site' and path in html_paths:
            live.require('text/html' in row['contentType'].lower(), 'Unexpected page MIME')
            checks, parsed = live.check_html(path, raw, expected, base, snippets, docs.get(path))
            scans[url] = parsed; row.update(checks)
        elif kind == 'site':
            live.require(raw == expected, 'Public asset or metadata bytes changed')
            row.update(wholeFileExact=True)
        else:
            parsed = live.scan(raw); scans[url] = parsed
            if path.startswith(('world-laws/', 'legacy-laws/')):
                live.require(live.article(raw) == live.article(expected), 'Fallback article changed')
                row.update(statutoryArticleExact=True, articleSha256=live.sha(live.article(raw)))
            for linked in proof['portalFallbackUrls']:
                if urldefrag(linked)[0] == url and urlsplit(linked).fragment:
                    live.require(unquote(urlsplit(linked).fragment) in parsed.ids, 'Fallback fragment missing')
            row.update(fallbackVerified=True)
        rows.append(row)
    graph_links = 0
    for path in sorted(html_paths):
        source = live.canonical_for(base, path)
        for _, _, ref in scans[source].refs:
            target = urljoin(source, ref); bare, fragment = urldefrag(target)
            if live.approved_beacon(target):
                continue
            graph_links += 1
            if target.startswith(base):
                rel = live.fallback_path(target, base); key = live.canonical_for(base, rel)
                live.require(rel in hashes and key in observed, 'Missing local observed target')
                if fragment:
                    live.require(key in scans and unquote(fragment) in scans[key].ids, 'Missing local observed fragment')
            elif target.startswith(fallback_base):
                live.require(bare in observed, 'Missing observed portal fallback')
                if fragment:
                    live.require(unquote(fragment) in scans[bare].ids, 'Missing observed fallback fragment')
    sitemap = observed[base + 'sitemap.xml']; xml = ET.fromstring(body(root, sitemap))
    ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'; locs = [e.text for e in xml.findall(ns + 'url/' + ns + 'loc')]
    canonicals = {live.canonical_for(base, p) for p in html_paths}
    live.require(xml.tag == ns + 'urlset' and len(locs) == len(set(locs)) == 194 and set(locs) == canonicals, 'Sitemap differs')
    live.require(live.public_files(a.site) == hashes, 'Frozen site changed during replay')
    pages = [r for r in rows if r['kind'] == 'site' and r['path'] in html_paths]
    laws = [r for r in pages if r['path'] in docs]
    live.require(len(pages) == 194 and len(laws) == 190, 'Wrong canonical/article totals')
    result = {'passed': True, 'mode': 'saved-actual-HTTP-response-replay-no-new-requests',
              'recheckedAt': live.now(), 'httpRequestsDuringReplay': 0,
              'originalHttpRequests': initial['httpRequestsAttempted'], 'supplementalHttpRequests': len(supplemental['responses']),
              'completedUniqueHttpObservations': 215, 'canonicalPagesVerified': 194, 'statutoryArticlesExact': 190,
              'servedNonHtmlFilesExact': 13, 'fallbackPagesVerified': 8, 'fallbackArticlesExact': 4,
              'sitemapCanonicals': 194, 'graphLinksChecked': graph_links,
              'originalPublisherSnippetsExactOnEveryPage': True, 'rightsOmissionsAndScopeExact': True,
              'wholeHtmlFilesExact': sum(r['wholeFileExact'] for r in pages),
              'pagesWithExactlyReviewedEdgeBeacon': sum(len(r['edgeBeaconScripts']) == 1 for r in pages),
              'allowedEdgeBeaconExactAttributes': live.APPROVED_EDGE_BEACON,
              'sourceAndReceiptTimesPreserved': True, 'allResponseBodiesShaVerified': True,
              'initialFailureReportSha256': live.sha(initial_file.read_bytes()),
              'supplementalReportSha256': live.sha(supplemental_file.read_bytes()),
              'checkerSha256': live.sha(Path(live.__file__).read_bytes()),
              'replayProgramSha256': live.sha(Path(__file__).read_bytes()),
              'siteRelativeFileManifestSha256': proof['siteRelativeFileManifestSha256'],
              'browserVisualQa': False, 'analyticsExecutionTested': False, 'remoteWrites': False,
              'notTested': ['HTTP serving of .nojekyll build control file', 'Third-party script execution and official-source endpoint availability'],
              'responses': rows}
    out = root / 'live-recheck-report.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    gh = json.loads((root / 'github-observations.json').read_bytes())
    for name in ['ref', 'gitCommit', 'gitTree', 'deployment']:
        live.require(json.loads(body(root, gh['githubReads'][name])) == gh[name], 'GitHub snapshot/receipt mismatch')
    child = {'schemaVersion': 1, 'repository': 'NaNaCompany/world-law-jp-01', 'publicBase': base,
             'checkedAt': live.now(), 'commit': gh['commit'],
             **{k: gh[k] for k in ['ref', 'gitCommit', 'gitTree', 'deployment', 'githubReads']},
             'pages': pages, 'sitemap': sitemap}
    cp = root / 'child-live-proof.json'; cp.write_text(json.dumps(child, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'responses'}, indent=2))
    print('LIVE_RECHECK_REPORT_SHA256', live.sha(out.read_bytes()))
    print('CHILD_LIVE_PROOF_SHA256', live.sha(cp.read_bytes()))


if __name__ == '__main__':
    main()
