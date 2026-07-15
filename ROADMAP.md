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

## Now (next patch/minor)

- [ ] Triage the inherited issue backlog; label, reproduce, close stale. Two
      long-standing bugs already fixed (gh#99, gh#116); more to review.
- [x] `py.typed` marker + `Typing :: Typed` classifier shipped in **3.1.0**;
      the most-used public API is now annotated end-to-end (gh#3): `index`
      entry points (`create_in`, `open_dir`, `exists_in`, `exists`), the
      `fields.Schema` methods and field-type constructors, `qparser.QueryParser`,
      and the `searching` layer (`Searcher`, `search`, `search_page`). A CI
      `mypy` smoke job guards the public surface against regressions. Types are
      correct only, never fabricated. Deeper coverage of *internal* modules can
      follow incrementally as needed; coordinating with community typing work
      rather than duplicating it (see whoosh-reloaded#114 / de-odex/whoosh-novo).
- [ ] Resource-lifecycle hardening: readers/searchers as context managers with
      explicit `close()` (shipped) — document and test the Windows file-lock
      path end-to-end for downstreams like paperless-ngx and MoinMoin
      ([#4](https://github.com/priya-sundaram-dev/whoosh/issues/4), help wanted).

## Next

- [ ] A small, honest benchmark suite vs. prior releases to catch regressions.
- [ ] Expand "when to use Whoosh" guidance to cover Tantivy/`tantivy-py` and
      Lucene-based engines, not just SQLite FTS5.

## Later / exploring

- [ ] Optional accelerators behind extras, without breaking pure-Python
      install.
- [ ] Better Unicode/tokenizer coverage and documented analyzer recipes.
- [ ] A cookbook of integration examples (Flask/Django/FastAPI, static-site
      search — [#5](https://github.com/priya-sundaram-dev/whoosh/issues/5), good
      first issue).
- [ ] `--json` output for the `whoosh` command-line search, for scripting and
      pipelines ([#6](https://github.com/priya-sundaram-dev/whoosh/issues/6)).

## Non-goals

- Becoming a distributed search cluster. Whoosh is an embedded library.
- Mandatory native dependencies.
- Chasing feature parity with Lucene.

Feedback welcome — open an issue or discussion. The roadmap is a living
document and will change as the ecosystem does.
