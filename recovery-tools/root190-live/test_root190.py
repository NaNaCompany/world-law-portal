#!/usr/bin/env python3
"""Hermetic adversarial tests. All HTTP is mocked; no real network requests."""
import copy
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import verify_root190 as c
from test_edge_primitives import RAW, BODY, BEACON, SNIPPETS, PATH

COMMIT = 'a' * 40  # Synthetic only; never used for a real request.
RUN = 123
ARGS = SimpleNamespace(run_live=True, root_commit=COMMIT, pages_run=RUN, workers=1)


class RootHtml(unittest.TestCase):
    def verify(self, raw=RAW):
        return c.check_html(PATH, raw, RAW, SNIPPETS)

    def reject(self, raw):
        with self.assertRaises(ValueError): self.verify(raw)

    def test_exact(self):
        self.assertTrue(self.verify()['wholeFileExact'])

    def test_exact_established_module_beacon(self):
        result = self.verify(RAW.replace(b'</body>', BEACON + b'</body>'))
        self.assertEqual(len(result['edgeBeaconScripts']), 1)
        self.assertFalse(result['wholeFileExact'])

    def test_legal_byte_change(self): self.reject(RAW.replace('甲'.encode(), '丙'.encode()))
    def test_legal_whitespace_change(self): self.reject(RAW.replace(b'</span><p', b'</span> <p'))
    def test_beacon_in_article(self): self.reject(RAW.replace(b'</article>', BEACON + b'</article>'))
    def test_duplicate_beacons(self): self.reject(RAW.replace(b'</body>', BEACON + BEACON + b'</body>'))
    def test_unknown_beacon_type(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'type="module"', b'type="text/javascript"') + b'</body>'))
    def test_changed_beacon_token(self):
        self.reject(RAW.replace(b'</body>', BEACON.replace(b'9f3423bb', b'00000000') + b'</body>'))
    def test_added_unapproved_script(self): self.reject(RAW.replace(b'</body>', b'<script>bad()</script></body>'))
    def test_removed_article(self): self.reject(RAW.replace(BODY, b''))
    def test_added_article(self): self.reject(RAW.replace(BODY, BODY + BODY))
    def test_altered_canonical(self): self.reject(RAW.replace(b'/laws/test.html', b'/laws/other.html'))
    def test_removed_publisher(self): self.reject(RAW.replace(SNIPPETS['footer'], b''))
    def test_changed_publisher_code(self): self.reject(RAW.replace(SNIPPETS['footer'], SNIPPETS['footer'] + b'bad'))


class Gates(unittest.TestCase):
    def reject(self, **changes):
        args = SimpleNamespace(**{**vars(ARGS), **changes})
        with patch.object(c, 'get_and_save', side_effect=AssertionError('Network reached')):
            with self.assertRaises(ValueError): c.live(args, {}, None)

    def test_canonical_navigation_urls(self):
        self.assertEqual(c.public_url('index.html'), c.BASE)
        for locale in ('en', 'zh', 'es', 'kr'):
            self.assertEqual(c.public_url(locale + '/index.html'), c.BASE + locale + '/')
    def test_exact_law_url(self):
        self.assertEqual(c.public_url('world-laws/jp-example.html'), c.BASE + 'world-laws/jp-example.html')
    def test_exact_metadata_url(self):
        self.assertEqual(c.public_url('sitemap.xml'), c.BASE + 'sitemap.xml')
    def test_no_run_live(self): self.reject(run_live=False)
    def test_missing_commit(self): self.reject(root_commit=None)
    def test_short_commit(self): self.reject(root_commit='a' * 7)
    def test_baseline_commit(self): self.reject(root_commit=c.BASELINE)
    def test_candidate_commit(self): self.reject(root_commit='973e5914cc1a7b4887de97b3e22a04bf2586396b')
    def test_child_commit(self): self.reject(root_commit='36f9a13ea6851e0257927a488a532bf178dd2d29')
    def test_missing_run(self): self.reject(pages_run=None)
    def test_invalid_run(self): self.reject(pages_run=-1)
    def test_valid_synthetic_gate(self): c.validate_live_gate(ARGS)
    def test_output_traversal(self):
        with self.assertRaises(ValueError): c.output_dir('../outside')
    def test_output_absolute(self):
        with self.assertRaises(ValueError): c.output_dir('/outside')
    def test_output_collision(self):
        with self.assertRaises(ValueError): c.output_dir('offline-proof-01')
    def test_pinned_file_mismatch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as name:
            p = Path(name) / 'input.json'; p.write_text('{"passed": true}')
            with self.assertRaises(ValueError): c.pinned_json(p, '0' * 64)


