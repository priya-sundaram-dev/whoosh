# Whoosh

**Fast, pure-Python full-text indexing, search, and spell checking.**

[![CI](https://github.com/priya-sundaram-dev/whoosh/actions/workflows/ci.yml/badge.svg)](https://github.com/priya-sundaram-dev/whoosh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/whoosh3)](https://pypi.org/project/whoosh3/)
[![Python versions](https://img.shields.io/pypi/pyversions/whoosh3)](https://pypi.org/project/whoosh3/)
[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue)](LICENSE.txt)
[![Downloads](https://img.shields.io/pypi/dm/whoosh3)](https://pypi.org/project/whoosh3/)

Whoosh lets you add real search — ranked results, a query language, faceting,
highlighting, "did you mean?" spell-correction — to any Python program, with
**no compiler, no server, and no native dependencies**. It's `pip install` and
go. If you can open a file, you can build an index.

> **Project status (2026): actively maintained again.** This fork continues
> Whoosh after two rounds of abandonment. See [Maintenance](#maintenance) below
> for the honest history and who's behind it.

---

## Why Whoosh?

- **Pure Python.** No C to compile, no wheels that break on your platform, no
  mystery segfaults. Works anywhere CPython runs — including PyPy and, yes,
  the browser via Pyodide.
- **Embedded, not a server.** The index is just files in a directory. No daemon
  to run, no port to open, no ops. Great for desktop apps, CLIs, static-site
  search, notebooks, and tests.
- **Real search, not just `LIKE '%foo%'`.** BM25F ranking, boolean/phrase/range
  /wildcard/fuzzy queries, fields and facets, result highlighting, and a
  pure-Python spell checker.
- **Extensible everywhere.** Scoring, analysis, storage, and posting formats are
  all pluggable.
- **Typed (PEP 561).** Ships a `py.typed` marker, so `mypy`/`pyright` and your
  editor pick up Whoosh's types automatically. The most-used entry points are
  annotated today, with coverage expanding each release.

**When *not* to reach for Whoosh:** if you need a distributed cluster, or you're
already on Postgres/SQLite and their built-in FTS is enough, use those. Whoosh
shines when you want good search *inside* a Python process without extra infra.

## Install

```bash
pip install whoosh3
```

```python
import whoosh
print(whoosh.versionstring())
```

The import package is still `whoosh`. Already using the original `Whoosh` or
`whoosh-reloaded`? Migrating is usually a one-line change — see
[MIGRATING.md](MIGRATING.md).

## Quickstart (5 minutes)

```python
from whoosh.fields import Schema, TEXT, ID
from whoosh.index import create_in
from whoosh.qparser import QueryParser
import tempfile

# 1. Describe your documents.
schema = Schema(title=TEXT(stored=True), path=ID(stored=True), content=TEXT)

# 2. Create an index (just a directory of files).
ix = create_in(tempfile.mkdtemp(), schema)

# 3. Add documents.
writer = ix.writer()
writer.add_document(title="First", path="/a", content="Pure-Python full text search")
writer.add_document(title="Second", path="/b", content="No compiler required")
writer.commit()

# 4. Search.
with ix.searcher() as searcher:
    query = QueryParser("content", ix.schema).parse("python")
    for hit in searcher.search(query):
        print(hit["title"], "->", hit["path"])
```

A runnable version (with result highlighting) lives in
[`examples/quickstart.py`](examples/quickstart.py). Want more? The
[**5-minute tutorial**](TUTORIAL.md) covers schemas, updates, sorting,
faceting, and highlighting — every snippet is runnable
([`examples/tutorial.py`](examples/tutorial.py)).

## Documentation

- **Tutorial:** [TUTORIAL.md](TUTORIAL.md) — Whoosh in 5 minutes
- **Migrating** from Whoosh or whoosh-reloaded? See
  [MIGRATING.md](MIGRATING.md) — usually a one-line change
- **Docs site:** https://priya-sundaram-dev.github.io/whoosh/ (rebuilt; work in progress)
- **Examples:** the [`examples/`](examples/) directory, including a
  reproducible [benchmark vs SQLite FTS5](examples/benchmark_vs_sqlite.py)
  a [did-you-mean / spell-check demo](examples/did_you_mean.py), a
  [search-as-you-type / autocomplete example](examples/autocomplete.py), a
  [faceted-navigation / filter-sidebar recipe](examples/faceted_search.py), a
  [highlighting / search-snippets recipe](examples/highlighting.py), and a
  [custom-analyzers recipe](examples/custom_analyzers.py), a
  [custom scoring & sorting recipe](examples/scoring_and_sorting.py), and a
  [FastAPI search API](examples/fastapi_app.py) with upsert/delete/search
  endpoints, and a
  [command-line folder-search tool](examples/search_cli.py) that indexes and
  searches a directory of files in one command
- **Roadmap:** [ROADMAP.md](ROADMAP.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

## Maintenance

Whoosh has a long history worth being honest about:

1. **Original Whoosh** was written by **Matt Chaput** and released under the
   BSD 2-Clause license. It was widely used, then went dormant.
2. **whoosh-reloaded** (by **Sygil-Dev** and contributors) revived it, modernized
   the packaging, and kept the tests green — then was itself marked *no longer
   maintained*.
3. This fork picks the torch back up: keeping CI green across current Pythons,
   cutting fresh releases, triaging issues, and improving docs and examples —
   while keeping Whoosh small, dependency-light, and pure Python.

Huge thanks to Matt Chaput and the Sygil-Dev maintainers; this project stands
entirely on their work, and their copyright and license are preserved.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
The test suite runs with `pytest`; please keep it green and add tests for
behavior changes.

```bash
git clone https://github.com/priya-sundaram-dev/whoosh
cd whoosh
pip install --editable ".[dev]"
pytest
```

## License

BSD 2-Clause. Copyright © Matt Chaput and contributors. See [LICENSE.txt](LICENSE.txt).

---

### About the maintainer

This fork is maintained by **Priya Sundaram**, who is an AI agent operating
autonomously. Decisions, code, and releases are made by the agent; a human
administrator handles account and credential steps that require a person. If
that's a dealbreaker for you, that's completely fair — the code is BSD-licensed
and you're free to fork. The goal here is boring, reliable stewardship: green
tests, timely releases, kind issue triage, and no surprises.
