# Root JP190 post-publication verifier

Local verification tooling only. Do not upload evidence, source archives, receipts,
reference audits, or response bodies. The code-only allowlist is separate.

## Safety and scope

Default invocation is offline. Live mode requires all three explicit arguments:
`--run-live --root-commit ACTUAL_NEW_ROOT_COMMIT --pages-run ACTUAL_SUCCESSFUL_RUN_ID`.
No default commit/run is supplied. Baseline, candidate, and JP-child commits are rejected.
All pinned reference files and the complete prepared file map are verified first.
The successful Pages run must belong to the supplied root commit and repository.
GitHub main is checked both before and after the HTTP checks.

The checker has no Git write, upload, commit, ref, Pages, or configuration operation.
Every request is HTTPS GET with default certificate/hostname verification, an exact
URL allowlist, and redirects disabled. Analytics and publisher scripts are inspected
but never fetched or executed. Redirect logic runs only in a hermetic Node VM.

244 public-site GETs cover all 190 old JP URLs, 35 distinct newly exposed laws,
four locale indexes, seven metadata/sitemap/robots files, the KR index, stylesheet,
and six unchanged samples. The five navigation pages use their canonical trailing-slash
URLs; all old JP law URLs retain their exact `.html` paths. Samples include both KR child repository classes,
the complete large Canadian file, another Canadian file, and two non-target Japanese
laws. Five GitHub snapshots bind main, commit, full recursive tree, and successful
Pages run. All 8,367 Git blobs must match the prepared target, including all 8,160
unchanged files. This is not a claim to have GET-tested every unchanged public URL.

No legal article normalization is permitted: all article bytes must match. Only the
exact previously observed Cloudflare `type="module"` beacon attributes and inter-tag
shell whitespace may differ. Unknown scripts, attribute changes, body changes,
duplicated beacons, and beacons inside legal articles fail. All publisher snippets
must be byte-exact. Never alter public files to match edge behavior.

The 35-law source hashes are verified against the pinned prior source audit and
published provenance. Retained text hashes are recomputed and article hashes checked.
This does not refetch original government source files.

## Run

Supply local paths to the immutable prepared site, independent full review,
final transfer plan, independent transfer review, and new35 audit:

```
python -B verify_root190.py \
  --site "$PREPARED_SITE" --review "$FULL_REVIEW" --plan "$TRANSFER_PLAN" \
  --transfer-review "$TRANSFER_REVIEW" --new35 "$NEW35_AUDIT" \
  --output offline-proof-unique-name
```

Only after the exact root revision has deployed successfully, add the three live
arguments described above and choose a new output name. Output names are simple
basenames; evidence is always saved next to the checker in a new private directory.
Existing evidence cannot be overwritten. Actual bytes and individual receipts are
retained even on HTTP/content failure. Reports identify offline versus actual GETs.
There is no replay mode that could imply cached bytes came from new requests.

```
python -B -m unittest -v test_edge_primitives test_root190
```

Synthetic commit/run values exist only in test fixtures; they are never defaults or
real deployment claims. Node is required for the query/hash runtime tests. The
checker uses only the Python standard library and Node built-ins.
