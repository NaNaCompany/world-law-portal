# Japanese-law phase1 tools

These tools prepare a **local candidate for 190 corrected Japanese documents only**. They do not deploy, change a remote repository, or complete the full multi-repository migration.

The code was reconstructed after a workspace loss. Byte identity with the previous implementation is **not verified**. The 17 synthetic tests pass, including a mock 190-document build, validation, packing, freeze, and small-request Git transfer plan. The restored code still requires fresh review against the actual 190 documents before any publication.

## Files

- `phase1_jp01.py`: default-paused local builder for the reviewed JP190 subset.
- `validate_phase1_jp01.py`: article, source metadata, publisher, sitemap and link checks.
- `pack_phase1_jp01.py`: deterministic local site archive. This does not authorize publishing a source archive.
- `freeze_phase1_jp01.py`: binds current public files to successful local and independent reviews, records hashes and transfer sizes.
- `prepare_tree_packages.py`: local-only small Git tree requests and separate whole-file blob requests. It sends no API calls.
- `compare_phase1_history.py`: read-only comparison with prior public-file and Git-tree fingerprints. A mismatch must be investigated, never hidden by changing evidence.
- `build_release.py`: only recovered shared primitives. The full split entry point is deliberately blocked.
- `pack_release.py`: only the shared deterministic archive helper. Full split packing is blocked.
- `test_recovery.py`: synthetic fixtures and negative tests, without real legislation or network access.

## Tests

Run `python3 -B -m unittest -v test_recovery.py` from this directory. Temporary mock fixtures are created and removed under `.selftest/`. Passing these tests is not evidence that the real source corpus was restored or published.

## Required reviewed inputs

The phase1 builder requires a clean committed source checkout, a SHA-pinned manifest containing exactly the actual 190 Japanese catalogue paths, and readiness evidence for source structure, omissions and independent review. Each document needs reviewed whole-page, article, source and text SHA256 values. No records may be fabricated to meet counts.

Run the builder only with `--enable-reviewed-phase1` and explicit `--source`, `--jp-manifest`, `--expected-manifest-sha256`, `--readiness-proof`, and a new `--output` outside the source. The optional base proof must describe real HTTPS bootstrap evidence, not a successful content deployment. Then run the phase1 validator, an independent review, the packer and the freezer.

The legal article bytes are preserved. Necessary navigation, canonical and asset changes occur outside the article. JP190 links go directly to the child; other laws retain existing portal destinations. Unknown routes fail closed. Four interface-language indexes and exactly 194 canonical sitemap URLs are generated. Figures, formulas and tables are excluded; source, rights, edition, omission notices and publisher tags remain intact. The source and hub are not modified.

Static public metadata describes the build scope, source snapshot and counts. It contains no `publicationState` or `published` assertion. Actual deployment status is verified separately from the exact remote revision, Pages run and live HTTP/browser checks. Private build receipts retain their truthful creation-time state.

Every output explicitly says `phase=jp190-only` and `fullSplitComplete=false`. Source totals are observed honestly. The unavailable full-split corpus and full builder are not certified by this phase.

## Small transfer strategy

Transfer planning requires the independently reviewed exact 208-file freeze and `--enable-reviewed-transfer-plan`. Tree requests use at most 500 KiB including a 64 KiB reserve. Larger files use separate whole-file base64 `create_blob` arguments, followed by SHA-only tree references. The previous multi-megabyte inline tree strategy is not used. Statute HTML is never truncated or arbitrarily split.

The largest previously available blob is reused only if its exact SHA matches the new frozen file. Otherwise the difference is reported and the actual whole file is measured. All requests are stored as ASCII JSON with separately measured UTF8 wire sizes. Every blob and intermediate/final tree is checked using both local Git-object calculations and standard Git commands.

API availability and authorization must be checked before execution. Stop on any error, denial, unexpected SHA or uncertain outcome. Check uncertain results before retrying; do not change routes or tools to bypass a denial. Creating objects alone does not publish a site. Commit/ref compare-and-swap, the exact Pages revision, live article/canonical checks and desktop/mobile browser QA are separate steps. No permission expansion or domain/security changes are included.

Historical file fingerprints contain source-commit and manifest metadata. A newly reviewed commit can legitimately yield a different public fingerprint even when the law text is identical. Do not falsify commit or review fields to force an old hash.

### Staging recovery checkpoints

The transfer plan interleaves a small batch of whole-file blob requests with its expected Git tree, by default at most 20 early files per tree. Law HTML and required assets come first. The original bootstrap README remains unchanged in intermediate trees; complete indexes, sitemap, catalogues and publication metadata appear only in the final tree. All final files stay byte-identical to the reviewed site.

Each successful expected tree has an explicit cumulative file list and a suggested `staging/corrected-jp190` checkpoint. Intermediate commits must be described as partial and not deployed. This tool does not create commits or update that branch. Final main/ref movement and Pages deployment remain prohibited until the complete 208-file tree and all review gates pass. Raw source archives, audit notes and private reports are excluded from every checkpoint.
