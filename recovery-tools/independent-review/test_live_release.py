#!/usr/bin/env python3
"""Hermetic adversarial tests for the read-only live release checker."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import verify_live_release as checker

BASE = 'https://example.org/library/'
PATH = 'laws/test.html'
TEXT_HASH = '1' * 64
BODY = ('<article lang="ja" data-text-sha256="' + TEXT_HASH + '">'
        '<div data-ja=\'{"Flag":"A"}\'><span data-jl="0">甲&#13;乙</span>'
        '<p class="omission">Table omitted at /children/0</p></div></article>').encode()
SNIPPETS = {
    'head': b'<script data-nana-publisher="adsense"></script><script data-nana-publisher="gtm"></script><script data-nana-publisher="ga4-loader"></script><script data-nana-publisher="ga4-config"></script>',
    'body': b'<noscript data-nana-publisher="gtm-noscript"></noscript>',
    'footer': b'<script data-nana-publisher="cloudflare-fallback"></script>',
}
RAW = (b'<!doctype html><html><head><title>Test</title><link rel="canonical" href="' + (BASE + PATH).encode() +
       b'"><link rel="stylesheet" href="../style.css"><script defer src="https://nanalab.kr/src_cdn/banner/astra.js"></script>' +
       SNIPPETS['head'] + b'</head><body>' + SNIPPETS['body'] +
       b'<header id="header">Header</header><main><h1>Law</h1><p>Rights: source</p>'
       b'<p>not a complete-law or current-force certification</p>' + BODY +
       b'</main><a href="https://nanalab.kr/apps/">More Apps</a>' + SNIPPETS['footer'] + b'</body></html>\n')
DOC = {'articleSha256': checker.sha(BODY), 'textSha256': TEXT_HASH}
BEACON = ('<script type="module" src="' + checker.APPROVED_EDGE_BEACON['src'] +
          '" integrity="' + checker.APPROVED_EDGE_BEACON['integrity'] +
          '" data-cf-beacon=\'' + checker.APPROVED_EDGE_BEACON['data-cf-beacon'] +
          '\' crossorigin="anonymous"></script>').encode()



class Checks(unittest.TestCase):
    def verify(self, raw=RAW, doc=DOC):
        return checker.check_html(PATH, raw, RAW, BASE, SNIPPETS, doc)[0]

    def reject(self, raw):
        with self.assertRaises(ValueError):
            self.verify(raw)

    def test_exact(self):
        self.assertTrue(self.verify()['statutoryArticleExact'])
        self.assertTrue(self.verify()['wholeFileExact'])

    def test_only_known_beacon_addition(self):
        raw = RAW.replace(b'</body>', BEACON + b'</body>')
        result = self.verify(raw)
        self.assertFalse(result['wholeFileExact'])
        self.assertEqual(len(result['edgeBeaconScripts']), 1)

    def test_intertag_whitespace_outside_article(self):
        self.verify(RAW.replace(b'</head><body>', b'</head>\r\n<body>'))

    def test_legal_text_mutation(self):
        self.reject(RAW.replace('甲'.encode(), '丙'.encode()))

    def test_article_whitespace_even_if_dom_equivalent(self):
        self.reject(RAW.replace(b'</span><p', b'</span> <p'))

    def test_attribute_mutation(self):
        self.reject(RAW.replace(b'"Flag":"A"', b'"Flag":"B"'))

    def test_omission_notice_mutation(self):
        self.reject(RAW.replace(b'Table omitted', b'Table provided'))

    def test_rights_mutation(self):
        self.reject(RAW.replace(b'Rights: source', b'Rights: changed'))

    def test_canonical_mutation(self):
        self.reject(RAW.replace((BASE + PATH).encode(), b'https://example.org/other.html'))

    def test_duplicate_canonical(self):
        self.reject(RAW.replace(b'</head>', b'<link rel="canonical" href="https://example.org/other"></head>'))

    def test_missing_publisher_snippet(self):
        self.reject(RAW.replace(SNIPPETS['head'], b''))

    def test_changed_original_script(self):
        self.reject(RAW.replace(b'"cloudflare-fallback"></script>', b'"cloudflare-fallback">bad()</script>'))

    def test_asset_link_changed(self):
        self.reject(RAW.replace(b'../style.css', b'../other.css'))

    def test_header_removed(self):
        self.reject(RAW.replace(b'<header id="header">Header</header>', b''))

    def test_unknown_script(self):
        self.reject(RAW.replace(b'</body>', b'<script src="https://example.org/unknown.js"></script></body>'))

    def test_beacon_spoofed_host(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'insights.com', b'insights.com.evil.test') + b'</body>'))

    def test_beacon_http(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'https:', b'http:') + b'</body>'))

    def test_beacon_inline_code(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'></script>', b'>bad()</script>') + b'</body>'))

    def test_beacon_event_attribute(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'<script ', b'<script onload="bad()" ') + b'</body>'))

    def test_beacon_inside_article(self):
        self.reject(RAW.replace(b'</article>', BEACON + b'</article>'))

    def test_unreviewed_beacon_version(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'vce701', b'vother') + b'</body>'))

    def test_unreviewed_beacon_type(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'type="module"', b'type="text/javascript"') + b'</body>'))

    def test_unreviewed_beacon_integrity(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'sha512-UKNk', b'sha512-wrong') + b'</body>'))

    def test_unreviewed_beacon_token(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'9f3423bb', b'aaaaaaaa') + b'</body>'))

    def test_missing_beacon_attribute(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b' crossorigin="anonymous"', b'') + b'</body>'))

    def test_duplicate_beacon_attributes(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'<script ', b'<script src="https://bad.example/evil.js" ') + b'</body>'))

    def test_duplicate_beacon(self):
        self.reject(RAW.replace(b'</body>', BEACON + BEACON + b'</body>'))

    def test_corrupt_article_catalogue_hash(self):
        with self.assertRaises(ValueError):
            self.verify(doc={**DOC, 'articleSha256': '0' * 64})

    def test_corrupt_retained_text_pin(self):
        with self.assertRaises(ValueError):
            self.verify(doc={**DOC, 'textSha256': '0' * 64})

    def test_no_redirect_following(self):
        self.assertIsNone(checker.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.org/'))

    def test_plain_http_fails_before_network(self):
        with patch.object(checker, 'build_opener', side_effect=AssertionError('Network was reached')):
            with self.assertRaisesRegex(ValueError, 'HTTPS required'):
                checker.fetch_https('http://example.org/', 10, 100)

    def test_unsafe_fallback_path(self):
        with self.assertRaises(ValueError):
            checker.fallback_path(BASE + '%2e%2e/secret', BASE)

    def test_unknown_bytes_not_silently_decoded(self):
        self.reject(RAW.replace(b'Header', b'Header\xff'))


class BodyPersistence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_non_utf8_response_bytes(self):
        raw = b'<html>exact\r\nbytes\xff</html>'
        receipt = checker.save_response_body(self.root, 'bodies/site/index.html', raw)
        self.assertEqual((self.root / receipt['bodyFile']).read_bytes(), raw)
        self.assertEqual(receipt['bodySha256'], checker.sha(raw))

    def test_refuse_overwrite(self):
        checker.save_response_body(self.root, 'body.bin', b'first')
        with self.assertRaises(FileExistsError):
            checker.save_response_body(self.root, 'body.bin', b'second')

    def test_parent_path_refused(self):
        with self.assertRaises(ValueError):
            checker.save_response_body(self.root, '../escape', b'x')

    def test_absolute_path_refused(self):
        with self.assertRaises(ValueError):
            checker.save_response_body(self.root, str(self.root / 'absolute'), b'x')

    def test_symlink_parent_refused(self):
        (self.root / 'real').mkdir()
        (self.root / 'alias').symlink_to(self.root / 'real', target_is_directory=True)
        with self.assertRaises(ValueError):
            checker.save_response_body(self.root, 'alias/body', b'x')


if __name__ == '__main__':
    unittest.main()
