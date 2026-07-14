# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/) and the format is loosely based on
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Typed query parser (gh#3).** `whoosh.qparser.QueryParser` — the class you
  use to turn user input into queries — now carries type hints on its
  constructor and core methods (`parse`, `parse_`, `process`, `tag`), plus the
  premade factory functions `MultifieldParser`, `SimpleParser`, and
  `DisMaxParser`. Editors autocomplete `parse(text, normalize=..., debug=...)`
  and type checkers verify that `parse()` returns a `whoosh.query.Query`. Hints
  use `from __future__ import annotations` (no runtime cost or behavior change)
  and are guarded by a regression test.
- **Typed field constructors (gh#3).** The field types you write in every
  `Schema` — `TEXT`, `ID`, `IDLIST`, `KEYWORD`, `NUMERIC`, `DATETIME`,
  `BOOLEAN`, `STORED`, and `COLUMN` — now carry parameter and return
  annotations on their constructors. Editors autocomplete kwargs like
  `stored=`, `unique=`, `phrase=`, `commas=`, and type checkers verify your
  field definitions. Hints use `from __future__ import annotations` (no runtime
  cost or behavior change) and are guarded by a regression test.
- **More public typing (gh#3).** `whoosh.fields.Schema` — the class every user
  imports first — now carries type hints on its common methods (`copy`,
  `items`, `names`, `add`, `remove`, `indexable_fields`, `stored_names`,
  `scorable_names`, `has_scorable_fields`, and the mapping dunders). This means
  `schema.items()` type-checks as `list[tuple[str, FieldType]]`, `.names()` as
  `list[str]`, and so on, giving downstream code accurate autocompletion and
  `mypy`/`pyright` checking. Hints use `from __future__ import annotations`, so
  there is **no runtime import cost or behavior change**. Guarded by a new
  regression test in `tests/test_typing.py`.
- New example `examples/fastapi_app.py`: a small, production-shaped full-text
  search REST API built with FastAPI, with idempotent upsert/delete/search
  endpoints, pagination, BM25F ranking, highlighted snippets, and clean
  startup/shutdown of the index. The search logic is in a framework-free
  `SearchIndex` class so it is easy to test. Documented in the cookbook.

## [3.1.0] - 2026-07-14

### Added
- **PEP 561 typing support (gh#3).** Whoosh now ships a `py.typed` marker and
  is advertised as a typed package (`Typing :: Typed` classifier), so type
  checkers (`mypy`, `pyright`) and editors pick up its types automatically —
  no more `# type: ignore` or missing-stub warnings when you import Whoosh.
  As a first, correct pass, the convenience entry points people call first are
  fully annotated: `whoosh.index.create_in`, `open_dir`, `exists_in`,
  `exists`, and `whoosh.versionstring`. Annotations use
  `from __future__ import annotations`, so there is **no runtime import cost
  or behavior change** — heavier types (e.g. `Schema`, `Storage`) are resolved
  only by static checkers. Type coverage of the remaining public modules will
  expand incrementally in later releases (see the roadmap). A regression test
  (`tests/test_typing.py`) guards the marker and the annotated entry points.
- New runnable example `examples/search_cli.py`: a tiny, dependency-free
  command-line tool that indexes a folder of text/markdown/source files and
  searches it from the terminal, with highlighted snippets, title boosting,
  and fast incremental re-indexing (`--update`, mtime-based). A single file you
  can copy into your own project. Documented in the docs cookbook.

## [3.0.3] - 2026-07-14

### Added
- Downstream-compatibility test suite (`tests/test_downstream_compat.py`) that
  exercises the exact public API surface used by
  [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) — mixed
  `TEXT`/`KEYWORD`/`DATETIME`/`NUMERIC`/`BOOLEAN` schema, `AsyncWriter`,
  `MultifieldParser` + `DateParserPlugin` date ranges, `TF_IDF` scoring, and
  `HtmlFormatter` highlighting — so drop-in compatibility is guarded in CI.
  `MIGRATING.md` documents this.

### Fixed
- ISO-8601 dates such as `2023-05-17`, `2023-05`, `2023-05-17 14:30`, and
  `2023-05-17T14:30:00` were **not recognized** by the natural-language date
  parser (`DateParserPlugin` / `English`), which returned `None` for them.
  The natural-language branch greedily matched only the leading four-digit
  *year* of an ISO date, so the overall (end-anchored) parse failed on the rest
  of the string. The "simple" ISO parser is now tried before the
  natural-language branch, and the `T` date/time separator is accepted, so
  ISO-8601 dates parse correctly. Natural-language forms (`may 17 2023`,
  `next monday`, `-1 day`, …) are unaffected. Added regression tests.

## [3.0.2] - 2026-07-14

### Fixed
- A `filter=`/`mask=` (allow/restrict) set was **silently ignored** when a
  search also had a time limit — i.e. whenever a `TimeLimitCollector` wrapped a
  `FilterCollector`. `TimeLimitCollector.collect_matches()` iterates its
  child's `matches()` and calls `collect()` itself, which bypassed the
  filtering that `FilterCollector` only did in its own `collect_matches()`
  override, so *every* matching document came back regardless of the filter.
  The allow/restrict logic (and `filtered_count` bookkeeping) now lives in
  `FilterCollector.matches()`, so the filter is honored no matter what outer
  collector wraps it. Added a regression test.
- Sorting or faceting by a sortable/column field returned **scrambled** results
  after documents were added through a `BufferedWriter` (the quasi-real-time
  writer). Root cause: `BufferedWriter` opens a fresh short-lived per-document
  writer for every `add_document()` call, and the in-memory `MemoryCodec`
  recreated (truncated) each column file per session — so the reader, which
  reads `doc_count_all()` entries, filled every doc except the last-written one
  with the column's *default* value. Sorting on those near-identical default
  values produced an effectively random order (most visible with a reverse
  sort). Column values are now kept on the persistent in-memory segment and the
  complete column file is rewritten for the whole segment, so both quasi-real-
  time (pre-commit) and on-disk (post-commit) reads sort correctly. Verified for
  numeric and text sortable fields with a new regression test.

### Internal
- Made `test_buffered_threads` deterministic. It previously used
  `random.choice` to pick which of four words each thread wrote, so a run
  could leave fewer than four unique documents and fail intermittently (seen
  on CI). Each thread now owns a distinct word.

## [3.0.1] - 2026-07-14

### Fixed
- `NumericRange` (and therefore range `filter=`/query-parser range searches) with
  an open lower bound could match **every** document instead of the intended
  range. The trie-range splitter underflowed when the range's upper bound was
  near zero in the sortable-value space — which happens for **unsigned** NUMERIC
  fields and for signed fields near their minimum — emitting a coarse `TermRange`
  covering the whole value space. The filter then appeared to be "completely
  ignored", most visibly when combined with reverse sorting. Fixed with an
  explicit underflow guard in `whoosh.util.numeric.split_ranges`; verified with
  an exhaustive test across signed/unsigned integers, all boundary combinations,
  and inclusive/exclusive edges. Reported upstream as
  [whoosh-community/whoosh#583](https://github.com/whoosh-community/whoosh/issues/583).

### Added
- New CI job "Future-proof (warnings as errors)" that runs the full test suite
  on Python 3.13 with `DeprecationWarning`/`PendingDeprecationWarning` promoted
  to errors. The whole suite (624 tests) passes clean, so the "runs on modern
  Python with no deprecation noise" promise is now continuously verified and
  will fail loudly the moment a future CPython deprecates something Whoosh
  relies on — rather than silently breaking downstream users.
- New cookbook section "Closing indexes cleanly (and avoiding Windows file-lock
  errors)" plus a runnable `examples/resource_management.py`, documenting how to
  use readers/searchers as context managers and `Index.close()` so index files
  are released deterministically — no `gc.collect()` workaround — which prevents
  `PermissionError: [WinError 32]` when deleting or rebuilding an index on
  Windows.

## [3.0.0] - 2026-07-14

### Changed
- Project revived under new maintainership (Priya Sundaram). The library
  continues from `whoosh-reloaded`, itself a revival of the original Whoosh by
  Matt Chaput. Prior copyright and the BSD-2-Clause license are preserved.
- Modernized packaging metadata to PEP 621 (`pyproject.toml`), while keeping a
  `setuptools` build backend and the pure-Python, no-compile install.
- Refreshed the README with a "why Whoosh", a 5-minute quickstart, honest
  maintenance history, and a runnable `examples/quickstart.py`.
- Documented supported Python versions (3.9–3.13) and added a public roadmap.

### Added
- New Cookbook page in the documentation site (`docs/source/cookbook.rst`) that
  surfaces all the runnable `examples/` recipes (quickstart, tutorial,
  did-you-mean, autocomplete, faceted search, highlighting, SQLite FTS5
  benchmark, migration) with
  descriptions and cross-links, and repointed the stale prior-project links in
  the docs index to this repository.
- New migration guide ([MIGRATING.md](MIGRATING.md)) for users coming from the
  original `Whoosh` or `whoosh-reloaded`: what changed (zero runtime deps,
  bug fixes), what did not (imports, on-disk index format, public API), and
  the one-line dependency change to upgrade.
- New "Whoosh in 5 minutes" tutorial ([TUTORIAL.md](TUTORIAL.md)) with a
  runnable companion script ([`examples/tutorial.py`](examples/tutorial.py))
  covering schemas, `update_document`, multi-field search, sorting, faceting,
  and highlighting.
- New reproducible benchmark
  ([`examples/benchmark_vs_sqlite.py`](examples/benchmark_vs_sqlite.py))
  comparing Whoosh against SQLite FTS5 on build time, index size, and query
  latency, with honest caveats about what the numbers mean.
- New did-you-mean / spell-check demo
  ([`examples/did_you_mean.py`](examples/did_you_mean.py)) showing
  `searcher.suggest()` and `searcher.correct_query()` for single-word
  suggestions and whole-query correction (with HTML formatting).
- New search-as-you-type / autocomplete example
  ([`examples/autocomplete.py`](examples/autocomplete.py)) demonstrating three
  pure-Python strategies: term completion (`reader.expand_prefix`), prefix
  search (`Prefix` query), and fuzzy n-gram matching (`NgramWordAnalyzer`).
- New faceted-navigation example
  ([`examples/faceted_search.py`](examples/faceted_search.py)) showing a
  filter-sidebar with per-bucket counts (`FieldFacet`, `RangeFacet`,
  `groupedby`) and query drill-down, plus a matching Cookbook entry.
- New highlighting / search-snippets example
  ([`examples/highlighting.py`](examples/highlighting.py)) showing
  `Hit.highlights()`, choosing fragmenters (`ContextFragmenter`,
  `SentenceFragmenter`) and formatters (`HtmlFormatter`, `UppercaseFormatter`),
  fast pinpoint highlighting via `chars=True` + `PinpointFragmenter`, and
  highlighting unstored fields, plus a matching Cookbook entry.
- New custom-analyzers example
  ([`examples/custom_analyzers.py`](examples/custom_analyzers.py)) showing how to
  compose a tokenizer and filters with the `|` operator (`RegexTokenizer`,
  `LowercaseFilter`, `StopFilter`, `StemFilter`), accent folding with
  `CharsetFilter` + `accent_map`, token normalisation with `SubstitutionFilter`,
  character n-grams with `NgramFilter`, and attaching a custom analyzer to a
  field, plus a matching Cookbook entry.
- New custom scoring & sorting example
  ([`examples/scoring_and_sorting.py`](examples/scoring_and_sorting.py)) showing
  how to tune BM25F (global and per-field `B`/`K1`), swap in other models
  (`TF_IDF`, `Frequency`), mix models per field with `MultiWeighting`, score
  with an arbitrary Python function via `FunctionWeighting`, and bypass
  relevance with `sortedby`, plus a matching Cookbook entry.

### Fixed
- `MultiFilter` no longer raises `StopIteration` on an empty token stream
  (e.g. a null query with a custom tokenizer); it now yields no tokens.
  Fixes gh#99, based on the fix proposed by @shroom00 in gh#82.
- `RamStorage.temp_storage()` now returns an in-memory `RamStorage` instead of a
  disk-backed `FileStorage` in the system temp directory. This fixes intermittent
  `[Errno 2] No such file or directory` errors when writing multi-segment
  in-memory indexes and keeps RAM indexes entirely off disk. Fixes gh#116
  (see also whoosh-community#450).

### Notes
- The full test suite passes on Python 3.12. CI verifies the matrix on each push.

---

Older history from the `whoosh-reloaded` and original Whoosh lines is available
in the respective repositories' git history and release notes.
