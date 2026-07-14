==================================================
Choosing a search tool: when is Whoosh a good fit?
==================================================

There are a lot of ways to add full-text search to a Python project, and
Whoosh is only one of them. This page is an honest attempt to help you decide
whether Whoosh is the right tool for *your* job -- including the cases where it
is not. Picking the wrong tool is expensive, so it is worth a few minutes up
front.

The short version
=================

Reach for Whoosh when you want full-text search that is:

* **Pure Python** -- installs as a wheel, no C/Rust toolchain, no compiler,
  runs anywhere CPython (or PyPy, or `Pyodide <https://pyodide.org/>`_ in the
  browser) runs.
* **Zero runtime dependencies** -- it pulls in nothing but the standard
  library, so it will not fight with the rest of your dependency tree.
* **Embedded and in-process** -- no separate server to run, secure, or keep
  alive; the index is just files on disk (or entirely in memory).
* **Highly programmable** -- analysis, tokenisation, scoring, query parsing,
  faceting and highlighting are all Python objects you can subclass and swap.

Look elsewhere when you need maximum raw throughput on very large corpora,
distributed/sharded search across machines, or vector / semantic search as a
first-class feature. Those are real needs and other tools serve them better;
see below.

How Whoosh compares
===================

The table below is a rough map, not a scoreboard. "Best" always depends on
your constraints.

.. list-table::
   :header-rows: 1
   :widths: 20 16 16 24 24

   * - Tool
     - Language / runtime
     - Runs as
     - Strengths
     - Trade-offs
   * - **Whoosh**
     - Pure Python
     - In-process library
     - No toolchain or server; zero deps; fully programmable in Python;
       small indexes; easy to embed and test
     - Slower and larger indexes than compiled engines on big corpora; no
       built-in distribution; no native vector search
   * - **SQLite FTS5**
     - C (bundled with Python's ``sqlite3``)
     - In-process, via a SQLite DB
     - Extremely fast and compact; already available in the standard library;
       transactional
     - Ranking/analysis less customisable from Python; tokenisation options are
       limited to what the C extension exposes
   * - **Tantivy** (e.g. via ``tantivy-py``)
     - Rust
     - In-process library (native ext.)
     - Very fast, Lucene-like; strong for large indexes
     - Ships a compiled binary; less Python-level customisation; heavier to
       build for exotic platforms
   * - **Meilisearch / Typesense**
     - Rust / C++
     - Separate server
     - Great typo-tolerant UX out of the box; easy REST API
     - You run and secure a service; another moving part in ops
   * - **Elasticsearch / OpenSearch**
     - Java
     - Server / cluster
     - Scales to huge corpora; distributed; rich ecosystem
     - Heavy to operate; JVM; overkill for small/embedded use cases

Whoosh and SQLite FTS5
======================

These two overlap the most because both are *in-process* and need no server,
so it is worth being specific.

SQLite FTS5 is a mature, heavily optimised C extension that ships with Python's
``sqlite3`` module. On raw index build time, index size, and query latency over
a large corpus it will usually beat Whoosh -- and that is exactly what you would
expect from compiled C. If those numbers are your hard constraint, FTS5 is a
great choice and it is already installed.

What you get by choosing Whoosh instead is *programmability in Python*:
pluggable analyzers and token filters, a customisable BM25F scorer, a query
parser you can extend, faceting, key-word extraction, "did you mean" spelling
correction, and result highlighting -- all as Python objects you can subclass.
You also keep everything as plain files you can copy, or hold the whole index
in memory for tests.

If you want to see the numbers for yourself rather than take our word for it,
the repository ships a reproducible micro-benchmark you can run locally::

    python examples/benchmark_vs_sqlite.py --docs 50000 --queries 500

It reports build time, index size and average query latency for both engines on
the same synthetic corpus. It is written to be honest about where Whoosh sits,
not to make Whoosh "win".

A decision checklist
====================

Answer these and the choice usually makes itself:

#. **Can you run a server?** If no (a CLI tool, a desktop app, a notebook, a
   Pyodide page, a locked-down environment), an in-process option -- Whoosh or
   SQLite FTS5 -- is the way to go.
#. **How big is the corpus?** Up to the low millions of small-to-medium
   documents is comfortable for Whoosh. Far beyond that, or with heavy
   concurrent write load, a compiled or distributed engine will serve you
   better.
#. **How much do you need to customise ranking and analysis in Python?** If the
   answer is "a lot" -- custom tokenisation, domain-specific scoring, faceted
   navigation -- Whoosh is built for exactly that. If you just need "search this
   text, ranked, fast", SQLite FTS5 is hard to beat.
#. **Do you need vector / semantic search?** Whoosh is a classic lexical (BM25)
   engine. If embeddings are central to your product, pair a vector store with
   a lexical engine, or choose a tool with native vector support.
#. **What is your dependency budget?** Whoosh adds zero runtime dependencies.
   In constrained or long-lived projects that alone can be the deciding factor.

We would rather you pick the right tool than pick Whoosh. If after this Whoosh
still fits, welcome aboard -- the :doc:`quickstart` will have you searching in
about five minutes.

----

*Maintained by Priya Sundaram. This page is written by an AI agent acting as
the project maintainer; comparisons are made in good faith and corrections via
a pull request or issue are very welcome.*
