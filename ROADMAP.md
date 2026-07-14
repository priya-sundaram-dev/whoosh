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

## Now (0.x stabilization)

- [x] Verify the full test suite passes on modern Python (3.12 confirmed).
- [ ] CI matrix across Python 3.9–3.13 (and 3.14 when stable).
- [ ] Modern PEP 621 packaging (`pyproject.toml`, `hatchling`/`setuptools`
      build backend), reproducible wheels.
- [ ] Publish a fresh release to PyPI under clear maintainership.
- [ ] A "Getting Started in 5 minutes" quickstart in the README.
- [ ] Triage the inherited issue backlog; label, reproduce, and close stale.

## Next

- [ ] Type hints on the public API (`index`, `fields`, `qparser`,
      `searching`) + a `py.typed` marker.
- [ ] Docs site rebuilt and hosted (GitHub Pages), with runnable examples.
- [ ] A small, honest benchmark suite vs. prior releases to catch regressions.
- [ ] Clear "when to use Whoosh (and when not to)" guidance vs. SQLite FTS5,
      Tantivy/`tantivy-py`, Lucene-based engines.

## Later / exploring

- [ ] Optional accelerators behind extras, without breaking pure-Python
      install.
- [ ] Better Unicode/tokenizer coverage and documented analyzer recipes.
- [ ] A cookbook of integration examples (Flask/Django/FastAPI, static-site
      search).

## Non-goals

- Becoming a distributed search cluster. Whoosh is an embedded library.
- Mandatory native dependencies.
- Chasing feature parity with Lucene.

Feedback welcome — open an issue or discussion. The roadmap is a living
document and will change as the ecosystem does.
