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

## Done (3.29.0 — released 2026-07-28)

- [x] **Complete public-API type hints for the read/write/spell surface.**
      `whoosh.reading` (`IndexReader` public read API + `TermInfo`, gh#64),
      `whoosh.writing` (`IndexWriter` public write API, gh#62), and
      `whoosh.spelling` (`Corrector`/`Correction`/`QueryCorrector`, gh#61) are
      now annotated end-to-end, joining the already-typed `index`, `fields`,
      `qparser`, `searching`, `sorting`, `scoring`, `highlight`, and `query`
      layers. A `mypy` smoke job and `tests/typing_smoke.py` guard the surface
      against regressions. Types are correct-only, never fabricated.

## Done (3.32.0–3.33.1 — released 2026-07-31 … 2026-08-04)

- [x] **MCP server, first-class and installable (3.32.0).** The
      [Model Context Protocol](https://modelcontextprotocol.io/) integration
      graduated from an example to a supported module — `whoosh.mcp`, a
      `whoosh-mcp` console script, and a `whoosh3[mcp]` optional dependency —
      so you can serve a folder of your own docs to an AI agent as `search` and
      `fetch` tools with `pip install "whoosh3[mcp]"` and `whoosh-mcp ~/notes`,
      pure Python, no server, no native deps. The `SearchCore` class has no MCP
      dependency, so it's reusable behind any agent framework and unit-testable
      on its own. A [Docker image](https://priya-sundaram-dev.github.io/whoosh/whoosh-mcp-server-agent-search-tool.html)
      (3.33.0) lets it run without a local Python environment, and the server
      now fails with a single actionable line — not a traceback — when the
      optional `mcp` SDK is missing (3.33.1). Covered by `tests/test_mcp.py`.
- [x] **`whoosh.analysis` typing sweep essentially complete (through 3.33.0).**
      The coordinated, module-at-a-time effort — mostly driven by first-time
      contributors — has landed for `tokenizers` (gh#72, by
      [@mani787060](https://github.com/mani787060)), `filters` (gh#76, by
      [@CrucialVansh](https://github.com/CrucialVansh)), `morph` (gh#77, by
      [@mani787060](https://github.com/mani787060)), `acore` (gh#80), `ngrams`,
      `analyzers` (gh#87, by [@Kiet-B](https://github.com/Kiet-B)), and finally
      `intraword` (gh#82). The sweep is now complete across `whoosh.analysis`.
      Types are correct-only, never fabricated, and guarded by the `mypy` smoke
      job plus `tests/typing_smoke.py`.

## Done (3.34.0–3.36.0 — released 2026-08-08)

- [x] **First-class LangChain retriever (3.34.0).** `whoosh.langchain` ships a
      `WhooshSearch` store and a `make_whoosh_retriever(...)` helper so Whoosh
      can be the retrieval half of a RAG pipeline — lexical BM25F search with
      **no vector database and no API key**, pure Python. The module imports
      cleanly whether or not `langchain-core` is installed (it degrades to a
      clear error only when you actually build a retriever), so it never breaks
      a plain `import whoosh`. Covered by `tests/test_langchain.py` and written
      up in the [local-RAG guide](https://dev.to/priyasundaram/a-local-rag-retriever-in-pure-python-no-vector-db-no-api-key-with-whoosh-2k92).
- [x] **First-class LlamaIndex retriever (3.35.0).** `whoosh.llamaindex`
      exposes a `BaseRetriever` implementation usable on its own or inside a
      LlamaIndex `QueryFusionRetriever` for hybrid lexical+vector setups. Same
      contract as the LangChain module: imports without `llama-index-core`
      present and fails only at construction with an actionable message.
      Covered by `tests/test_llamaindex.py`, with a
      [retriever landing page](https://priya-sundaram-dev.github.io/whoosh/whoosh-llamaindex-retriever.html).
      These two integrations make Whoosh a drop-in keyword retriever for the
      RAG ecosystem while keeping the core dependency-free — heavy framework
      code stays optional, per the guiding principles.
- [x] **Acronyms and tech tokens are searchable (3.36.0).** The default
      `StandardAnalyzer` splits and drops tokens like `R&D`, `C++`, `C#`,
      `.NET`, and `AT&T`, so notes containing them were unfindable — a papercut
      reported repeatedly downstream (e.g. flatnotes#276). Whoosh now ships a
      `TechAnalyzer()` (a scoped `RegexTokenizer` that preserves these shapes
      most-specific-first, leaving ordinary hyphenation untouched), a runnable
      [`examples/acronyms.py`](examples/acronyms.py), a cookbook recipe, and
      end-to-end regression tests (`tests/test_example_acronyms.py`) that
      contrast it against the default analyzer.

## Done (3.38.0–3.42.0 — released 2026-08-09 … 2026-08-21)

- [x] **Tiny-block compression skip on the write path (3.42.0).** Building on
      the format-safe indexing work above, the `whoosh3` codec now skips zlib
      for postings blocks below a *measured* 80-byte crossover
      (`COMPRESSION_MIN_SIZE`), so single-posting blocks of rare terms — the
      long tail of any Zipfian corpus — are stored uncompressed instead of being
      *expanded* by zlib's header overhead. The per-block compression flag is
      written into the block header and honoured on read, so the change is fully
      format-compatible. Contributed by
      [@tltaylor1](https://github.com/tltaylor1) (gh#100, closes gh#99), whose
      pre/post-size instrumentation found the crossover empirically rather than
      guessing. A latent dead-store that had been silently disabling the older
      skip was fixed in the same release.


- [x] **Real bugs fixed in the segment-merge path (3.40.0).** Three latent
      bugs in `whoosh.formats` `combine()` — the code that folds a term's
      posting values across segments during `optimize()`/`commit()` — were
      surfaced while type-checking the module: `Frequency.combine` called a
      non-existent `decode_value`, and `Characters`/`CharacterBoosts` transposed
      their per-position lookup, so merging those fields across segments raised
      `AttributeError`/`TypeError`. All three are fixed and pinned by round-trip
      regression tests (`tests/test_formats_combine.py`). Fix contributed by
      [@AdvaitVarhade](https://github.com/AdvaitVarhade) (gh#89, closes gh#88).
- [x] **First step on indexing throughput (3.39.0).** `FieldWriter.add_postings`
      no longer rebuilds the length-field name and re-resolves the length column
      reader on every posting; it binds a per-field length accessor once when
      the field changes (new `PerDocumentReader.doc_field_length_reader`). This
      hoists ~600k redundant string builds and look-ups out of the hot loop in a
      5,000-doc build, with byte-identical output and no on-disk format change —
      the first format-safe step of the profiled indexing work in
      [Later / exploring](#later--exploring).
- [x] **New "Improving recall" guide (3.40.0).** A
      [walkthrough](https://priya-sundaram-dev.github.io/whoosh/docs/recall.html)
      of stemming, `Variations`, fuzzy terms, did-you-mean spelling correction,
      and pseudo-relevance feedback for when searches return too few results.
- [x] **Community typing sweep continues across the storage/read layer.** With
      new first-time contributors: `whoosh.formats` (gh#89, by
      [@AdvaitVarhade](https://github.com/AdvaitVarhade)), `whoosh.idsets`
      (gh#86), `whoosh.externalsort` (gh#91, by
      [@ShlokShar](https://github.com/ShlokShar)), `whoosh.fields` (gh#94, by
      [@TheGittyPerson](https://github.com/TheGittyPerson)), `whoosh.columns`
      base classes (gh#96, by [@DebayanSen96](https://github.com/DebayanSen96)),
      and the `IndexReader` context-manager methods (gh#98, by
      [@Muhammad08-dot](https://github.com/Muhammad08-dot)) are now annotated,
      each guarded by the `mypy` smoke job. Types are correct-only, never
      fabricated. `whoosh.reading` and `whoosh.collectors` were the last two
      storage/read-layer modules left open here; both were completed in 3.43.0
      (see below).

## Done (3.43.0 — released 2026-08-22)

- [x] **Concrete-reader and collector typing scope complete (gh#3).** The
      public reader and collector API is now fully annotated end-to-end. This
      release typed the two concrete multi-/empty-index readers in
      `whoosh.reading` — `MultiReader` (returned by `ix.reader()` when an index
      has more than one segment) and `EmptyReader` — so that, together with the
      already-typed `IndexReader` base and `SegmentReader`, every built-in
      reader mirrors the base contract. `whoosh.collectors` — the `Collector`
      base and the `ScoredCollector`/`TopCollector`/`UnlimitedCollector`
      scoring path — was typed in the same scope. An `IndexReader.cursor()`
      method was added to the base class so the cursor interface is part of the
      documented, type-checked reader contract (all three concrete readers
      already implemented it).
- [x] **Three correctness fixes surfaced by the typing work.** No on-disk
      format change and no runtime behaviour change for the built-in readers:
      `SegmentReader.has_column` now honours its `bool` contract; a broken
      abstract `IndexReader.doc_count()` body (referencing a non-existent
      `deleted_count()`) now raises a clear `NotImplementedError` for third-party
      subclasses instead of `AttributeError`; and a dead pre-3.8
      `cached_property` fallback import was removed. `whoosh.reading` and
      `whoosh.collectors` now type-check clean under the `mypy` smoke job.

## Done (3.44.0 — released 2026-08-23)

- [x] **`whoosh3[mcp]` moved to the MCP Python SDK 2.x (gh#111, gh#112).** The
      SDK renamed `FastMCP` to `MCPServer` (`mcp.server.MCPServer`) in its 2.0
      release; `whoosh.mcp` now imports and constructs `MCPServer`, and the `mcp`
      optional dependency is `mcp>=2`. The tool surface (`@server.tool()`,
      `list_tools()`, `run()`) is unchanged, so the `whoosh-mcp` console script
      and the "Whoosh as an MCP server" docs work as before. First contribution
      from @mayuriphad, with a packaging-format catch from @cclauss.
- [x] **The `ruff` lint gate is now meaningful (gh#104).** The CI `ruff check`
      step previously ran with `|| true`, hiding 457 latent findings. The run
      now fails for real: genuine style nits were fixed automatically and the
      intentional patterns Whoosh relies on (function-local lazy imports, naive
      `DATETIME` handling, deliberate blind-except guards) are suppressed with
      documented rationale rather than silently ignored. No behaviour change.
- [x] **Quieter multiprocess indexing (gh#113).** The `os.fork()`
      `DeprecationWarning` that CPython 3.12+ emits when `MpWriter` forks with
      threads alive is scoped out via `filterwarnings`, and the `procs=`
      docstrings point users at `start_method="spawn"`/`"forkserver"` for
      fork-free multiprocess indexing. A forward-compatibility regression test
      exercises the default indexing path under a non-`fork` context (thanks
      @cclauss). Documentation/comment typos were also swept with codespell
      (gh#114, @cclauss).

## Now (next patch/minor)

- [x] **Python 3.14 support (3.11.0).** Verified the full suite passes on the
      latest stable CPython (3.14.0, released 2025-10-07), added it to the CI
      matrix, and shipped the `Programming Language :: Python :: 3.14`
      classifier. Whoosh now supports 3.10–3.14.
- [ ] Triage the inherited issue backlog; label, reproduce, close stale. Two
      long-standing bugs already fixed (gh#99, gh#116); more to review.
- [x] **Python support policy.** CI now also exercises the 3.15 / 3.15t
      release candidates (non-blocking until 3.15.0 final; gh#104 follow-up).
      Python 3.9 reached upstream end-of-life in October 2025, so the floor was
      raised to **3.10** (gh#124), unblocking modern typing constructs without
      version guards. `pip` respects `requires-python`, so deployments still on
      3.9 keep resolving the last 3.9-compatible release (3.44.0) — nothing
      breaks for existing users. Announced in the changelog before it landed.
- [x] **`whoosh.analysis` typing sweep complete (gh#82, in `[Unreleased]`).**
      The last self-contained analysis module, `whoosh.analysis.intraword`
      (`CompoundWordFilter`, `BiWordFilter`, `ShingleFilter`,
      `IntraWordFilter`), is now typed end-to-end and clean under both `mypy`
      and `ruff`. `Token`'s optional positional attributes (`pos`, `startchar`,
      `endchar`) are now declared on the class, and the four filters are
      exercised in `tests/typing_smoke.py` so the public typing stays
      CI-guarded.
- [x] **`whoosh.idsets` fully type-annotated (gh#86, shipped 3.38.0).** The
      whole doc-id set surface (`DocIdSet`, `BitSet`, `OnDiskBitSet`,
      `SortedIntSet`, `ReverseIdSet`, `RoaringIdSet`, `MultiIdSet`) is typed
      end-to-end and clean under both `mypy` and `ruff`. Annotating it surfaced
      and fixed two real bugs (`RoaringIdSet` `OverflowError` for ids ≥ 65536;
      `OnDiskBitSet.__repr__` `AttributeError`), each now covered by a
      regression test.
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
      construct directly, and the boolean combinators in
      `whoosh.query.compound` (gh#52): `And`, `Or`, `DisjunctionMax`, and
      `AndNot`, the queries most programs build via the `&`/`|` operators, and
      the wrapping query classes in `whoosh.query.wrappers` (gh#53): `Not`
      (the `-` operator), `ConstantScoreQuery`, `WeightingQuery`, and the
      `WrappingQuery` base.
      Deeper coverage of *internal*
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

- [ ] **Indexing throughput (profiled, contributor-ready).** Whoosh's honest
      weakness vs. SQLite FTS5 is index-build speed, so it's worth being
      precise about *where* the time goes. Profiling a 5,000-doc / ~600k-token
      build (`StandardAnalyzer`, positions on) shows analysis is only ~10% of
      wall time; the other ~90% is the postings write pipeline. The largest
      addressable costs there, in order:
    - **Positions encoding via `pickle` — investigated, not worth it in pure
      Python (2026-08-09).** `whoosh.formats.Positions.encode` serialises each
      term's position-delta list with `dumps(deltas, 2)` (~520k calls in a
      5,000-doc `StandardAnalyzer` build), so it looked like the obvious next
      target: a varint/group-varint delta codec should be smaller and faster.
      A prototype (zig-zag varints on the shared `whoosh.util.varints`
      primitives, self-describing so legacy pickle postings keep decoding with
      no migration — verified with a fuzz round-trip and a legacy-index
      end-to-end read) was built and measured against the previous release
      before any release, exactly as this section requires. The result was a
      **net non-improvement**, for two reasons that are easy to miss on paper:
        1. **CPython's `pickle` is a C extension; our varint codec is pure
           Python.** For these short lists of small ints, C-`pickle` *encodes*
           the delta list faster than a per-int Python varint loop can, and
           decodes it faster too. Measured on the positions-heavy build,
           indexing went from ~4.36s to ~4.46s (a ~2% *regression*), not a
           speedup.
        2. **Block-level `zlib` already captures most of the space win.**
           Postings blocks are `zlib`-compressed on disk, so the ~50% shrink of
           the *raw* per-term payload collapses to only **~2.5%** off the total
           optimized index (7.30 MB → 7.12 MB in the same build).
      A pure-Python re-encoding of a value that C-`pickle` already handles well,
      guarded forever by a format branch, is not a good trade for ~2.5% on disk
      and a small speed cost. The realistic path to a genuine win here would be
      an *optional* C/Rust accelerator (see the accelerators item below) or
      tunable block compression — not a pure-Python format change. Leaving this
      documented so it isn't re-attempted. The profiling above still stands: the
      postings-write pipeline dominates build time, so future throughput work
      should target the pipeline (batching, fewer allocations, the length-lookup
      hoist already shipped) rather than the value codec.
    - **Per-posting field-length lookups.** *(Done — Unreleased.)*
      `FieldWriter.add_postings` used to call `doc_field_length(docnum,
      fieldname)` once per posting, rebuilding the `_lenfield` string and
      re-resolving the length column reader each time. It now binds a per-field
      length accessor once when the field changes
      (`PerDocumentReader.doc_field_length_reader`, with a fast `whoosh3`
      override) and calls it once per posting — byte-identical output, no
      format change, a few percent off build wall-time.
    - **Block compression (`zlib.compress`).** *(Documented — Unreleased.)*
      The `whoosh3` codec's per-block `zlib` level was already a constructor
      parameter; it is now a documented, supported knob. Pass
      `ix.writer(codec=W3Codec(compression=N))` (0–9) to trade indexing CPU for
      index size — measured across levels on a 3,000-doc text index, `0`
      (no compression) is ~2.3x larger than the default `3`, while `9` is only
      ~2% smaller than `3`. See the
      [batch-indexing guide](https://priya-sundaram-dev.github.io/whoosh/docs/batch.html).
      Blocks below the `zlib`-header break-even are left uncompressed
      automatically, and the level is recorded per block so indexes read back
      transparently regardless of the writer's setting.
    Any change here ships only with the benchmark suite
    ([`benchmark/regression.py`](benchmark/regression.py)) showing a real,
    reproducible gain and green cross-version CI.
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
      runnable [Flask search app](examples/flask_app.py) and a runnable
      [Django search app](examples/django_app.py) (portable full-text search
      without PostgreSQL) alongside the FastAPI one.
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
