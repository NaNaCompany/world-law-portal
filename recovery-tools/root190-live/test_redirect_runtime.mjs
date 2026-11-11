// Hermetic runtime test: fake browser objects, no network or site scripts.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const rows = JSON.parse(fs.readFileSync(0, 'utf8'));
const cases = [['', ''], ['?x=a%26b&x=2', '#article-1'],
  ['?next=https%3A%2F%2Fexample.invalid%2F', '#%E7%AC%AC%E4%B8%80%E6%9D%A1'],
  ['?q=%3Cscript%3E&empty=', '#abc%23def']];
let checked = 0;
for (const row of rows) for (const [search, hash] of cases) for (const visibleExists of [true, false]) {
  let result;
  const visible = {href: ''};
  const window = {location: {search, hash, replace: url => {
    assert.equal(result, undefined, 'Duplicate redirect'); result = url;
  }}};
  const document = {getElementById: id => {
    assert.equal(id, 'relocated-law'); return visibleExists ? visible : null;
  }};
  vm.runInNewContext(row.script, {URL, window, document}, {timeout: 1000});
  assert.equal(result, row.target + search + hash);
  if (visibleExists) assert.equal(visible.href, result);
  checked++;
}
console.log(JSON.stringify({passed: true, redirects: rows.length, cases: checked,
  queryAndFragmentPreserved: true, destinationFixed: true, browserVisualQa: false}));