class GithubChecks(unittest.TestCase):
    def setUp(self):
        self.files = [{'path': 'a.html', 'mode': '100644', 'type': 'blob', 'sha': 'b' * 40},
                      {'path': 'sub/b.html', 'mode': '100644', 'type': 'blob', 'sha': 'c' * 40}]
        self.tree = {'sha': c.TARGET_TREE, 'truncated': False, 'tree': self.files +
                     [{'path': 'sub', 'mode': '040000', 'type': 'tree', 'sha': 'd' * 40}]}
        self.ref = {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': COMMIT}}
        self.commit = {'sha': COMMIT, 'tree': {'sha': c.TARGET_TREE}, 'parents': [{'sha': c.BASELINE}]}
        self.run = {'id': RUN, 'head_sha': COMMIT, 'head_branch': 'main',
                    'repository': {'full_name': c.REPOSITORY}, 'status': 'completed', 'conclusion': 'success',
                    'name': 'pages build and deployment', 'path': 'dynamic/pages/pages-build-deployment'}

    def test_valid_synthetic_github(self):
        c.validate_tree(self.tree, self.files); c.validate_ref(self.ref, COMMIT)
        c.validate_commit(self.commit, COMMIT); c.validate_run(self.run, COMMIT, RUN)
    def test_truncated_tree(self):
        self.tree['truncated'] = True
        with self.assertRaises(ValueError): c.validate_tree(self.tree, self.files)
    def test_correct_blob_sizes(self):
        tree = copy.deepcopy(self.tree)
        for e in tree['tree']:
            if e['type'] == 'blob': e['size'] = 7
        c.validate_tree(tree, self.files, {'a.html': 7, 'sub/b.html': 7})
    def test_wrong_blob_size(self):
        tree = copy.deepcopy(self.tree)
        for e in tree['tree']:
            if e['type'] == 'blob': e['size'] = 7
        with self.assertRaises(ValueError): c.validate_tree(tree, self.files, {'a.html': 8, 'sub/b.html': 7})
    def test_missing_file(self):
        self.tree['tree'] = self.tree['tree'][1:]
        with self.assertRaises(ValueError): c.validate_tree(self.tree, self.files)
    def test_changed_blob(self):
        tree = copy.deepcopy(self.tree); tree['tree'][0]['sha'] = 'e' * 40
        with self.assertRaises(ValueError): c.validate_tree(tree, self.files)
    def test_changed_mode(self):
        tree = copy.deepcopy(self.tree); tree['tree'][0]['mode'] = '100755'
        with self.assertRaises(ValueError): c.validate_tree(tree, self.files)
    def test_duplicate_blob(self):
        self.tree['tree'] = self.tree['tree'] + [self.tree['tree'][0]]
        with self.assertRaises(ValueError): c.validate_tree(self.tree, self.files)
    def test_extra_directory(self):
        self.tree['tree'] = self.tree['tree'] + [{'path': 'extra', 'type': 'tree', 'mode': '040000', 'sha': 'e' * 40}]
        with self.assertRaises(ValueError): c.validate_tree(self.tree, self.files)
    def test_wrong_head(self):
        with self.assertRaises(ValueError): c.validate_ref(self.ref, 'e' * 40)
    def test_wrong_commit_tree(self):
        self.commit['tree']['sha'] = 'e' * 40
        with self.assertRaises(ValueError): c.validate_commit(self.commit, COMMIT)
    def test_wrong_commit_parent(self):
        self.commit['parents'][0]['sha'] = 'e' * 40
        with self.assertRaises(ValueError): c.validate_commit(self.commit, COMMIT)
    def test_unsuccessful_run(self):
        self.run['conclusion'] = 'failure'
        with self.assertRaises(ValueError): c.validate_run(self.run, COMMIT, RUN)
    def test_pending_run(self):
        self.run['status'] = 'in_progress'
        with self.assertRaises(ValueError): c.validate_run(self.run, COMMIT, RUN)
    def test_wrong_run_sha(self):
        self.run['head_sha'] = 'e' * 40
        with self.assertRaises(ValueError): c.validate_run(self.run, COMMIT, RUN)
    def test_wrong_run_repository(self):
        self.run['repository']['full_name'] = 'Other/repo'
        with self.assertRaises(ValueError): c.validate_run(self.run, COMMIT, RUN)
    def test_not_pages_workflow(self):
        self.run['path'] = '.github/workflows/test.yaml'
        with self.assertRaises(ValueError): c.validate_run(self.run, COMMIT, RUN)
    def test_bad_github_blocks_site_requests(self):
        calls = []
        def fake(url, *rest):
            calls.append(url)
            data = copy.deepcopy(self.ref); data['object']['sha'] = 'e' * 40
            return json.dumps(data).encode(), {}
        with patch.object(c, 'get_and_save', side_effect=fake):
            with self.assertRaises(ValueError): c.live(ARGS, {'selected': ['index.html']}, None)
        self.assertEqual(calls, [c.API + '/git/ref/heads/main'])


class Transport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        self.url = c.BASE + 'index.html'
    def tearDown(self): self.temp.cleanup()
    def test_unallowlisted_url_before_network(self):
        with patch.object(c, 'build_opener', side_effect=AssertionError('Network reached')):
            with self.assertRaises(ValueError): c.get_and_save('https://example.invalid/', 'x', self.root, {self.url})
    def test_plain_http_before_network(self):
        with patch.object(c, 'build_opener', side_effect=AssertionError('Network reached')):
            with self.assertRaises(ValueError): c.get_and_save('http://example.invalid/', 'x', self.root, {'http://example.invalid/'})
    def fake_response(self, raw, code=200, url=None, encoding='identity'):
        response = io.BytesIO(raw); response.code = code; response.url = url or self.url
        response.headers = Message(); response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Encoding'] = encoding
        return response
    def test_save_actual_response_and_receipt(self):
        raw = b'actual\r\nbytes\xff'
        with patch.object(c, 'build_opener') as build:
            build.return_value.open.return_value = self.fake_response(raw)
            body, receipt = c.get_and_save(self.url, 'http/index.html', self.root, {self.url})
        self.assertEqual(body, raw); self.assertEqual((self.root / receipt['bodyFile']).read_bytes(), raw)
        self.assertEqual(receipt['responseSha256'], c.sha(raw)); self.assertEqual(receipt['status'], 200)
        self.assertTrue(receipt['defaultTlsVerified']); self.assertTrue(receipt['checkedAt'])
    def test_404_body_retained(self):
        headers = Message(); headers['Content-Type'] = 'text/html'
        error = HTTPError(self.url, 404, 'Not Found', headers, io.BytesIO(b'not found'))
        with patch.object(c, 'build_opener') as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(ValueError): c.get_and_save(self.url, 'http/index.html', self.root, {self.url})
        self.assertEqual((self.root / 'http/index.html').read_bytes(), b'not found')
        receipt = json.loads((self.root / 'http/index.html.receipt.json').read_text())
        self.assertEqual(receipt['status'], 404)
    def test_wrong_final_url_rejected(self):
        with patch.object(c, 'build_opener') as build:
            build.return_value.open.return_value = self.fake_response(b'body', url=c.CHILD_BASE)
            with self.assertRaises(ValueError): c.get_and_save(self.url, 'http/index.html', self.root, {self.url})
    def test_oversize_rejected_and_retained(self):
        with patch.object(c, 'build_opener') as build:
            build.return_value.open.return_value = self.fake_response(b'12345')
            with self.assertRaises(ValueError): c.get_and_save(self.url, 'http/index.html', self.root, {self.url}, max_bytes=3)
        self.assertEqual((self.root / 'http/index.html').read_bytes(), b'1234')
        self.assertTrue(json.loads((self.root / 'http/index.html.receipt.json').read_text())['overByteLimit'])
    def test_compressed_response_rejected(self):
        with patch.object(c, 'build_opener') as build:
            build.return_value.open.return_value = self.fake_response(b'body', encoding='gzip')
            with self.assertRaises(ValueError): c.get_and_save(self.url, 'http/index.html', self.root, {self.url})


if __name__ == '__main__':
    unittest.main()
