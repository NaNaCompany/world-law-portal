# Root190 delta-transfer planning

`prepare_root190_transfer.py` changes only the approved 204 existing files and adds three routing/validation files on the pinned portal tree. The other 8,160 files are inherited without reupload, including the unchanged large Canadian statute. Raw archives, audit reports, saved HTTP bodies and tools never enter the target tree.

Use `--draft-estimate` only for measurement. It writes `draft-estimate.json`, no executable request files, and never passes publication readiness. Supply the draft release, clean source, final child release, current independent root review and a new output path.

Use `--enable-reviewed-transfer-plan` only after building a new prepared root with real child evidence. Supply the same inputs plus the actual child live proof and fresh root main-ref evidence. The tool runs the preparation gate before writing any request. All public bytes must match both current local and independent full-file maps. Never relabel a draft or reuse a stale proof.

Tree requests remain at most 512,000 bytes including a 65,536-byte envelope reserve. Large files use separate whole-file base64 blobs; they are never truncated or arbitrarily split. All 10 completion/navigation metadata files appear only in the final tree. Every intermediate and final tree is computed from the complete inherited tree and independently checked with standard Git. Request files are ASCII JSON; on-disk and compact UTF8 wire sizes/hashes are separate.

The measured draft needs 21 operations: 10 whole-file blobs and 11 trees. It transfers 207 files totaling 11,098,273 raw bytes. Actual prepared metadata and hashes will differ when genuine deployment evidence is inserted, so use the final prepared plan rather than these draft values.

A separate authorized publisher must verify each returned object SHA and stop after an error, denial, mismatch or uncertain outcome. Check uncertain outcomes before retrying. Do not update main or Pages for any intermediate tree. Only the exact complete 8,367-file final tree may proceed to a separately authorized commit and main compare-and-swap after a fresh root-head check. Creating Git objects does not mean deployment completed. Exact Pages revision, live redirects/articles/sitemap and browser checks remain necessary.

Run `python3 -B -m unittest -v test_root190_transfer.py` for five synthetic, network-free tests. These tests do not verify live deployment. No network or remote-write function exists in this planner.
