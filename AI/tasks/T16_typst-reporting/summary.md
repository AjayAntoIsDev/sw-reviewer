# T16 Summary: Typst Report Generation

**Task**: T16 (Typst report generation pipeline)

Implemented Typst-based report generation in `src/sw_reviewer/reporting/`.
- `typst.py`: `render_typst_source()` fills a Typst template with verdict data (policy checklist, web results, CLI results). `generate_report()` writes `.typ` source + JSON verdict bundle and optionally compiles to PDF using the `typst compile` CLI.
  - Gracefully skips PDF compilation when Typst binary is absent.
  - Includes 60-second timeout for compilation.
- `bundle.py`: `ArtifactBundle` class manages evidence registration, verdict persistence, and artifact indexing under `artifacts/<review_id>/`.
- 3 tests in `tests/test_reporting.py`, all passing.
