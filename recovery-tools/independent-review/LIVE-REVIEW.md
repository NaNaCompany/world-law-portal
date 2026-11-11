# Static legal-text release live verification

`verify_live_release.py` uses Python's standard library. It does not write to a repository, change deployment state, run browser code, or send analytics events.

Inputs are an immutable public site directory, its independently reviewed file-hash map, and the source directory for existing cross-country fallback pages. The default mode reads local fixtures only. It checks all 194 canonical pages, 190 exact statutory articles, 13 non-HTML public resources, eight fallback pages, and local links and fragments. `.nojekyll` is treated as a repository build-control file, not a required HTTP resource.

Example offline invocation:

    python verify_live_release.py --site ./site --review ./review.json --fallback-source ./source --fallback-base https://example.org/old-portal/ --report ./offline-report.json

For live checks, add `--live --deployment-confirmed --deployed-commit <40-character-final-main-commit> --pages-run-url <successful-GitHub-Actions-run-URL>` only after confirming deployment. The evidence is recorded as operator-supplied, not claimed as independently queried by this program. Requests use default TLS verification, refuse redirects, and run at a maximum concurrency of four. There are no automatic retries.

Statutory article bytes, source attributes, omissions, provenance, rights, original publisher snippets, canonicals, and local asset files must match the reviewed reference. An extra empty external Cloudflare Insights beacon with only known attributes may be recorded separately from the frozen page. Other unexplained shell changes fail. Inter-tag whitespace outside the article may differ; article whitespace remains exact. JSON metadata and non-HTML files require exact bytes.

Run hermetic adversarial tests with:

    python test_live_release.py -v

Reports distinguish offline fixtures from actual HTTP responses, full-file equality from allowed edge additions, and verified results from failures. Browser appearance, execution of advertising/analytics code, and official-source endpoint availability are not tested. A static publication-state field is reported as its frozen value and is not treated as evidence of current deployment.
