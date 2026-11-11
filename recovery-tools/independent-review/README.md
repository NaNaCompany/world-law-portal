# Independent Japanese structure verification

This read-only validator compares 190 pinned e-Gov JSON snapshots, their original catalogue/text receipts and structured HTML. It performs exact source-leaf, attribute-order, parentage, omission-conservation and HTML5/lxml checks. It does not download source data or publish anything. Only the requested report path is written.

Install requirements-review.txt in an isolated Python environment. Run verify_jp_structure.py with --source SOURCE_REPOSITORY, --raw RAW_JSON_DIRECTORY, --renderer RENDERER_PYTHON_FILE, --source-commit COMMIT_SHA, --catalogue-sha256 CATALOGUE_SHA256 and --report REPORT_PATH. Add --pages CANDIDATE_ROOT and --catalog CANDIDATE_CATALOGUE to check actual candidate files. Optional --golden GOLDEN_HTML checks the known largest-page reference.

The source repository must be clean. Input/raw files, generated reports and dependency installations are not part of this code package. A passing parser/content audit does not certify current legal force, complete national coverage, or browser visual layout.
