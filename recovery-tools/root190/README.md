# JP190 partial root-transition tools

This local workflow prepares a partial portal transition after the corrected Japanese child is independently verified live. It does not publish, update branches, make a commit, change Pages, or complete the full multi-repository split. A draft is not eligible for publication.

## Preserved scope

The input portal has 2,707 laws and 356 additions. Exactly 190 selected Japanese law paths become HTML JavaScript/noscript/visible-link redirects to the corrected child. JavaScript preserves query and fragment; static no-script fallback uses the canonical URL. These are not HTTP 301 redirects.

The other 2,517 law files, including the large Canadian statute, and 5,628 Korean redirects remain byte-identical. Four locale indexes change only the selected 190 cards and their corrected edition labels. The additions catalogue retains 356 records: 166 local and 190 external. Each external record preserves the source, original and corrected text hashes, rights, original root path and child canonical path. The root sitemap has 2,522 canonical URLs. Local/aggregate counts remain separate. No other unprovisioned child is linked.

The build changes exactly 204 existing files and adds three routing/validation files. Publisher snippets are retained. The three legacy mutating importers fail before writes whenever the routing marker exists, even if it is malformed. Both old validator entry points dispatch to a route-aware validator that retains source-text hashes, character counts, publisher, private-file, media and active-body checks for local content.

## Entry points

- `build_root190.py`: new isolated output only. Supply clean root and corrected candidate checkouts, reviewed child release, exact child independent review, and the expected source commit. Without `--live-proof`, only explicit `--draft` is permitted.
- `validate_root190.py`: full baseline conservation, exact redirects/catalogue/index/sitemap transformations, and all three Node validator entry points. Writes a private report only to the requested location.
- `check_root190_gates.py`: rejects drafts, missing/stale/mismatched live proof, stale file maps, or a changed root main ref. It returns local preparation eligibility only; no CAS or deployment is performed.
- `root190_common.py`: deterministic redirects, tree hashing, evidence validation and shared helpers.
- `root190-route-guard.mjs` and `validate-jp190-transition.mjs`: public route-aware checks copied to the prepared root.
- `test_root190.py`: eight synthetic tests, including 13 negative live-proof cases. Run `python3 -B -m unittest -v test_root190.py`. These tests use no network or real legislation.

## Live-child evidence contract

Do not create a successful proof from cached booleans or expected commit values. The proof must describe actual observations of the exact final child deployment. It uses schemaVersion 1, repository `NaNaCompany/world-law-jp-01`, publicBase `https://nanalab.kr/world-law-jp-01/`, a fresh checkedAt and actual commit.

The `ref`, `gitCommit`, `gitTree` and `deployment` objects are actual GitHub JSON snapshots. `githubReads` has matching keys, each with its own fresh checkedAt, exact API URL, HTTP status 200, relative bodyFile and bodySha256. The saved body must parse to the matching snapshot. Ref must be main, the complete recursive tree must match all 208 frozen files and expected tree/directory entries, and the Pages run must succeed for that exact main commit. Extra entries, submodules, duplicates and stale per-read timestamps fail.

`pages` contains exactly 194 unique canonical URLs. Each HTTP receipt has url, finalUrl, status, defaultTlsValidation, checkedAt, relative bodyFile and bodySha256. Actual saved bodies must have the right canonical and publisher tags; all 190 article hashes and source/text pins must match. The `sitemap` receipt covers the actual sitemap and its exact 194 URLs. Paths must stay inside the proof directory without symlink ancestors. Reads older than one hour fail. This evidence is private and must not enter a publication tree.

A separate fresh root-head evidence receipt uses the same saved-body format for the portal main-ref API. Its actual commit must still match the approved source baseline. The final root preparation also needs current local and independent full-file maps. A later source change requires reconciliation, not an unconditional ref overwrite.

## Publication boundaries

After collecting real evidence, rebuild into another new directory with `--live-proof`, rerun full and independent review, and run the gate. A draft must never be relabeled ready. Static public metadata describes routing and build scope; it does not self-certify current deployment state. Private audit records retain their creation-time facts.

Commit/ref compare-and-swap, exact root Pages revision, old-path redirects and browser checks are separate authorized operations. Do not move main or call a partial tree complete. Root output remains roughly 560 MB in the present baseline; this partial workflow is not the full split's smaller-root target. A lower byte count than a previous successful deployment does not guarantee a timeout fix. Host-root sitemap ownership and registration are separate and untouched.

Only these code/docs files belong in a code checkpoint. Exclude source archives, law corpora, audit reports, HTTP bodies, logs and generated release files.
