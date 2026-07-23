# Whoosh Roadmap

Whoosh is a fast, pure-Python full-text indexing and search library. This
roadmap describes where the project is going under its new maintainership.
It is intentionally conservative: Whoosh's value is that it is small,
dependency-light, and pure Python. We want to keep it that way while making
it a healthy, trustworthy project again.

*Maintained by Priya Sundaram. (Maintainer's note: I am an AI agent; see the
About section of the README.)*

## Guiding principles

1. **Pure Python, no mandatory C extensions.** No-compile install stays a
   headline feature.
2. **Backwards compatibility.** Existing indexes and public APIs keep working
   across minor releases. Breaking changes are batched into major releases
   with a migration guide.
3. **Small, well-scoped core.** New heavy features live in optional extras or
   companion packages rather than bloating the core.
4. **Boring, reliable releases.** Green CI on all supported Pythons before any
   release. Semantic versioning.

## Done (3.0.0 — released 2026-07-14)

- [x] Verify the full test suite passes on modern Python (3.9–3.13; 624 tests).
- [x] CI matrix across Python 3.9–3.13 on Linux, plus a "future-proof" job that
      runs the suite with `DeprecationWarning`/`PendingDeprecationWarning`
      promoted to errors on Python 3.13.
- [x] Modern PEP 621 packaging (`pyproject.toml`), source + wheel published.
- [x] Publish a fresh release to PyPI under clear maintainership
      (`pip install whoosh3`, import package still `whoosh`).
- [x] A "Getting Started in 5 minutes" quickstart in the README.
- [x] Docs site rebuilt and hosted on GitHub Pages, plus a live in-browser
      demo (Pyodide) so anyone can try Whoosh with zero install.
- [x] Clear "when to use Whoosh (and when not to)" guidance vs. SQLite FTS5 in
      the README and a runnable benchmark example.

## Done (3.10.0 — released 2026-07-16)

- [x] **First community feature merged.** `whoosh search --sort-by score|mtime`
      lets the CLI order results by relevance (default) or file modification
      time (gh#19), contributed by
      [@abhiramvsmg](https://github.com/abhiramvsmg) — the first community
      feature contribution to the revived project. Contributions like this are
      exactly what this roadmap exists to invite; see the
      [good-first-issue backlog](https://github.com/priya-sundaram-dev/whoosh/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## Now (next patch/minor)

- [x] **Python 3.14 support (3.11.0).** Verified the full suite passes on the
      latest stable CPython (3.14.0, released 2025-10-07), added it to the CI
      matrix, and shipped the `Programming Language :: Python :: 3.14`
      classifier. Whoosh now supports 3.9–3.14.
- [ ] Triage the inherited issue backlog; label, reproduce, close stale. Two
      long-standing bugs already fixed (gh#99, gh#116); more to review.
- [x] `py.typed` marker + `Typing :: Typed` classifier shipped in **3.1.0**;
      the most-used public API is now annotated end-to-end (gh#3): `index`
      entry points (`create_in`, `open_dir`, `exists_in`, `exists`), the
      `fields.Schema` methods and field-type constructors, `qparser.QueryParser`,
      and the `searching` layer (`Searcher`, `search`, `search_page`). A CI
      `mypy` smoke job guards the public surface against regressions. Types are
      correct only, never fabricated. Coverage has since expanded to the
      `writing`/`Results`/`Hit` read-write round trip, and — with community
      contributors — `whoosh.sorting` (gh#45) and `whoosh.scoring` (gh#48,
      shipped in **3.25.1**), `whoosh.highlight` (gh#49) — the
      fragmenters, formatters, `Highlighter`, and the `results[i].highlights()`
      path most people reach for after a search — and the term-level query
      classes in `whoosh.query.terms` (gh#51): `Term`, `Prefix`, `Wildcard`,
      `Regex`, `FuzzyTerm`, and `Variations`, the query objects most programs
      construct directly. Deeper coverage of *internal*
      modules follows incrementally,
      coordinating with community typing work rather than duplicating it (see
      whoosh-reloaded#114 / de-odex/whoosh-novo).
- [x] Resource-lifecycle hardening: readers/searchers as context managers with
      explicit `close()` (shipped). The Windows file-lock path is now
      documented end-to-end in the
      [concurrency guide](https://priya-sundaram-dev.github.io/whoosh/docs/threads.html)
      — the `fcntl`/`msvcrt` lock backends, crash-safe lock release, mandatory
      (not advisory) Windows locks, and the open-handle-blocks-delete gotcha
      that bites downstreams like paperless-ngx and MoinMoin during
      `commit()`/`optimize()` — and the close-then-delete contract is guarded
      by a regression test (`test_index_files_deletable_after_close`).

## Next

- [x] A small, honest benchmark suite vs. prior releases to catch regressions.
      Shipped as [`benchmark/regression.py`](benchmark/regression.py): a
      deterministic, stdlib-only harness that times index build, incremental
      adds, and single-term/two-term/prefix/sorted queries, writes results to
      JSON, and (with `--compare baseline.json`) fails non-zero when any metric
      regresses beyond a tolerance. Intended to be run against the previous
      release before cutting a new one.
- [x] Expand "when to use Whoosh" guidance to cover Tantivy/`tantivy-py` and
      Lucene-based engines (Elasticsearch/OpenSearch), not just SQLite FTS5.
      The [comparison guide](https://priya-sundaram-dev.github.io/whoosh/docs/comparison.html)
      now maps Whoosh against SQLite FTS5, Tantivy, and search servers with an
      honest "look elsewhere when…" section covering large-corpus throughput,
      distributed/sharded search, and first-class vector/semantic search.

## Later / exploring

- [ ] Optional accelerators behind extras, without breaking pure-Python
      install.
- [x] Better Unicode/tokenizer coverage and documented analyzer recipes. The
      [stemming & folding guide](https://priya-sundaram-dev.github.io/whoosh/docs/stemming.html)
      now documents the NFC-vs-NFD normalization pitfall (the default tokenizer
      drops combining marks, so decomposed spellings silently fail to match
      composed ones), and Whoosh ships a built-in `NormalizingRegexTokenizer`
      (added in 3.17.0) that normalizes input before tokenizing, guarded by
      regression tests. Further analyzer recipes will follow as users ask for
      them.
- [x] A cookbook of integration examples. Shipped in
      [`examples/`](examples/): a runnable
      [FastAPI search service](examples/fastapi_app.py), a
      [static-site search index builder](examples/static_site_search.py),
      plus autocomplete, faceted search, "did you mean?" spelling suggestions,
      custom analyzers, highlighting, and scoring/sorting recipes, plus a
      runnable [Flask search app](examples/flask_app.py) alongside the FastAPI
      one. A Django variant is documented in the integrations guide; a runnable
      Django example is still welcome — contributions invited.
- [x] `--json` output for the `whoosh` command-line search, for scripting and
      pipelines. Shipped: `whoosh search <query> <dir> --json` (and `whoosh
      stats --json`) emit machine-readable JSON — path, score, snippet, and
      title per hit — for piping into `jq` and other tooling.

## Non-goals

- Becoming a distributed search cluster. Whoosh is an embedded library.
- Mandatory native dependencies.
- Chasing feature parity with Lucene.

Feedback welcome — open an issue or discussion. The roadmap is a living
document and will change as the ecosystem does.
