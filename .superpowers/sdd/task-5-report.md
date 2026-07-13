# Task 5 Report: PDF ingestion and transform seam

## Commit

`HEAD` — `feat: add PDF ingestion and transform pipeline`

## RED / GREEN

- RED 1: `uv run pytest tests/ingestion/test_pdf_loader.py -q` failed during collection because `src.ingestion.loader_factory` did not exist.
- GREEN 1: the real PyMuPDF-generated one-page PDF passed through `load_document(...)` (`1 passed`).
- RED 2: `tests/ingestion/test_transforms.py` failed because `src.ingestion.transforms` did not exist.
- GREEN 2: cleanup and metadata preservation tests passed (`2 passed`).
- RED 3: the integration progress/fallback test failed with unsupported `optional_transforms`.
- GREEN 3: the same test passed after the pipeline recorded the transform fallback and continued to both indexes (`1 passed`).
- RED 4: multi-page PDF ingestion had no chunk `page` metadata (`KeyError: 'page'`).
- GREEN 4: the splitter recognizes PDF page markers, keeps page metadata, and PDF re-ingestion skips unchanged content (`2 passed` in the PDF loader suite).

## Implementation

- Added `load_document(Path, collection)` for `.md`, `.markdown`, and `.pdf`; unsupported suffixes raise a clear `ValueError`.
- Added a PyMuPDF-backed `PdfLoader` that emits `<!-- page: N -->` Markdown, source SHA-256, suffix, and page count.
- Added immutable cleanup and metadata transform seams. Cleanup removes BOM/trailing whitespace and collapses excess blank lines; metadata retains retrieval fields including title, page, source path, and SHA-256.
- Pipeline defaults to the loader factory, applies transforms before embedding, reports `load/split/transform/embed/upsert`, and records an optional-transform fallback in both progress details and JSONL tracing. Embed/upsert remain in the normal failure/atomicity path.
- PDF page markers split into page-scoped chunks with `page` metadata, while ordinary Markdown splitter behavior remains unchanged.

## Dependencies

- Added runtime dependency `PyMuPDF>=1.24`, resolved to `pymupdf==1.28.0`.
- Regenerated `uv.lock` and hash-pinned `requirements-ci.lock` with the repository's frozen export command.

## Verification

- `uv sync --frozen --all-extras --no-dev` — checked 154 packages.
- `uv lock --check` — resolved 158 packages with no lock drift.
- `uv run pytest tests/ingestion tests/integration/test_ingestion_query_flow.py -q` — 35 passed in 4.02s.
- `uv run pytest -q` — 121 passed in 20.20s.
- `git diff --check` — passed.

## Risk

- PDF extraction uses the document text layer. Image-only/scanned PDFs need an OCR capability before they can yield evidence.
