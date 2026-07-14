# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/) and the format is loosely based on
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
