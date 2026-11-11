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

