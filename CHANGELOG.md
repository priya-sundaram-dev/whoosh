# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/) and the format is loosely based on
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed

- `CoordMatcher` (used by `OrGroup.factory(scale)`) no longer scores every hit
  `0.0` when a query resolves to a single term matcher. The SQR coordination
  factor `(termcount - 1) / termcount` collapses to `0` for a single term —
  the common case for a single-word query over a `MultifieldParser`, where the
  term survives in only one field — which zeroed all scores and left ranking in
  arbitrary docnum order. A single-term query now returns the unmodified score
  (there is nothing to coordinate over); genuine multi-term coordination
  penalties are unchanged. Thanks to @bet0x for the detailed root-cause report.

### Changed

- Typing: added parameter and return annotations to all public functions in
  `whoosh.util.text` (`byte`, `first_diff`, `prefix_encode`,
  `prefix_encode_all`, `prefix_decode_all`, `natural_key`, `rcompile`)
  (gh#173, part of gh#121). `rcompile` now declares `re.Pattern[str]`, which
  let the checker flag and fix the downstream `expression` parameters in
  `whoosh.analysis.analyzers` (now `str | re.Pattern[str]`, matching the
  tokenizers) and the `text`/`pos` parameters of the `whoosh.qparser.dateparse`
  parser classes.
- Typing: added parameter and return annotations to all public functions in
  `whoosh.util.varints` (`varint`, `signed_varint`, `varint_to_int`,
  `decode_signed_varint`, `read_varint`, and the internal `_varint`).
  `read_varint` declares its `readfn` parameter as
  `Callable[[int], bytes]` (gh#178, part of gh#121).

## [3.49.7] - 2026-09-03

### Fixed

- Date-range queries whose lower bound is a bare time of day and whose upper
  bound resolves straight to a concrete instant — for example
  `added:[noon TO now]` or `added:[noon TO -1 week]` — no longer crash the
  parser with `AttributeError: 'datetime.datetime' object has no attribute
  'ceil'`. The range-disambiguation step compared `start.floor().time()` with
  `end.ceil().time()` by calling the `adatetime` methods directly, but a bound
  that resolves to a plain `datetime` (like `now` or a relative offset) has no
  such methods. Both sides now go through the module-level `floor()`/`ceil()`
  helpers, which pass a concrete `datetime` through unchanged, so these
  ordinary "time-of-day until a fixed instant" ranges resolve correctly.

### Changed

- Typing: `DocIdSet.__eq__` now narrows its `object` argument to an
  `Iterable` (returning `NotImplemented` for non-iterables, the correct
  `__eq__` contract) instead of carrying a malformed
  `# type: ignore[call-overload]` comment. Clears the last single-instance
  `ty` rule (`invalid-ignore-comment`), which is dropped from the `[tool.ty]`
  ignore list (gh#144, part of gh#121). Comparing an id set with a
  non-iterable now returns `False` rather than raising `TypeError`.
- Typing: added parameter and return annotations to all public functions in
  `whoosh.util.numeric` (`bits_required`, `typecode_required`, `max_value`,
  `bytes_for_bits`, `to_sortable`, `from_sortable`, `float_to_sortable_long`,
  `sortable_long_to_float`, `float_to_byte`, `byte_to_float`,
  `length_to_byte`). No runtime behaviour is changed (gh#171, part of gh#121).

## [3.49.6] - 2026-09-02

### Fixed
- A double-quoted value on a self-parsing "atomic" field (`BOOLEAN`,
  `NUMERIC`, `DATETIME`, …) is now handed to the field's own `parse_query`,
  exactly like the unquoted and single-quoted forms, instead of being
  tokenized as free text. Previously `PhrasePlugin` sent the quoted text
  through the field's analyzer: a `BOOLEAN` field has none, so `flag:"true"`
  raised a bare `Exception: … field has no analyzer`, and a `NUMERIC` field's
  identity analyzer produced the raw string term `num:"42"` → `Term("num",
  "42")` that could never match the encoded numeric value (`num:42` and
  `num:'42'` both worked). N-gram fields (`NGRAM`/`NGRAMWORDS`) are
  self-parsing too but genuinely tokenize their input, so they keep producing
  `Phrase` queries. Mirrors
  [`stumpylog/whoosh-compat`](https://github.com/stumpylog/whoosh-compat)
  (`DIVERGENCES.md`, entry 38).

## [3.49.5] - 2026-09-02

### Fixed
- A trailing-star wildcard whose prefix contains a `[` character class no
  longer folds to a `Prefix` query, which silently dropped the class body.
  `[` is one of `Wildcard.SPECIAL_CHARS` (`"*?["`), but both fold sites —
  `Wildcard.normalize()` (`whoosh/query/terms.py`) and
  `WildcardPlugin.do_wildcards` (`whoosh/qparser/plugins.py`) — only tested
  for `*`/`?` before rewriting `text*` to `Prefix(text)`. A pattern like
  `202[0-3]*` therefore collapsed to the literal prefix `202[0-3]`, matching
  nothing instead of `2020`–`2023`. Both sites now keep such a pattern a
  `Wildcard`; a plain trailing star with no class (`abc*`) still folds to a
  `Prefix` as before. Mirrors paperless-ngx issue
  [#13568](https://github.com/paperless-ngx/paperless-ngx/issues/13568) and
  the differential test suite of
  [`stumpylog/whoosh-compat`](https://github.com/stumpylog/whoosh-compat)
  (`DIVERGENCES.md`, entry 13).

## [3.49.4] - 2026-09-01

### Fixed
- A truncated date value with a dangling separator no longer silently widens
  into a whole month or year. Two independent code paths shared the defect.
  In the `DateParserPlugin` grammar, the progressive numeric sequence advanced
  its reported end position past a separator *before* the element after it was
  tried, and still reported having consumed that separator when the element
  failed — so `2005-01-` parsed as all of January 2005 and `2005-01-01T` as
  that whole day, with the leftover fragment ANDed onto the query as stray
  terms. A non-whitespace separator is now consumed only provisionally, so a
  dangling `-`/`.`/`:`/`/`/`T` makes `ToEnd` reject the fragment instead.
  Separately, `DATETIME._parse_datestring` stripped `-`, `.` and spaces
  unconditionally, so `date:2005-01-` collapsed to `200501` and matched all of
  January 2005 even with no date plugin installed; a leading or trailing
  separator is now rejected as an unparseable date. Well-formed values —
  including natural truncations without a dangling separator (`2005-01`,
  `2005`) and the bare-digit form (`20050101`) — are unaffected. Surfaced by
  the differential test suite of
  [`stumpylog/whoosh-compat`](https://github.com/stumpylog/whoosh-compat)
  (`DIVERGENCES.md`, entry 54).

## [3.49.3] - 2026-09-01

### Fixed
- `FieldsPlugin` no longer drops text when a query contains two or more
  consecutive `word:` runs that don't name a real field. `do_fieldnames`
  tracked only the most recently seen rejected candidate, so in a run like
  `aa:bb:cc` (neither `aa` nor `bb` a field) the first candidate's text was
  silently discarded and the query collapsed to `bb:cc`, with the user's
  `aa:` gone without a trace. All consecutive rejected candidates are now
  accumulated in order before being folded back onto the following term.
  The same change fixes a companion span bug: after a demoted candidate was
  merged into the surviving node's text, that node's `startchar` still
  pointed at its own original position, so `endchar - startchar` no longer
  matched `len(text)`; the span is now widened to cover the whole merged
  run. Surfaced by the differential test suite of
  [`stumpylog/whoosh-compat`](https://github.com/stumpylog/whoosh-compat)
  (`DIVERGENCES.md`, entry 57).
- `RangePlugin` now recognizes the `TO` range separator only as a whole word,
  never inside an adjacent token. The tagger's regex matched a bare `[Tt][Oo]`
  with no word-boundary requirement, so the "to" that *starts* an end value
  was mistaken for the separator: `[TO today]` misparsed as start=`"TO"`/
  end=`"day"` (instead of an open-start range up to `today`), and
  `[total 5]` — which contains no real separator at all — became a garbage
  empty-start range with end `"tal 5"` (on a DATE field the captured `"TO"`
  even raised `"'TO' is not a parseable date"`). The separator is now matched
  as `\b[Tt][Oo]\b`, so genuine ranges (`[a TO b]`, `[TO b]`, `[into TO 5]`,
  quoted and exclusive bounds) parse unchanged while these mid-word
  lookalikes no longer tag as ranges. Surfaced by the differential test suite
  of [`stumpylog/whoosh-compat`](https://github.com/stumpylog/whoosh-compat)
  (`DIVERGENCES.md`, entry 56) — thanks for the careful cross-checking.

## [3.49.2] - 2026-09-01

### Fixed
- `DateParser.date_from` overrides are now honored for bracketed range bounds,
  not just single/keyword values (#161). Previously `DateParserPlugin.range_to_dt`
  reached past the configured parser to the bare grammar object, so any
  customization a `DateParser` subclass added in its own `date_from` (timezone
  normalization, clamping, logging, …) applied to `added:2020-06-15` but was
  silently skipped for both bounds of `added:[2020-06-15 TO 2020-07-15]`.
  Bound parsing now routes through `DateParser.date_from` via a new
  `disambiguate=False` seam that preserves the "parse each bound raw,
  disambiguate the whole span together" contract `range_to_dt` depends on.
  Overrides predating the seam (a fixed signature without `disambiguate`/
  `**kwargs`) fall back to the previous raw-grammar path, so they keep working
  unchanged rather than raising. Surfaced by the differential test suite of
  [`stumpylog/whoosh-compat`](https://github.com/stumpylog/whoosh-compat)
  (`DIVERGENCES.md`, entry 12) — thanks for the careful cross-checking.

## [3.49.1] - 2026-08-29

### Fixed
- `adatetime.date()` raised `TypeError: function takes at most 3 arguments
  (4 given)` on every call — it passed `tzinfo=timezone.utc` to
  `datetime.date()`, which (unlike `datetime`) accepts no `tzinfo` (a `date`
  is naive by definition). The stray keyword is removed; `adatetime.date()`
  now returns the expected `datetime.date`. Caught by @SantiagoDaleffe while
  clearing the `ty` `unknown-argument` rule (#158).

### Internal
- Cleared and un-ignored the `ty` `unknown-argument` rule (#158, 10 violations):
  widened the abstract base signatures `IndexWriter.commit`/`cancel` and
  `IndexReader.postings` with `**kwargs: Any` so they honour the arguments their
  concrete subclasses accept (`optimize=`, `merge=`, `scorer=`, …), plus two
  targeted `# ty: ignore[unknown-argument]` on mixin `self.__class__(...)`
  re-instantiations where the concrete constructor can't be known statically.
  Thanks to @SantiagoDaleffe.
- Replaced a few opaque `Any` parameter annotations with the concrete types the
  code and docstrings already document, so editors and type checkers can help
  callers: `Query.matcher(context=...)` is now `SearchContext | None`,
  `FieldType.sortable_terms(ixreader=...)` and `Expander(ixreader=...)` take an
  `IndexReader`, and `BitSet`/`OnDiskBitSet`'s on-disk methods take a
  `StructFile`. The concrete `ixreader` type also surfaced that the base
  `FieldType.sortable_terms` returns an `Iterable[bytes]` (from
  `reader.lexicon()`), not an `Iterator[bytes]`; the annotation is corrected.
  Genuinely polymorphic boundaries — term text and stored field values, which
  legitimately accept `str`, numbers, `bytes`, … — keep `Any`, since a narrower
  type there would be wrong. Thanks to @cclauss for the review that prompted
  this analysis.

## [3.49.0] - 2026-08-28

### Added
- **Parallel-indexing example for free-threaded builds** (`examples/parallel_indexing.py`).
  The blessed fan-out/fan-in pattern the concurrency guide points no-GIL users
  at: split the corpus across worker threads, have each thread build its own
  sub-index (keeping the single-writer contract — no shared writer, no lock
  contention), then merge the finished sub-indexes into one ordinary index with
  `IndexWriter.add_reader()`. Ships with a serial-vs-parallel timing harness
  that reports the runtime's GIL status and a correctness check that the merged
  index equals a serial build. On a GIL build the parallel path matches the
  serial baseline (merge overhead, expected); on a free-threaded `3.13t`/`3.14t`
  build the pure-Python indexing scales across cores. Covered by
  `tests/test_example_parallel_indexing.py`. Documented in the concurrency
  guide (`threads.rst`).

### Internal
- Tightened `ty` static-typing enforcement by clearing and un-ignoring two more
  rules across the query/analysis layers: `no-matching-overload` (#155) and
  `invalid-return-type` (#156, 28 violations). As part of the latter, the
  `__eq__` methods that used the `other and self.__class__ is other.__class__`
  form were switched to `type(self) is type(other)`, which also fixes a latent
  correctness bug: objects that are falsy when empty (`CompositeAnalyzer`,
  `CompoundQuery`) previously mis-compared — e.g. `And([]) == And([])` no longer
  short-circuits to a non-`True` result. Thanks to @SantiagoDaleffe for both.

### Documentation
- Concurrency guide (`threads.rst`) now opens with a per-object quick-reference
  table spelling out what is safe to share across threads: `Index`/`FileIndex`
  and a built `Schema` are shareable; `IndexReader`/`Searcher` are one-per-thread
  (file-cursor state); a plain `IndexWriter` is single-writer (holds the write
  lock); `BufferedWriter` is designed to be shared and serializes its state with
  an internal `threading.RLock`; `AsyncWriter` is the helper for coping with the
  single-writer rule. The contract is called out as applying equally to
  free-threaded (no-GIL, PEP 703) builds. Completes the "document the
  concurrency contract per component" roadmap item.

## [3.48.1] - 2026-08-26

### Fixed
- Whoosh 2.7.4 → whoosh3 migration regressions in span queries and hits,
  reported by @BenitoKme (#153):
  - Searching with `SpanNot` raised `IndexError: tuple index out of range`
    whenever the excluded (second) span did not match in a candidate
    document. `SpanNot._get_spans()` called `id()` on the exhausted "maybe"
    matcher; it now checks `is_active()` first (nothing to exclude → all
    spans from the first query pass through).
  - `str()` on any span query (`SpanNot`, `SpanNear`, `SpanOr`, ...) raised
    `NotImplementedError` from the base `Query.__str__`. Span queries have no
    dedicated query-language syntax, so `SpanQuery.__str__` now falls back to
    the well-defined `repr`.
  - `Hit.get(key[, default])` was missing, breaking dict-style
    `hit.get("field", fallback)` access that worked in Whoosh 2.7.4. The
    standard `dict.get` accessor is restored.
- `whoosh.support.bitstream.BitStreamReader.read` raised a tuple
  (`raise (IndexError, ...)`) instead of an exception on an out-of-range
  read, so callers got an unrelated `TypeError` rather than the intended
  `IndexError`. It now raises `IndexError` correctly. Surfaced by un-ignoring
  the `ty` `not-iterable`/`invalid-raise` rules (#152).

### Changed
- Type-checking hygiene: the `ty` rules `invalid-raise` and `not-iterable`
  are now enforced instead of ignored. This tightened a few re-raise sites in
  `filestore.py`/`index.py` (`except OSError as e: ... raise` instead of
  `sys.exc_info()`) and clarified test-double `children` attributes. Thanks
  @SantiagoDaleffe (#152).

## [3.48.0] - 2026-08-26

### Fixed
- `TimeLimitCollector` no longer crashes with `ValueError: signal only works
  in the main thread of the main interpreter` when a search is run from a
  worker thread (e.g. a threaded web server). The `SIGALRM` handler is now
  only armed on the main thread; off the main thread the collector falls back
  to its `threading.Timer`, which still enforces the time limit. Surfaced while
  auditing thread-safety under `pytest-run-parallel` (#146).

### Added
- CI now runs the pure-Python core under [`pytest-run-parallel`] on the
  free-threaded `3.14t` (and, as early-warning signal, `3.15t`) builds, executing
  every test across many worker threads to catch data races the GIL used to hide.
  Tests that mutate module/class globals or on-disk files directly are marked
  `@pytest.mark.thread_unsafe` and run serially; fixture-based thread-unsafety
  (`capsys`, `monkeypatch`, ...) is auto-detected by the plugin. Thanks @cclauss
  for the push toward free-threading readiness (#146).

  [`pytest-run-parallel`]: https://github.com/Quansight-Labs/pytest-run-parallel
- Property-based tests for `whoosh.support.base85` covering the invariants the
  module exists for: the alphabet being in ASCII order, fixed-width output, and
  encoded values sorting in the same order as the integers they encode -- the
  last asserted both directly and through `whoosh2`'s `sortable_int_to_text`
  and `sortable_long_to_text` (#139). Thanks @chmm195.

### Changed
- CI now installs dependencies with [`uv`](https://docs.astral.sh/uv/) (via
  `astral-sh/setup-uv`) across the test, docs, and publish workflows for faster,
  more reproducible installs. `actions/setup-python` still provisions the
  interpreters so the prerelease (3.15 RC) and free-threaded (`3.14t`/`3.15t`)
  matrix rows are preserved. Thanks @cclauss (#149).
- README now shows a `uv pip install whoosh3` quickstart alongside `pip` (#149).
- `whoosh.support.base85`'s module docstring now explains why the alphabet is
  in ASCII order and why it must not be replaced with `base64.b85encode`, whose
  alphabet is unordered (#139). Thanks @chmm195.

## [3.47.0] - 2026-08-25

### Fixed
- `GroupNode.apply` (and therefore `GroupNode.accept`) no longer raises
  `AttributeError`: a stale positional `self.type` argument referenced a
  non-existent attribute and mis-bound the `nodes`/`boost` parameters. Query
  syntax-tree transforms over group nodes now round-trip correctly, preserving
  `boost` and subnodes (#140). Thanks @SantiagoDaleffe.

### Added
- Type hints across the `whoosh.index.Index` abstract base class and the
  module-level functions `version_in`, `version`, and `clean_files`. The
  `Index` ABC now advertises a fully-annotated contract (return types on
  `refresh`, `reader`, `searcher`, `doc_count`, etc.), while the `create_in`
  and `open_dir` factory functions keep their concrete `FileIndex` return type
  so callers still see `.schema`/`.storage`. Closes #117. Thanks
  @SantiagoDaleffe for their first contribution!

### Internal / tooling
- Added the [auto-walrus](https://github.com/MarcoGorelli/auto-walrus)
  pre-commit hook and applied its safe assignment-expression rewrites across
  the codebase; bumped `pyproject-fmt` to v2.28.1 (#136). Thanks @cclauss.
- Enabled additional ruff rule sets (flake8-pie, flake8-raise, pygrep-hooks,
  pandas-vet, flake8-debugger) and applied their idiomatic fixes
  (`range(0, n)`→`range(n)`, chained `.endswith`/`.startswith`→tuple form,
  `not x is y`→`x is not y`, redundant `.keys()` removal, etc.) (#137). Thanks
  @cclauss.
- Enabled ruff's pycodestyle error (`E`) rules and cleaned up the flagged
  code: `type(x) == T`→`type(x) is T` (E721), `== True`/`== False`→truthiness
  in tests (E712), lambda assignments→`def` (E731), and `# noqa` for the
  intentional bare-`except`/ambiguous-name cases. Behavior-preserving (#138).
  Thanks @cclauss.
- Un-ignored the `empty-body` and `parameter-already-assigned` `ty` rules
  after removing a dead `parse_` stub and fixing the `GroupNode.apply` bug
  above (#140). Thanks @SantiagoDaleffe.
- Removed the dead Python-2-era byte codec `b85encode`/`b85decode` from
  `whoosh.support.base85`; both raised `TypeError` on Python 3 (float division
  used as a string multiplier/index) and were never imported or tested. The
  integer codec `to_base85`/`from_base85` used by the numeric fields is
  unchanged (#139).

## [3.46.0] - 2026-08-24

### Added
- `whoosh.mcp` now works across **every current MCP SDK** — the official MCP
  Python SDK 2.x (`mcp.server.MCPServer`) *and* 1.x
  (`mcp.server.fastmcp.FastMCP`), plus the standalone
  [FastMCP](https://github.com/jlowin/fastmcp) 2.x package (`fastmcp.FastMCP`).
  `build_mcp_server()` resolves the server class from whichever is installed;
  all three expose the identical `Server("name")` / `@server.tool()` /
  `server.run()` surface Whoosh uses, so no configuration is needed. The `mcp`
  extra is unpinned back to `mcp>=1` (both majors are supported), and a new
  `fastmcp` extra installs the standalone package: `pip install
  "whoosh3[fastmcp]"`. The "no SDK installed" error now points at both options.
  Builds on @mayuriphad's 2.x rename fix (#112) by keeping 1.x installs working.

### Internal / tooling
- Added a `ci:` block to `.pre-commit-config.yaml` in preparation for enabling
  the [pre-commit.ci](https://pre-commit.ci) App: `autofix_prs: false`, weekly
  hook `autoupdate`, and `skip: [zizmor]` (zizmor keeps running in CI). No
  behaviour change for contributors yet. Refs #133.

## [3.45.0] - 2026-08-24

### Internal / tooling
- Adopted the modern PEP 639 license declaration in `pyproject.toml` (#130):
  `license` is now the SPDX string `"BSD-2-Clause"` instead of the deprecated
  `{ text = ... }` table, and the redundant `License :: OSI Approved :: BSD
  License` classifier was dropped (a SPDX license expression cannot coexist
  with license classifiers). The build now requires `setuptools>=77`, which
  understands SPDX expressions and emits `License-Expression` metadata. This
  silences the `SetuptoolsDeprecationWarning` seen in the Pages build and keeps
  builds working past setuptools' 2027-02-18 removal deadline. Thanks @cclauss
  for the report.
- Swept residual `3.9` references left over from the Python 3.9 drop (#124):
  the docs (`index.rst`, `integrations.rst`, `migrating.rst`, `MIGRATING.md`),
  the roadmap, the demo/marketing pages (which advertised "Python 3.9–3.14"),
  and `.sonarcloud.properties` (which still listed 3.8/3.9) now all state the
  3.10–3.14 support range. Docs-only; thanks @cclauss for the catch.
- **Consolidated packaging/tooling config into `pyproject.toml`** (#125). The
  active pytest config (`addopts`, `filterwarnings`, `norecursedirs`, …) moved
  from `setup.cfg`'s `[tool:pytest]` into `[tool.pytest.ini_options]`, and
  coverage config into `[tool.coverage.run]`. Removed the now-redundant
  `setup.cfg`, `setup.py` shim (editable installs use PEP 660 via
  `setuptools>=64`), `requirements.txt` (`.`), and `requirements-dev.txt` (its
  contents were stale — `pytest` lives in the `dev` extra; `pythomata`/
  `versioneer` were unused). Behaviour is unchanged; the project is just easier
  to understand with one declarative config file. `docs/requirements.txt` is
  kept as the conventional Sphinx/Read-the-Docs build input. Thanks @cclauss.

### Removed
- **Dropped support for Python 3.9**, which reached end-of-life in October 2025.
  The minimum supported version is now Python 3.10. `pip` respects
  `requires-python`, so environments still on 3.9 will continue to resolve the
  last 3.9-compatible release (3.44.0) — nothing breaks for existing users, but
  new releases target 3.10+. This lets the codebase adopt modern typing
  constructs (e.g. `typing.TypeAlias`) without version guards. Thanks to
  @cclauss for proposing this (#124).

## [3.44.0] - 2026-08-23

### Changed
- **`whoosh3[mcp]` now targets the MCP Python SDK 2.x.** The SDK renamed
  `FastMCP` to `MCPServer` (`mcp.server.MCPServer`) in its 2.0 release
  (modelcontextprotocol/python-sdk#1732); `whoosh.mcp` was updated to import and
  construct `MCPServer`, and the `mcp` optional dependency is now `mcp>=2`. The
  tool surface (`@server.tool()`, `list_tools()`, `run()`) is unchanged, so the
  `whoosh-mcp` console script and the "Whoosh as an MCP server" docs work as
  before — but environments pinned to MCP SDK 1.x must upgrade. Thanks to
  @mayuriphad for finding and wiring up the 2.x API (their first contribution!)
  and @cclauss for the packaging-format catch. Closes #111 (#112).

### Internal / tooling
- Made the linter gate meaningful. The `ruff check` CI step previously ran with
  `|| true`, so 457 latent findings never failed the build (thanks to @cclauss
  for spotting this in #104). The lint run now passes for real: the ~80 genuine
  style nits were fixed automatically (double quotes, sorted imports, dropped
  `u""` prefixes, `Optional[x]` → `x | None` in files that already use
  `from __future__ import annotations`, `Tuple` → `tuple`, dict-`.items()`
  iteration), and the intentional patterns Whoosh relies on are now suppressed
  with documented rationale instead of being silently ignored: function-local
  lazy imports (`PLC0415`), naive `datetime` handling in the `DATETIME` field
  (`DTZ`), and deliberate blind-except guards around optional features
  (`BLE001`). No runtime behaviour changes.
- Fixed the broken CONTRIBUTING link in the pull-request template (#103), which
  pointed at a relative path that 404s from the PR-compose page; it now uses an
  absolute URL.
- Silenced the `os.fork()` `DeprecationWarning` noise that CPython 3.12+ emits
  when the multiprocessing `MpWriter` path forks while threads are alive: the
  warning is now scoped-out via `filterwarnings` in `setup.cfg` and the
  `MpWriter`/`procs=` docstrings point users at `start_method="spawn"` /
  `"forkserver"` for fork-free multiprocess indexing (thanks @cclauss, #113).
- Swept documentation, docstring and comment typos across `src`, `tests` and
  `docs` with codespell — no functional changes (thanks @cclauss, #114).

### Testing
- Added a forward-compatibility regression test for `MpWriter` that runs the
  default (`start_method=None`) indexing path under a non-`fork` default
  multiprocessing context. The interpreter default is `fork` on Linux today
  but is already `spawn` on macOS/Windows and becomes `forkserver` on Linux in
  CPython 3.14; the test (run in a subprocess so the process-global start
  method can be forced safely) confirms the `SubWriterTask`-driven default path
  still commits correctly, locking in the guarantee that `procs=N` indexing
  keeps working as CPython moves away from fork-by-default.
- Added `tests/test_examples_runnable.py`, a smoke test that runs the
  dependency-free, no-argument `examples/*.py` scripts (including the front-door
  `quickstart.py` and `tutorial.py`) end to end in a throwaway directory and
  asserts a clean exit. Nothing previously guarded these copy-paste examples, so
  an API refactor could have silently broken the project's own onboarding code.

## [3.43.0] - 2026-08-22

Completes the concrete-reader and collector scope of the public-API typing
umbrella (#3), and ships three correctness fixes that typing surfaced along the
way. No on-disk format change; runtime behaviour of the built-in readers and
collectors is unchanged.

### Added
- Type hints for the `MultiReader` and `EmptyReader` concrete readers in
  `whoosh.reading`, completing the concrete-reader scope of the public-API
  typing umbrella (#3): every method on the multi-segment reader (returned by
  `ix.reader()` when an index has more than one segment) and the empty-index
  reader now carries parameter and return types that mirror the `IndexReader`
  base contract. Also added `IndexReader.cursor()` to the base class so
  `cursor` is part of the documented, type-checked reader interface (all
  concrete readers already implemented it). `mypy` on `reading.py` is clean and
  the reader/search/column suites pass (854 tests).
- Type hints for the `SegmentReader` concrete reader in `whoosh.reading` (the
  reader you get from `ix.reader()` on a single-segment index), completing the
  primary concrete-reader scope under the public-API typing umbrella (#3).
  Every method now mirrors the already-typed `IndexReader` base contract:
  the accessors, term/doc iteration, length and postings/vector accessors,
  and the column API. `mypy` on `reading.py` stays clean and the
  reader/search/column/vector suites pass.
- Completed type hints for the `IndexReader` abstract base class, closing the
  base-class scope of #97. Every method on the class now carries parameter and
  return types, including the accessors (`codec`/`segment`/`segments`/`storage`,
  `is_atomic`, `close`, `generation`), term/doc iteration
  (`__iter__`/`iter_from`/`iter_prefix`, `field_terms`, `all_doc_ids`/`iter_docs`),
  length accessors (`field_length`/`min_field_length`/`max_field_length`/
  `doc_field_length`), postings/vectors (`iter_postings`, `vector`, `vector_as`),
  spelling/analysis helpers (`corrector`, `most_frequent_terms`,
  `most_distinctive_terms`), and the composite/column API (`leaf_readers`,
  `supports_caches`, `has_column`, `column_reader`). `mypy` on `reading.py`
  introduces no new errors and the reader/search/vector/spelling/column test
  suites pass.
- Type hints for the wrapping/facet/filter collectors in `whoosh.collectors`
  (second pass on #101, following the core scoring path in #92): annotated
  `SortingCollector`, `UnsortedCollector`, `WrappingCollector`,
  `FilterCollector`, `FacetCollector`, `CollapseCollector`,
  `TimeLimitCollector` and `TermsCollector`. The dynamic attributes that these
  collectors attach to `Results` (`filtered_count`, `allowed`, `restricted`,
  `collapsed_counts`, `termdocs`, `docterms`) are now declared on the `Results`
  class so they are part of the documented, type-checked surface. `mypy` on
  `collectors.py` is now fully clean (0 errors).

### Fixed
- `SegmentReader.has_column()` returned the field's `Column` object (or `None`)
  rather than a strict `bool`, contradicting its declared `-> bool` contract on
  the `IndexReader` base class. Callers only used it for truthiness so behaviour
  was unchanged, but the method now returns a real `bool`. Surfaced by typing
  the concrete reader against the base contract.
- `CollapseCollector.all_ids()` iterated `child.subsearchers()`, but a
  `Collector` has no `subsearchers()` method (`subsearchers` is an attribute of
  a `Searcher`), so calling `all_ids()` on a collapse collector raised
  `AttributeError`. It now iterates `self.top_searcher.leaf_searchers()`, the
  same idiom used by `Collector.run()` and the other collectors.
- `IndexReader.doc_count()` (the abstract base implementation) referenced a
  non-existent `self.deleted_count()` method, so any third-party `IndexReader`
  subclass that inherited the base `doc_count` instead of overriding it would
  raise `AttributeError` rather than a clear `NotImplementedError`. The base
  method now `raises NotImplementedError`, consistent with its sibling abstract
  methods (`doc_count_all`, `frequency`, …). All built-in readers
  (`SegmentReader`, `MultiReader`, `EmptyReader`) already override `doc_count`,
  so runtime behaviour is unchanged; this only fixes the abstract contract for
  downstream subclasses. Also removed a dead `cached_property` import-fallback
  (the `< 3.8` branch can never run on Whoosh's 3.9+ floor and pulled in a
  third-party package that isn't a dependency). Both changes clear the last two
  `mypy` errors on `reading.py`, so the whole module now type-checks clean.
- Documentation: corrected two broken Pages links in `ROADMAP.md` (the MCP
  Docker image and the LlamaIndex retriever landing page) that pointed to 404
  URLs.

## [3.42.0] - 2026-08-21

### Added
- Type hints for `IndexReader.__enter__`/`__exit__` context-manager methods (partial progress on #97). Thanks to @Muhammad08-dot for their first contribution! (#98)

### Performance
- `whoosh3` codec: raised the small-block compression-skip threshold to a
  measured 80-byte crossover (`COMPRESSION_MIN_SIZE`), so single-posting blocks
  of rare terms are stored uncompressed instead of being expanded by zlib's
  header overhead. Reduces build time and slightly shrinks on-disk indexes on
  Zipfian corpora; the per-block compression flag is stored in the block
  header and honoured on read, so the change is format-compatible. Thanks to
  [@tltaylor1](https://github.com/tltaylor1) for the measured analysis and
  tests (#100, closes #99).

### Fixed
- `whoosh3` codec: corrected a dead-store in `_write_block` where the
  small-block compression skip was immediately overwritten and never took
  effect. Behaviourally a no-op at the current threshold (guaranteed no index
  size or format change), but the code now matches its documented intent and
  clears the ground for a follow-up tiny-block compression optimization.

## [3.41.0] - 2026-08-20

### Added

- Type hints for the `whoosh.columns` base classes (`Column`, `ColumnWriter`,
  and `ColumnReader`) — the abstract interface every column store implements,
  so editors and mypy surface accurate signatures when writing or subclassing a
  column type. Contributed by
  [@DebayanSen96](https://github.com/DebayanSen96) (gh#96, closes gh#95).
- Type hints for `whoosh.fields` — the field-type hierarchy (`FieldType`,
  `TEXT`, `ID`, `KEYWORD`, `NUMERIC`, `DATETIME`, `BOOLEAN`, `Schema`, …) that
  users touch most when defining a schema, so editors and mypy now surface
  accurate signatures. Contributed by
  [@TheGittyPerson](https://github.com/TheGittyPerson) (gh#94, closes gh#93).
- Type hints for `whoosh.externalsort` (`SortingPool` and the module-level
  `sort()` helper), continuing the incremental typing effort toward a fully
  type-checked public API. Contributed by
  [@ShlokShar](https://github.com/ShlokShar) (gh#91, closes gh#90).

## [3.40.0] - 2026-08-10

### Fixed

- Three latent bugs in `whoosh.formats` `combine()` — the segment-merge path
  that folds the posting values for a term from several segments into one
  during `optimize()`/`writer.commit()`:
  - `Frequency.combine` called a non-existent `decode_value` instead of
    `decode_frequency`, so merging a frequency-format field across segments
    raised `AttributeError`.
  - `Characters.combine` and `CharacterBoosts.combine` transposed the
    per-position lookup (`pos[s]` instead of `s[pos]`), raising `TypeError`
    when the same token position appeared in more than one segment being
    merged.
  These were surfaced by type-checking while annotating the module and are now
  covered by round-trip regression tests (`tests/test_formats_combine.py`) that
  pin `combine()` behaviour for `Existence`, `Frequency`, `Positions`,
  `PositionBoosts`, `Characters`, and `CharacterBoosts`. Fix contributed by
  [@AdvaitVarhade](https://github.com/AdvaitVarhade) (gh#89, closes gh#88).

### Added

- Full type annotations for `whoosh.formats` — the `Format` class hierarchy
  (`Existence`, `Frequency`, `Positions`, `PositionBoosts`, `Characters`,
  `CharacterBoosts`) is now typed end-to-end, so editors and `mypy`/`pyright`
  get accurate signatures for the posting encode/decode/`combine` API. The
  module is clean under both `mypy` and `ruff`. Contributed by
  [@AdvaitVarhade](https://github.com/AdvaitVarhade) (gh#89).
- A new ["Improving recall"](https://priya-sundaram-dev.github.io/whoosh/docs/recall.html)
  guide covering stemming, `Variations`, fuzzy terms, did-you-mean spelling
  correction, and pseudo-relevance feedback for when searches return too few
  results.

## [3.39.0] - 2026-08-09

### Changed

- Faster index writing: `FieldWriter.add_postings` no longer rebuilds the
  internal length-field name and re-resolves the length column reader on every
  posting. It now binds a per-field length accessor once when the field
  changes (via the new `PerDocumentReader.doc_field_length_reader`, with a fast
  override in the default `whoosh3` codec) and calls it once per posting. This
  hoists ~600k redundant string builds and reader look-ups out of the hot loop
  in a 5,000-doc build, trimming a few percent off wall-clock index build time
  with byte-identical output and no on-disk format change. Third-party length
  providers that only implement `doc_field_length` keep working unchanged via a
  transparent fallback. This is the first, format-safe step of the profiled
  indexing-throughput work tracked in the roadmap.

### Added

- Full type annotations for `whoosh.analysis.intraword` — the sub-word
  analysis filters (`CompoundWordFilter`, `BiWordFilter`, `ShingleFilter`,
  `IntraWordFilter`) are now typed end-to-end, so editors and `mypy`/`pyright`
  get accurate signatures for the CamelCase/`Wi-Fi`/`SD500` splitting and
  pseudo-phrase shingling used in custom analyzer chains. `Token`'s optional
  positional attributes (`pos`, `startchar`, `endchar`) are now declared on
  the class so consumers that guard access behind `token.positions` /
  `token.chars` type-check cleanly. The module is clean under both `mypy` and
  `ruff`, and the four filters are exercised in `tests/typing_smoke.py` so the
  public typing stays CI-guarded (closes gh#82; completes the
  `whoosh.analysis` typing sweep tracked in gh#121).

## [3.38.0] - 2026-08-09

### Added

- Full type annotations for `whoosh.idsets` — the public doc-id set API
  (`DocIdSet`, `BitSet`, `OnDiskBitSet`, `SortedIntSet`, `ReverseIdSet`,
  `RoaringIdSet`, `MultiIdSet`) is now typed end-to-end, so editors and
  `mypy`/`pyright` get accurate signatures for indexes, iteration and set
  algebra. A new `IntSetLike` alias documents the "another set of ints"
  parameter accepted by the combining/comparison methods. The module is
  clean under both `mypy` and `ruff` (closes gh#86; part of the incremental
  typing effort tracked in gh#121).

### Fixed

- `RoaringIdSet` was unusable for any id at or above 65536: `_find()` computed
  the per-bucket range floor as `n << 16` instead of `bucket << 16`, so adding
  such an id produced a negative in-bucket offset and raised `OverflowError`.
  Its `__iter__` also tried to unpack `self.idsets` (a flat list) as
  `(index, set)` pairs and raised `TypeError`. Both are fixed and covered by a
  new regression test, so `RoaringIdSet` now stores and iterates large id sets
  correctly.
- `OnDiskBitSet.__repr__` referenced non-existent attributes (`self.dbfile`,
  `self.bytecount`) and raised `AttributeError` when repr'd; it now uses the
  real `_dbfile`/`_bytecount` fields.

## [3.37.0] - 2026-08-09

### Fixed

- `StemFilter.cache_info()` no longer raises `TypeError` when the filter was
  created with caching disabled (`cachesize=None`); it now returns `None` in
  that case, matching the documented "no stats available" behaviour.

### Changed

- `StemFilter` (and therefore `StemmingAnalyzer` and `LanguageAnalyzer`) now
  backs its bounded stem cache with the C-accelerated
  `functools.lru_cache` instead of the old hand-rolled pure-Python LFU cache.
  The stem function is pure, so the eviction policy has no effect on results —
  only on which entries survive when the cache fills — but the hot cache-hit
  path is several times faster (~4x on a repeated-token stream in a local
  micro-benchmark), which is where stemming spends most of its time. This
  speeds up indexing and query-time analysis for any schema using a stemming
  analyzer, with no API change. `StemFilter.cache_info()` keeps working and
  now returns the standard `functools` `CacheInfo` named tuple
  (`hits, misses, maxsize, currsize`).

## [3.36.0] - 2026-08-08

### Added

- Cookbook recipe and runnable example (`examples/acronyms.py`) on searching
  for acronyms and tech tokens such as `R&D`, `AT&T`, `Q&A`, `C++`, `C#`, `F#`
  and `.NET`. The stock analyzers tokenize on `&`/`+`/`#`/`.` boundaries, so
  `R&D` splits into `R` and `D` and — because `StandardAnalyzer` also drops
  single characters — the acronym disappears entirely, and a search for it
  returns nothing even though the text is present. The recipe ships a targeted
  `TechAnalyzer` (a `RegexTokenizer` whose pattern tries the tech shapes
  most-specific-first, then falls through to the normal word pattern) that
  keeps those tokens whole while leaving ordinary hyphenation like
  `well-known`/`e-mail` unchanged. Covered by `tests/test_example_acronyms.py`,
  including an end-to-end index+search check that `R&D`, `C++`, `C#` and `.NET`
  all match. Addresses a recurring downstream papercut (e.g. dullage/flatnotes#276).

## [3.35.0] - 2026-08-08

### Added

- First-class LlamaIndex integration, shipped as `whoosh.llamaindex` and
  installed with `pip install "whoosh3[llamaindex]"`. Mirrors the LangChain
  adapter: use Whoosh as a lexical (BM25) retriever to complement dense/vector
  retrieval, which can quietly miss the exact literal tokens that matter most
  (SKUs, error codes, gene symbols, ticket IDs). The dependency-free
  `WhooshSearch` core is now shared across framework adapters in a new
  `whoosh.retrieval` module (Whoosh + stdlib only, fully unit-tested), and a
  thin `make_whoosh_llamaindex_retriever()` factory lazily builds a
  `llama_index.core.retrievers.BaseRetriever` — so importing `whoosh.llamaindex`
  never requires `llama-index-core`. Drop it into a `QueryFusionRetriever` for
  hybrid (lexical + vector) search. Covered by `tests/test_llamaindex.py` and a
  runnable `examples/llamaindex_retriever.py`. `whoosh.langchain` re-exports the
  shared core, so `from whoosh.langchain import WhooshSearch, Hit` keeps working.
- Cookbook recipe and runnable example (`examples/signed_numbers.py`) on
  indexing signed numbers. The stock word tokenizer treats `-`/`+` as
  boundaries, so a leading sign is silently dropped from numeric text and
  `-100`/`100` collapse to one term. The recipe documents two sign-preserving
  approaches — a `NUMERIC(signed=True)` field (which also enables range
  queries) and a targeted tokenizer that keeps signed numbers while leaving
  hyphenated words intact — and explains why widening the whole word pattern
  regresses ordinary hyphenation. Covered by `tests/test_example_signed_numbers.py`.

## [3.34.0] - 2026-08-08

### Added

- First-class LangChain integration, shipped as `whoosh.langchain` and installed
  with `pip install "whoosh3[langchain]"`. Use Whoosh as a lexical (BM25)
  retriever to complement dense/vector retrieval — dense search can quietly miss
  the exact literal tokens that matter most (SKUs, error codes, gene symbols,
  ticket IDs). All search logic lives in a dependency-free `WhooshSearch` core
  (Whoosh + stdlib only, with `from_texts()` / `open_dir()` constructors), and a
  thin `make_whoosh_retriever()` factory builds a `langchain_core.BaseRetriever`
  lazily — so importing `whoosh.langchain` never requires `langchain-core`, and
  the retriever drops into any chain, `EnsembleRetriever` (hybrid search), or
  LangGraph agent. Covered by `tests/test_langchain.py` (the adapter test skips
  cleanly when `langchain-core` is absent). Documented in the cookbook, with a
  runnable demo in `examples/langchain_retriever.py`.

## [3.33.1] - 2026-08-04

### Fixed

- `whoosh-mcp` now fails gracefully when the optional `mcp` SDK is not
  installed: it prints a single actionable line
  (`whoosh-mcp: The MCP server requires the 'mcp' package. Install it with:
  pip install "whoosh3[mcp]"`) and exits `1`, instead of dumping a chained
  Python traceback. First impressions matter for the MCP audience trying the
  server for the first time.

## [3.33.0] - 2026-08-04

### Added

- Type hints for the `whoosh.analysis.analyzers` public API — `Analyzer`,
  `CompositeAnalyzer` and the analyzer factory functions (e.g. `StandardAnalyzer`,
  `StemmingAnalyzer`, `KeywordAnalyzer`, `FancyAnalyzer`, `LanguageAnalyzer`) now
  carry [PEP 484](https://peps.python.org/pep-0484/) annotations, so editors and
  `mypy` can type-check analyzer construction end to end. `StandardAnalyzer` is
  now exercised in the typing smoke test. Typing-only; no runtime behaviour
  change. Thanks to [@Kiet-B](https://github.com/Kiet-B) for the contribution
  ([#87](https://github.com/priya-sundaram-dev/whoosh/pull/87), fixes
  [#85](https://github.com/priya-sundaram-dev/whoosh/issues/85)).
- **Migration guide on the docs site.** The "Migrating to whoosh3" guide is now
  a first-class page in the rendered documentation (previously only `MIGRATING.md`
  at the repo root), so it is linked from the docs navigation and indexed by
  search engines for users moving from `Whoosh` / `whoosh-reloaded`.
- **Docker image for the MCP server.** A `Dockerfile` (plus `.dockerignore`) is
  now shipped so `whoosh-mcp` can be built and run without a local Python
  environment: `docker build -t whoosh-mcp .` then
  `docker run --rm -i -v "$HOME/notes:/corpus:ro" whoosh-mcp /corpus`. The image
  serves the built-in sample corpus with no argument, so it is introspectable out
  of the box (useful for MCP registries and directories). The MCP guide documents
  the container workflow alongside the pip install.
- A `glama.json` manifest declaring the project maintainer, so the whoosh-mcp
  server can be indexed and attributed in the Glama MCP directory.

## [3.32.0] - 2026-07-31

### Added

- Type hints for the `whoosh.analysis.morph` public API — `StemFilter.__call__`
  and `DoubleMetaphoneFilter.__call__` now carry [PEP 484](https://peps.python.org/pep-0484/)
  annotations (`tokens: Iterator[Token]` in, `Iterator[Token]` out); this also
  covers `PyStemmerFilter`, which subclasses `StemFilter`. `Token` is kept under
  `TYPE_CHECKING` to avoid an import cycle. Thanks to @mani787060 for their
  second contribution. (gh#77)
- **MCP server, now first-class and installable.** The
  [Model Context Protocol](https://modelcontextprotocol.io/) integration graduates
  from an example to a supported module, `whoosh.mcp`, plus a `whoosh-mcp` console
  script and a `whoosh3[mcp]` optional dependency. Serve a folder of your own docs
  to an AI agent as `search` and `fetch` tools with `pip install "whoosh3[mcp]"`
  and `whoosh-mcp ~/notes` — pure Python, no server, no native deps. The
  `SearchCore` class (`whoosh.mcp.SearchCore`) has no MCP dependency, so it is
  reusable behind any agent framework (LangChain/LlamaIndex tools, function
  calling) and importable/unit-testable on its own; `SearchCore.from_directory()`
  or the `WHOOSH_MCP_CORPUS` environment variable index a directory of
  `.md`/`.txt`/`.rst` files (one document per file), else built-in samples are
  used. `build_mcp_server()` raises a clear "install whoosh3[mcp]" error when the
  SDK is absent. `examples/mcp_server.py` is retained as a thin, runnable wrapper.
  Covered by a new `tests/test_mcp.py` suite. Companion guide at
  `whoosh-mcp-server-agent-search-tool.html`.

## [3.31.0] - 2026-07-31

### Added

- Type hints for the `whoosh.analysis.tokenizers` public API — the
  `IDTokenizer`, `RegexTokenizer`, and `NormalizingRegexTokenizer`
  `__call__`/`__init__` signatures now carry [PEP 484](https://peps.python.org/pep-0484/)
  annotations (`value: str`, boolean/int options, `Iterator[Token]` returns),
  with `CompositeAnalyzer` kept under `TYPE_CHECKING` to avoid an import cycle.
  Thanks to @mani787060 for their first contribution. (gh#72)
- Type hints for the `whoosh.analysis.filters` public API — the `Filter`
  subclasses (`LowercaseFilter`, `StripFilter`, `ReverseTextFilter`,
  `StopFilter`, `SubstitutionFilter`, `DelimitedAttributeFilter`,
  `CharsetFilter`, `PassFilter`, `TeeFilter`, `MultiFilter`, `LoggingFilter`)
  now carry [PEP 484](https://peps.python.org/pep-0484/) annotations on their
  `__init__` and `__call__` signatures (`Iterable[Token]` inputs,
  `Iterator[Token]` returns). `logging`, `re`, and
  `CompositeAnalyzer` stay behind `TYPE_CHECKING` to avoid any import-time
  cost. (gh#76)
- Type hints for the `whoosh.analysis.acore` public API — `Token` now declares
  its common public attributes (`text: str`, `positions`/`chars`/`stopped`/
  `removestops: bool`, `boost: float`, `mode: str`) while keeping its dynamic
  attributes intact, and `Composable.__or__` is annotated to return a
  `CompositeAnalyzer` (kept under `TYPE_CHECKING` to avoid an import cycle).
  Thanks to @tomatotomata for their first contribution. (gh#80)

## [3.30.0] - 2026-07-29

### Added

- Type hints for the `whoosh.query.Query` base-class public API — the generic
  query surface every query type inherits and that tree-transformation and
  introspection code calls polymorphically. The boolean predicates
  (`is_leaf()` / `is_range()` / `has_terms()` / `needs_spans()` → `bool`), the
  tree walkers (`children()` / `leaves()` → `Iterator[Query]`), term
  introspection (`iter_all_terms()` / `terms()` / `expanded_terms()` →
  `Iterator[tuple[str, str]]`, `all_terms()` → `set[tuple[str, str]]`,
  `existing_terms()` → `set[tuple[str, bytes]]`), the transforms
  (`apply()` / `accept()` accept a `Callable[[Query], Query]`;
  `with_boost()` / `copy()` / `replace()` / `normalize()` / `simplify()` →
  `Query`), the estimators (`estimate_size()` / `estimate_min_size()` → `int`),
  `field()` → `str | None`, `requires()` → `set[Query]`, `docs()` /
  `deletion_docs()` → `Iterator[int]`, `matcher()` → `Matcher`, and
  `all_tokens()` / `tokens()` → `Iterator[Token]` now carry
  [PEP 484](https://peps.python.org/pep-0484/) annotations. Heavy imports
  (`Matcher`, `IndexReader`, `Searcher`, `Token`) stay behind `TYPE_CHECKING`,
  so there is no import-time cost. (gh#69)
- Type hints for the `whoosh.analysis.ngrams` public API — `NgramTokenizer`
  and `NgramFilter` (both `__call__`s are generators, annotated
  `Iterator[Token]`; constructors take `int` sizes and an optional `at`
  string), and the `NgramAnalyzer` / `NgramWordAnalyzer` factories
  (`→ CompositeAnalyzer`). `CompositeAnalyzer` stays under `TYPE_CHECKING`
  because `analysis.analyzers` imports back into this module. Thanks to
  @Rfannn for their first contribution. (gh#71)

## [3.29.0] - 2026-07-28

### Added

- Type hints for the public read API in `whoosh.reading` — the `IndexReader`
  surface every search touches. The term-enumeration methods
  (`indexed_field_names()` → `Iterable[str]`, `all_terms()` →
  `Iterable[tuple[str, bytes]]`, `lexicon()` / `expand_prefix()` → bytestrings,
  `iter_field()` → `(bytes, TermInfo)` pairs), the per-term statistics
  (`term_info()` → `TermInfo`, `frequency()` / `doc_frequency()` → `int`,
  `first_id()` → `int`, `postings()` → `Matcher`), the document counts and
  flags (`doc_count()` / `doc_count_all()` → `int`, `has_deletions()` /
  `is_deleted()` / `has_vector()` → `bool`), the stored-field accessors
  (`stored_fields()` → `dict[str, Any]`, `all_stored_fields()`), and
  `terms_within()` now carry [PEP 484](https://peps.python.org/pep-0484/)
  annotations, along with the `TermInfo` statistics object
  (`doc_frequency()` / `max_id()` → `int`, `weight()` / `max_weight()` →
  `float`, min/max length accessors). Heavy imports (`Matcher`, `Schema`) stay
  under `TYPE_CHECKING` and the module gains
  `from __future__ import annotations`, so there is no import-time cost. The
  reader entry points are now exercised by the `tests/typing_smoke.py` mypy
  fixture. Annotations only — no runtime behaviour changes. (#64)
- Type hints for the public write API in `whoosh.writing` — the `IndexWriter`
  surface almost every Whoosh program calls. The schema-mutation helpers
  (`add_field(name, FieldType)` / `remove_field(name)` → `None`), the deletion
  helpers (`delete_by_term()` / `delete_by_query()` → `int` count of documents
  removed, `delete_document(docnum)`), and the grouping helpers
  (`group()` → context manager, `start_group()` / `end_group()`) now carry
  [PEP 484](https://peps.python.org/pep-0484/) annotations, alongside the
  already-typed `add_document` / `update_document` / `commit` / `cancel`. Heavy
  imports (`Query`, `FieldType`, `IndexReader`, `Searcher`) stay under
  `TYPE_CHECKING` and the module gains `from __future__ import annotations`, so
  there is no import-time cost. The writer entry points are now exercised by the
  `tests/typing_smoke.py` mypy fixture. Annotations only — no runtime behaviour
  changes. (#62)
- Type hints for the public API of `whoosh.spelling` — the spell-correction /
  "did you mean" surface. `Corrector.suggest()` (and the `_suggestions()` hook
  subclasses override), `ReaderCorrector` / `ListCorrector` / `MultiCorrector`,
  the `Correction` result object (`format_string()` → `str`), and
  `QueryCorrector` / `SimpleQueryCorrector.correct_query()` → `Correction` now
  carry [PEP 484](https://peps.python.org/pep-0484/) annotations, so downstream
  users get real signatures from the shipped `py.typed` marker in their editors
  and `mypy`/`pyright` runs. Heavy imports stay under `TYPE_CHECKING` and the
  module gains `from __future__ import annotations`, so there is no import-time
  cost. The spelling entry points are now exercised by the
  `tests/typing_smoke.py` mypy fixture. Annotations only — no runtime behaviour
  changes. (#61)

## [3.28.0] - 2026-07-27

### Added

- **CJK (Chinese / Japanese / Korean) text support** via a new `CJKFilter` and
  `CJKAnalyzer` in `whoosh.analysis`. CJK scripts don't put spaces between
  words, so the default `RegexTokenizer` (which splits on `\w+` runs) indexes a
  whole CJK phrase as a _single_ token — meaning a search only matches if the
  query happens to equal the entire run. `CJKFilter` splits any run of CJK
  characters into individual single-character tokens (unigram indexing, the
  same strategy Lucene's CJK analyzer uses) while leaving Latin/other text
  untouched, so both single-character terms and quoted phrases match. Because it
  only touches CJK characters, it composes onto existing analyzers
  (`StemmingAnalyzer() | CJKFilter()`) without changing behaviour for other
  languages. `CJKAnalyzer` bundles a tokenizer + lowercase + `minsize=1` stop
  filter + `CJKFilter` for the common case. Positions are renumbered so adjacent
  CJK characters occupy consecutive positions (phrase queries rely on this), and
  character offsets are preserved for highlighting. Covers Han ideographs
  (incl. Extensions A–F), Hiragana/Katakana (incl. halfwidth), and Hangul.
  Four regression tests in `tests/test_analysis.py` cover tokenization,
  positions/offsets, and an end-to-end index-and-search including phrase and
  no-false-positive cases.

## [3.27.0] - 2026-07-27

### Added

- Type hints for the public API of `whoosh.classify` — the query-expansion
  models `ExpansionModel`, `Bo1Model`, `Bo2Model`, `KLModel`, and the `Expander`
  class used for automatic query expansion / relevance feedback. Constructor and
  method signatures (weights and lengths as `float`, `doc_count` as `int`,
  `expanded_terms` → `list[tuple[str, float]]`) now surface in editors and
  `mypy`/`pyright` via the shipped `py.typed` marker, and the flow is exercised
  in `tests/typing_smoke.py`. Annotations only — no runtime behaviour changes.
  Thanks to **@AshSgDe29071999** for the first external contribution to the
  revived project ([#60](https://github.com/priya-sundaram-dev/whoosh/pull/60),
  closes [#59](https://github.com/priya-sundaram-dev/whoosh/issues/59)).
- New example `examples/rag_retriever.py`: using Whoosh as a BM25 retriever for
  RAG, with a runnable **hybrid search** pattern (Whoosh BM25 + any vector store,
  fused via Reciprocal Rank Fusion). It demonstrates the complementary failure
  modes hybrid search fixes — dense retrieval bridging synonyms while BM25 nails
  rare literal tokens like error codes — and assembles the fused top-k chunks
  into an LLM context window. Runs with only Whoosh and the standard library
  (the dense retriever is a dependency-free stand-in you swap for
  FAISS/Chroma/pgvector). Covered by `tests/test_example_rag_retriever.py` so
  the "Whoosh for RAG" guide always has working code behind it.

## [3.26.0] - 2026-07-26

This release completes the type annotations for the whole `whoosh.query`
package. Combined with the already-typed term and field-type APIs and the
shipped `py.typed` marker, the query classes programs build directly — boolean
combinators, wrappers, ranges, and phrase/positional queries — now surface
their signatures in editors and `mypy`/`pyright`. These are annotation-only
changes: runtime behaviour and docstrings are unchanged.

### Added

- Type hints for the public API of `whoosh.query.compound` — the boolean
  combinator query classes `CompoundQuery`, `And`, `Or`, `DisjunctionMax`,
  `BinaryQuery`, and `AndNot`. These are the queries most programs build
  directly (or via the `&`/`|` operators), so annotations here flow into
  editors and `mypy`/`pyright` through the shipped `py.typed` marker:
  constructor arguments (`subqueries` as a `Sequence[Query]`, `boost`, and the
  class-specific `minmatch`/`scale`/`tiebreak` kwargs), the binary-query
  `a`/`b` operands, and the container dunders (`__len__` → `int`, `__iter__`
  → `Iterator[Query]`, `__getitem__` → `Query`, plus `str`/`eq`/`hash`).
  Annotations only — runtime behaviour and docstrings are unchanged, and the
  `whoosh.query.compound` combinators are now exercised by the
  `tests/typing_smoke.py` mypy fixture. (#52)
- Type hints for the public API of `whoosh.query.wrappers` — the query
  classes that wrap another query: `WrappingQuery`, `Not`,
  `ConstantScoreQuery`, and `WeightingQuery`. `Not` is a staple of everyday
  boolean queries (and the `-` operator), so its annotations flow into editors
  and `mypy`/`pyright` through the shipped `py.typed` marker: constructor
  arguments (the wrapped `child`/`query` as a `Query`, plus `float`
  `boost`/`score`), `children()` → `Iterator[Query]`, `apply()` → the wrapping
  query type, and the `str`/`repr`/`eq`/`hash`/`is_leaf` dunders. Annotations
  only — runtime behaviour and docstrings are unchanged, and `Not`/
  `ConstantScoreQuery` are now exercised by the `tests/typing_smoke.py` mypy
  fixture. (#53)
- Type hints for the public API of `whoosh.query.ranges` — the range query
  classes `TermRange`, `NumericRange`, and `DateRange` (plus the shared
  `RangeMixin`). These flow into editors and `mypy`/`pyright` through the
  shipped `py.typed` marker: constructor arguments (`fieldname`, the
  field-appropriate `start`/`end` bounds — `str` for `TermRange`, a number for
  `NumericRange`, a `datetime` for `DateRange` — plus the `startexcl`/`endexcl`
  flags, `boost`, and `constantscore`), the `is_range`/`overlaps` predicates,
  `merge()` → `Query`, and the `repr`/`str`/`eq`/`hash` dunders. Annotations
  only — runtime behaviour and docstrings are unchanged, and all three range
  classes are now exercised by the `tests/typing_smoke.py` mypy fixture. (#55)
- Type hints for the public API of `whoosh.query.positional` — the
  position-aware query classes `Phrase`, `Sequence`, and `Ordered`. `Phrase`
  is what quoted searches parse into, so its annotations flow into editors and
  `mypy`/`pyright` through the shipped `py.typed` marker: constructor arguments
  (`fieldname`, `words` as a `list[str]`, the wrapped `subqueries`, `slop`,
  `ordered`, `boost`, and `char_ranges`), `has_terms()` → `bool`,
  `terms()`/`tokens()` → their annotated iterators, `replace()` → `Phrase`, and
  the `repr`/`str`/`eq`/`hash` dunders. Annotations only — runtime behaviour and
  docstrings are unchanged, and `Phrase`/`Sequence`/`Ordered` are now exercised
  by the `tests/typing_smoke.py` mypy fixture. (#56)

## [3.25.3] - 2026-07-24

### Added

- New `examples/django_app.py`: a runnable Django full-text search app,
  completing the FastAPI/Flask/Django trio that all expose the same
  upsert/delete/search JSON API. Django's built-in full-text search only works
  on PostgreSQL; this shows portable, relevance-ranked search (BM25F, with
  highlighted snippets) on any database — or none — with a no-compile
  `pip install`. It is a single-file Django project (settings, URLs, and views
  inline) so it runs without a `startproject` layout, the Whoosh logic lives in
  the same framework-free `SearchIndex` class as the other examples (with a
  `python django_app.py` self-test), and the docstring documents the
  `post_save`/`post_delete` signal wiring for keeping the index in sync with
  the ORM. (#54)
- Type hints for the public API of `whoosh.query.terms` — the term-level query
  classes `Term`, `MultiTerm`, `PatternQuery`, `Prefix`, `Wildcard`, `Regex`,
  `ExpandingTerm`, `FuzzyTerm`, and `Variations`. These are the query objects
  most programs construct directly, so annotations here reach editors and
  `mypy`/`pyright` via the shipped `py.typed` marker: constructor keyword
  arguments (`fieldname`, `text`, `boost`, `maxdist`, `prefixlength`,
  `constantscore`), the `str`/`repr`/`hash` dunders, `matcher()` (returns a
  `Matcher`), `normalize()`/`replace()`/`simplify()` (return a `Query`), and the
  term-iteration helpers. Annotations only — docstrings and runtime behaviour
  are unchanged (verified by an AST docstring diff), and a `whoosh.query.terms`
  snippet was added to the `tests/typing_smoke.py` CI type-check fixture. (#51)

## [3.25.2] - 2026-07-23

### Added

- Type hints for the public API of `whoosh.highlight` — `Fragmenter` and its
  subclasses (`WholeFragmenter`, `SentenceFragmenter`, `ContextFragmenter`,
  `PinpointFragmenter`), `Formatter` and its subclasses (`NullFormatter`,
  `UppercaseFormatter`, `HtmlFormatter`, `GenshiFormatter`), `Fragment`,
  `Highlighter`, and the module-level `highlight`, `top_fragments`, and
  scoring/order helpers. Highlighting matched terms is one of the most common
  post-search operations, so annotations here reach editors and `mypy`/`pyright`
  via the shipped `py.typed` marker. Annotations only — docstrings and runtime
  behaviour are unchanged (verified by an AST docstring diff), and a highlight
  snippet was added to the `tests/typing_smoke.py` CI type-check fixture. (#49)
- New `examples/flask_app.py`: a runnable Flask full-text search app mirroring
  the FastAPI example — idempotent `PUT`/`DELETE` document endpoints and a
  `GET /search` endpoint with pagination, BM25F ranking, and highlighted
  snippets. The Whoosh logic lives in a framework-free `SearchIndex` class
  (with a `python flask_app.py` self-test), and the example demonstrates safe
  concurrency: writes serialised behind a lock, a fresh searcher per request.
  Documented in the cookbook and integrations guides. (#50)

## [3.25.1] - 2026-07-22

### Added

- Type hints for the public API of `whoosh.sorting` (`FacetType`,
  `Categorizer`, `Facets` and the built-in facet/map classes), so type
  checkers can follow faceting and sorting code. Docstrings are unchanged.
  Thanks to @cyber-chic-0. (#45)

### Changed

- **Type annotations for the scoring public API (gh#44).** `whoosh.scoring` now
  carries type hints across its public surface: `WeightingModel`, `BaseScorer`
  and its subclasses, the concrete weighting models and their scorers (`BM25F`,
  `DFree`, `PL2`, `TF_IDF`, `Frequency`, `Weighting`, `MultiWeighting`,
  `ReverseWeighting`, `FunctionWeighting`), and the module-level `bm25`/`dfree`/`pl2`
  helpers. Tuning constructors such as `BM25F(B=0.75, K1=1.2, **kwargs)` and
  `PL2(c=1.0)` are fully annotated. Hints use `from __future__ import annotations`
  (no runtime cost or behavior change); `searcher`/`matcher` parameters stay `Any`
  to avoid import cycles. Thanks to @VedantPatel04. (#48)

## [3.25.0] - 2026-07-22

### Added

- CLI: `whoosh search --min-score FLOAT` drops hits whose relevance score is
  below the given floor, trimming the weak tail of a broad query. It applies
  uniformly across the default text output, `--json`/`--jsonl`, `--count`, and
  `-l`/`--files-with-matches`, filters on score even under `--sort-by mtime`,
  and behaves like a no-match search (exit status `1`) when every hit is
  filtered out. (#22)

## [3.24.0] - 2026-07-21

### Added

- CLI: `whoosh search --color {auto,always,never}` colorizes matched terms in
  the default text output with ANSI escape codes instead of UPPERCASE. `auto`
  (the default) colorizes only when writing to a terminal and honors the
  `NO_COLOR`/`FORCE_COLOR` environment variables. Highlighting runs through the
  same `Formatter` pipeline as `--html`, so it emphasises the actual matched
  tokens, including stemmed matches. Adds a new `whoosh.colorize` module
  (`resolve_color_mode`, `highlight`, and an `AnsiFormatter` `Formatter`
  subclass). (#42, #43, thanks @tapheret2)

## [3.23.0] - 2026-07-21

### Added

- CLI: `whoosh search -l -0` (aliases `--files-with-matches --null`) emits
  NUL-terminated paths for safe use with tools such as `xargs -0`. Requires
  `-l`; errors with exit status `2` otherwise. (#41, thanks @jhtyhc666)

## [3.22.0] - 2026-07-21

### Added

- CLI: `whoosh index --follow-symlinks` follows symlinked directories when
  building the index (off by default for safety). Threaded through `iter_files`
  via `os.walk(..., followlinks=...)` and honored by both the real index pass
  and `--dry-run`. (#38, thanks @cyber-chic-0)

## [3.21.0] - 2026-07-21

### Added

- CLI: `whoosh search -l` / `--files-with-matches` prints just the matching
  file paths, one per line (grep `-l` style), with no scores, snippets, or
  numbering. It honors `--limit`/`--page`, is mutually exclusive with the other
  output modes, and exits with status `1` (empty output) when there are no
  matches — perfect for piping into `xargs`, `wc -l`, or your editor. (#37,
  thanks @cyber-chic-0)

## [3.20.0] - 2026-07-21

### Added

- CLI: `whoosh search --page N` pages through results using `--limit` as the
  page size, while keeping JSON, JSON Lines, and count output machine-friendly.
  Human-readable output prints page metadata after the first page; requesting a
  page beyond the last returns no matches with exit status `1`. (#35, thanks
  @jhtyhc666)

## [3.19.0] - 2026-07-21

### Added

- CLI: `whoosh search --jsonl` (alias `--ndjson`) emits one JSON object per
  match for line-oriented processing, using the same per-hit shape as the
  `--json` array. No matches produces no output and exits with status `1`,
  while `--json` continues to emit `[]`. Great for streaming results into
  `jq` and other line-oriented tools. (#32, thanks @jason-scheffel)

## [3.18.7] - 2026-07-20

### Fixed

- `NUMERIC.__setstate__` (and therefore `DATETIME`) now correctly recomputes and
  restores `min_value`/`max_value` when unpickling legacy indices (Whoosh 2.5.2
  and earlier) that were written without those cached bounds. The previous code
  assigned the recomputed bounds to a throwaway local state dict, leaving the
  reconstructed field without the attributes and raising `AttributeError` on
  later use. Fixes whoosh-community #359.

## [3.18.6] - 2026-07-20

### Fixed

- `AndMaybeMatcher.weight()` no longer raises `IndexError` when the optional
  (second) sub-matcher is exhausted while the required (first) sub-matcher is
  still producing documents. It now guards on `self.b.is_active()` exactly like
  `score()` already did, returning just the required matcher's weight in that
  case. This is the `weight()` counterpart of the long-standing
  `AndMaybe`/`quality` IndexError class of bugs (inherited
  whoosh-community#124); regression test added.

## [3.18.5] - 2026-07-20

### Added

- CLI: `whoosh index --max-size SIZE` skips files larger than `SIZE` before
  they're read (e.g. `10MB`, `500k`, `2048`). Accepts a bare integer (bytes)
  or a `k`/`m`/`g` suffix, case-insensitive, with or without a trailing `b`.
  No `--max-size` given -> unchanged behavior. `--dry-run` respects it too.
  (#30)

## [3.18.4] - 2026-07-19

### Added

- CLI: `whoosh search --or` matches documents containing **any** query term
  (broader recall) instead of requiring all terms. Uses `OrGroup.factory(0.9)`
  so documents matching more terms still rank higher. (#18)

## [3.18.3] - 2026-07-19

### Fixed

- `PinpointFragmenter` highlighted the wrong word (often the last token in the
  document, e.g. rendering `dog` for a `"quick brown"` query) whenever a search
  matched more than one term _and_ the field did not store character positions
  (so highlighting fell back to re-tokenizing the stored text). The
  non-retokenizing fragmenter collected matched tokens with a list
  comprehension over the analyzer's token stream, but the analyzer yields a
  single Token object that it mutates in place — so every collected reference
  pointed at the same, already-advanced token. It now snapshots each matched
  token with `Token.copy()`. Added a regression test.
- The legacy `whoosh2` backwards-compatibility codec (`whoosh.codec.whoosh2`)
  imported `NoGraphError` from `whoosh.reading`, but that name was removed from
  `reading.py` when the on-disk word graph was dropped — so
  `import whoosh.codec.whoosh2` raised `ImportError`. Because `whoosh.legacy`
  maps old pickled schema classes (`OLD_NUMERIC`, `OLD_DATETIME`,
  `int_to_text`, …) onto this module to read pre-3.0 indexes, the broken import
  silently prevented reading old-format indexes. `NoGraphError` is now defined
  in the codec module itself (its only user), so the legacy codec imports
  again. Added a regression test.

## [3.18.2] - 2026-07-19

### Fixed

- `whoosh.analysis.Filter.__ne__` was defined as `return self != other`, which
  called itself recursively — any `!=` comparison between two analysis filters
  (e.g. `LowercaseFilter() != PassFilter()`) raised `RecursionError`. It now
  correctly returns `not self == other`. Filter inequality is used when
  comparing analyzers, so this could surface in schema/field comparisons.
- `whoosh.analysis.TeeFilter.__eq__` compared `self.filters == other.filters`
  (misspelled attribute), so comparing two `TeeFilter` instances raised
  `AttributeError` instead of returning a boolean. It now compares
  `other.filters`.
- `whoosh.query.spans.Span.__ne__` only compared `start`/`end` while
  `__eq__` also compares `startchar`/`endchar`. Two spans differing only in
  their character offsets therefore reported both `a == b` and `a != b` as
  `False` — a contradiction that violates Python's data model and could make
  span de-duplication or set membership behave inconsistently. `__ne__` now
  delegates to `__eq__` so the two are always consistent.

## [3.18.1] - 2026-07-19

### Fixed

- `whoosh.qparser.RangeNode` (the query-syntax AST node for range queries) is
  now re-exported from the `whoosh.qparser` package namespace, so
  `from whoosh.qparser import RangeNode` works like the other syntax nodes
  (`WordNode`, `TextNode`, `MarkerNode`, …). It was defined in
  `whoosh.qparser.syntax` and documented in the API reference but had been
  omitted from the package's public imports, which also caused an autodoc
  import failure when building the docs.
- `whoosh.__version_str__` is now derived automatically from
  `whoosh.__version__` instead of being a separate hardcoded literal. The two
  had drifted (`__version__` said `3.18.1` while `__version_str__` still said
  the previous value), which fed the wrong version into the built package
  metadata. There is now a single source of truth for the version.

### Documentation

- Added an API reference page for the `whoosh.classify` module
  (`docs/source/api/classify.rst`), covering `Expander` and the
  `ExpansionModel` weighting models (`Bo1Model`, `Bo2Model`, `KLModel`). The
  keyword-extraction guide now cross-links to it.
- Added module-level docstrings to several core modules that were missing them
  (`whoosh.query`, `whoosh.qparser`, `whoosh.writing`, `whoosh.sorting`,
  `whoosh.multiproc`). These now appear as overviews at the top of their API
  reference pages (which use `automodule`) and in `help()`.

## [3.18.0] - 2026-07-19

### Added

- The multiprocessing writer (`whoosh.multiproc.MpWriter`, used via
  `ix.writer(procs=N)`) now accepts an explicit `start_method` argument (e.g.
  `ix.writer(procs=4, start_method="spawn")`). Passing `"spawn"` or
  `"forkserver"` builds the worker processes and queues from an explicit
  `multiprocessing` context, which avoids the `DeprecationWarning` CPython 3.12+
  emits when `fork()` is used from a multi-threaded parent, and is the
  forward-compatible choice as CPython moves away from fork-by-default. When
  `start_method` is unset the writer keeps its original behavior (the
  interpreter's default context), so this is fully backward compatible.
  Documented in the batch-indexing guide (`docs/source/batch.rst`).

### Documentation

- Updated the stale `whoosh.__version__` sample output in the app-integration
  guide (`docs/source/integrations.rst`) from `(3, 16, 1)` to match the current
  release, consistent with the same fix in the CLI guide.
- Fixed the "Creating custom operators" example in the query-parser guide
  (`docs/source/parsing.rst`): it referenced the nonexistent
  `qparser.OperatorPlugin` (singular) in the `OpTagger` snippets, which raised
  `AttributeError` when copy-pasted. The class is `qparser.OperatorsPlugin`.
- Updated the stale `whoosh --version` sample output in the CLI guide
  (`docs/source/cli.rst`) from `3.16.1` to match the current release.
- Corrected the default search limit in the searching guide
  (`docs/source/searching.rst`): the prose said `Searcher.search()` limits hits
  to 20 by default, but the actual default is 10 (matching the adjacent
  `scored_length()` example and the `Searcher.search` implementation).
- Fixed the query-parser output examples in the quick-start guide
  (`docs/source/quickstart.rst`): the snippets call `print(parser.parse(...))`,
  which prints the human-readable form of a query (e.g.
  `(content:render AND content:shade AND content:animate)`), but the documented
  output showed the `repr()` form (`And([Term(...), ...])`) instead. New users
  copy-pasting the examples saw output that did not match the docs. Corrected the
  three samples to the actual `print()` output and added a note explaining the
  difference between `print()`/`str()` and `repr()` for queries.

## [3.17.0] - 2026-07-18

### Added

- New built-in `NormalizingRegexTokenizer` (`whoosh.analysis`): a
  `RegexTokenizer` that Unicode-normalizes its input _before_ tokenizing. This
  fixes a subtle correctness bug where the same word indexed in one
  normalization form silently fails to match a query written in another — the
  default `RegexTokenizer` treats a combining accent as a non-word character, so
  the decomposed (NFD) spelling `cafe\u0301` tokenizes to `cafe` while the
  composed (NFC) `café` tokenizes to `café`. Because the normalization has to
  happen before the regex splits the string, a post-tokenizer filter is too
  late. The `form` argument accepts `"NFC"`, `"NFD"`, `"NFKC"` (default) or
  `"NFKD"`; NFKC also folds compatibility characters such as full-width Latin
  letters and ligatures. This promotes what was previously a documented recipe
  into batteries-included functionality.

### Documentation

- Rewrote the **Unicode normalization** section of the stemming/folding guide
  (`docs/source/stemming.rst`) to use the new built-in
  `NormalizingRegexTokenizer` instead of a copy-paste recipe, keeping the
  explanation of the NFC-vs-NFD pitfall (macOS filenames are NFD, most web input
  is NFC) and the guidance on choosing NFC/NFKC/NFD/NFKD.
- Documented the Windows file-locking path end-to-end in the concurrency guide
  (`docs/source/threads.rst`): the OS-level lock backends (`fcntl` vs.
  `msvcrt`), why a crash never leaves the index permanently locked, and the two
  Windows-specific gotchas that bite long-running downstreams like paperless-ngx
  and MoinMoin — mandatory (not advisory) locks that make `LockError` handling
  required, and open reader/searcher handles that block segment deletion during
  `commit()`/`optimize()` with `PermissionError` (WinError 32). Added guidance
  to use readers/searchers as context managers and to `refresh()` long-lived
  searchers rather than holding handles across a rebuild.

### Tests

- Added `test_unicode_normalization_tokenizer` and
  `test_normalizing_tokenizer_form_validation_and_equality` covering the new
  built-in `NormalizingRegexTokenizer`: NFC and NFD spellings of `café` tokenize
  identically, NFKC folds full-width Latin and ligatures, unknown forms raise
  `ValueError`, and equality is keyed on the normalization form (so caches don't
  confuse analyzers that differ only in form).
- Added `test_index_files_deletable_after_close` guarding the close-then-delete
  contract (readers, searchers, and writers release their file handles so index
  files can be removed/replaced). Nearly a no-op on POSIX; catches leaked
  handles on Windows before a release ships.

## [3.16.5] - 2026-07-18

### Fixed

- Strict phrase highlighting (`hit.highlights(..., strict_phrase=True)`) now
  works when the source text contains any uppercase letters. Previously the
  phrase scanner compared the analyzer-normalized (lower-cased, stemmed) phrase
  words against the _raw_ source text re-split on whitespace, so a document
  like `"... Java Developer ..."` never matched the query phrase `java
developer` and strict highlighting silently returned an empty string. The
  scanner now derives its word sequence from the analyzed tokens themselves, so
  casing and tokenization always line up. This also keeps the highlighted token
  indices correctly aligned with the source when punctuation or contractions
  would have thrown off a naive `str.split()`. Added regression tests covering
  the exact-phrase and slop branches with mixed-case input. Fixes the "exact
  matching does not work" confusion reported upstream at mchaput/whoosh#29,
  where a phrase search correctly matched only adjacent occurrences but the
  highlighter appeared to mark every stray occurrence of each word.

### Documentation

- Clarified the meaning of the `~N` phrase "slop" factor. The `Phrase`
  docstring previously described `slop` as "the number of words allowed
  between each word", which is off by one and contradicted its own claim that
  the default of 1 means an exact match. `slop` is actually the maximum
  allowed difference in _position_ between adjacent words (1 = adjacent), so a
  slop of `N` permits up to `N - 1` intervening words. Both the docstring and
  the query-language guide now state this precisely and note that words the
  analyzer removes (stop words, short tokens) are never indexed and so do not
  count toward the distance — the source of the "proximity search ignores
  filler words" confusion. Added regression tests pinning the slop-to-distance
  relationship. Addresses the confusion reported upstream at mchaput/whoosh#48.

## [3.16.4] - 2026-07-18

### Fixed

- Fields now reject a bare `Filter` passed where a full analyzer is expected
  (for example `TEXT(analyzer=CharsetFilter(accent_map))`). A `Filter` can only
  transform tokens produced by a tokenizer, so used alone it previously failed
  much later during indexing with a cryptic
  `TypeError: CharsetFilter.__call__() got an unexpected keyword argument
'mode'`. `TEXT` and `KEYWORD` now raise `FieldConfigurationError` at
  construction time with an actionable message
  (e.g. `RegexTokenizer() | CharsetFilter(...)`). Fixes gh#41 (reported
  upstream at mchaput/whoosh#41).

## [3.16.3] - 2026-07-18

### Fixed

- Multiprocessing writer: committing with `procs > 1` and `multisegment=False`
  no longer crashes a sub-writer with `IndexError: list index out of range`
  (in `finish_subsegment`, at `pool.runs[0]`) when a sub-writer received only
  documents that produce no indexed postings — for example documents made up
  entirely of `STORED` fields, or `TEXT` that tokenizes to nothing. Previously
  such a sub-writer died silently, risking lost documents; now its
  per-document (stored) data is merged correctly and all documents survive.
  Reported upstream as mchaput/whoosh#35.

## [3.16.2] - 2026-07-18

### Fixed

- `whoosh stats --top-terms FIELD` now prints a clear, actionable error when
  the named field cannot have text terms ranked — for example a `NUMERIC` or
  `DATETIME` field such as the built-in `mtime`. Previously it surfaced a
  leaked low-level decode message (`invalid literal for int() with base 10`).
  It now reports, e.g., `error: field 'mtime' (NUMERIC) does not store text
terms, so it has no top terms to list; try a TEXT field` and exits `2`.

### Documentation

- "Command-line search": corrected the documented `whoosh --version` and
  `whoosh --help` output, which still showed an old version string
  (`3.5.0`) and an outdated usage line. Added an example of the improved
  `--top-terms` error for non-text fields.

## [3.16.1] - 2026-07-17

### Fixed

- `ListCorrector` (and `MultiCorrector` built on top of it) failed to suggest
  a correction whose only close match was the **first** word in the sorted word
  list. The internal `Skipper` cursor unconditionally advanced past its current
  position before searching, so the very first lookup permanently skipped
  `wordlist[0]`. For example, `ListCorrector(["apple", ...]).suggest("aple")`
  returned `[]` instead of `["apple"]`. The cursor now uses the current
  position as an inclusive lower bound, and a brute-force equivalence test
  guards against future regressions.
- `Corrector.suggest()` no longer returns the word being checked as one of its
  own corrections, matching the documented behavior. Previously, checking a word
  that exists in the index or word list (e.g. `suggest("apple")` when `apple`
  is indexed) listed `apple` itself as a "did you mean" suggestion.

### Documentation

- "Correcting errors in user queries": fixed two examples that no longer matched
  the API. `MultiCorrector` requires an `op` argument to combine scores
  (e.g. `MultiCorrector([c1, c2], max)`), and a corrected query is formatted with
  the returned correction's `format_string(formatter)` method rather than a
  (nonexistent) `formatter=` keyword on `correct_query()`.

## [3.16.0] - 2026-07-17

### Added

- `whoosh index --dry-run`: preview which files _would_ be indexed under the
  current `--ext`/`--exclude` filters, then exit without creating, clearing, or
  writing the `.whoosh_index` directory. Prints one relative path per line to
  stdout (easy to pipe or `grep`) and a short summary count to stderr. The
  preview reuses the exact same file-walking generator as a real run, so the
  listed set matches what indexing would ingest. Thanks to @Nitjsefnie (gh#23).

## [3.15.0] - 2026-07-17

### Added

- `whoosh.reading.CorruptIndexError`: reading a damaged or truncated postings
  block now raises this clear, dedicated exception instead of a cryptic
  low-level pickle error (for example `UnpicklingError: invalid load key, 'x'`
  or `ValueError: unsupported pickle protocol`). The message names the affected
  file and offset and explains the most common cause — writing to the same
  index from multiple processes/threads without the shared write lock, or an
  interrupted commit — along with the fix (rebuild the index). This makes a
  previously baffling failure mode diagnosable. Behavior for valid indexes is
  unchanged, so this is backward compatible (gh#46).

## [3.14.1] - 2026-07-17

### Fixed

- `NestedParent` no longer silently drops results when the index contains a
  document that matches the child query but does not belong to any parent group
  (an "orphan" child — for example a matching document indexed before the first
  parent, or in a gap between groups). Previously, encountering such a child
  would cause `NestedParent.before()` to return `None`, which terminated the
  whole matcher and dropped every subsequent, legitimately-parented match. The
  matcher now skips orphan children and continues. The same guard was added to
  `NestedParent.deletion_docs()` (which had a latent `range(None, ...)` crash on
  the same input) (gh#31).

## [3.14.0] - 2026-07-17

### Added

- `Phrase(..., degrade=True)` and `PhrasePlugin(degrade=True)`: an opt-in way to
  make a phrase (quoted) query fall back to matching documents that contain
  _all_ of the words (an `AND` of the terms) when the searched field does not
  store term positions — for example `NGRAMWORDS` fields, which use a frequency
  format and cannot support true phrase matching. Previously such a query
  always raised `QueryError: field has no positions`, which surfaced as a hard
  crash for applications (notably django-haystack) that accept quoted user
  input against ngram fields. The default behavior is unchanged (strict phrase
  matching still raises), so this is fully backward compatible (gh#27,
  django-haystack#632).

### Changed

- The `QueryError` raised when running a phrase query against a field with no
  positions is now actionable: it explains that the field needs a
  position-storing format (or `phrase=True`) and points to the new
  `degrade=True` fallback (gh#27).

## [3.13.0] - 2026-07-17

### Added

- `AsyncWriter.wait(timeout=None)`: a public, race-free way to block until the
  background commit thread (if one was started) has finished and to re-raise
  any exception it hit. Previously, callers had to poke `AsyncWriter`
  internals — `if writer.running: writer.join()` followed by manually checking
  `writer.exception` — to find out whether an asynchronous commit actually
  landed, and getting that pattern wrong could silently drop buffered
  documents. `wait()` collapses that into a single call: it is a no-op when
  the commit was written synchronously, blocks otherwise, and raises on
  failure (or `RuntimeError` if an optional `timeout` elapses). The old
  `join()`/`exception` pattern still works unchanged (gh#14).

## [3.12.4] - 2026-07-17

### Fixed

- Multiprocessing writing (`index.writer(procs=N)` with `N > 1`) on a
  non-shared storage such as `RamStorage` no longer silently discards every
  document. The multiprocessing writer passes job files to sub-processes
  through a shared filesystem, which an in-memory storage cannot provide, so
  the sub-processes never saw the documents and the commit produced an empty
  index. Whoosh now detects storages that don't support cross-process writing
  (via the new `Storage.supports_multiproc_writing` flag, `True` only for
  `FileStorage`) and transparently falls back to a correct single-process
  writer with a warning. On-disk indexes still use the real multiprocessing
  writer (gh#38).

## [3.12.3] - 2026-07-17

### Fixed

- Span/phrase queries containing a wildcard or prefix sub-query (for example a
  `Sequence`/`SpanNear` phrase like `"ro* place house"`) no longer raise
  `Exception: Field does not support spans` on larger indexes. Wildcard and
  prefix queries default to `constantscore=True`, which builds a fast
  constant-scoring union (`ArrayUnionMatcher`) that does not expose positions.
  Span queries now build their sub-matchers with `needs_current=True`, forcing
  the wildcard to fall back to a position-aware matcher so `.spans()` works.
  The bug was intermittent because it only appeared once the index was large
  enough to select the array matcher (gh#49).

## [3.12.2] - 2026-07-17

### Fixed

- Date handling: `adatetime.disambiguated()` and `timespan.disambiguated()`
  now default `basedate` to the current UTC time when it is omitted or `None`,
  matching their documented behaviour (their docstrings even show calls with no
  argument). Previously, passing `None` — or resolving a range whose end was
  missing a field such as the year, e.g. `date:[oct 1970 to dec 8]` — raised
  `AttributeError: 'NoneType' object has no attribute 'year'`. An explicitly
  supplied `basedate` is still honoured (gh#50, reported by @CodeOptimist).

## [3.12.1] - 2026-07-17

### Fixed

- Query parser: malformed queries where a `NOT` (or any wrapper node) ends up
  wrapping no sub-node — for example `NOT OR foobar` — no longer raise
  `IndexError: list index out of range` from `Wrapper.query`. The empty wrapper
  now contributes no query and the rest of the expression parses normally, so
  `NOT OR foobar` yields `foobar` and a bare `NOT` yields the null query
  (gh#19, reported by @CodeOptimist).

### Documentation

- Rewrote the documentation landing page (`index.rst`). It previously opened
  with stale boilerplate (a "Bitbucket page" label and a "mailing list" link)
  and no description of the library. It now leads with a one-paragraph overview,
  a link to the live in-browser demo, a pointer to the quickstart, and an honest
  project-status note directing readers to the issue tracker and Discussions.
- Fixed the runnable examples in the "Indexing and searching N-grams" guide
  (`ngrams.rst`). Both examples were missing their `from whoosh.analysis import ...`
  imports (copy-pasting them raised `NameError`), and the `NgramFilter` example's
  documented output was simply wrong: with `minsize=2, maxsize=4` it omitted every
  2-gram (showing `['ren', 'rend', ...]` instead of the real `['re', 'ren',
'rend', ...]`), so a user checking their output against the docs would think the
  library was broken. The output is now the exact Python 3 result, and the `u''`
  prefixes were removed.
- Fixed the runnable examples in the "Stemming and variations" guide
  (`stemming.rst`). The `StemFilter` example was missing its
  `from whoosh.analysis import RegexTokenizer, StemFilter` import (copy-pasting
  it raised `NameError`), and the example outputs were modernized from Python 2
  (`[u"fundament", ...]` and `set([...])`) to the actual Python 3 output. The
  `variations()` example is now shown via `sorted(...)` since it returns a
  `set` with no meaningful order.
- Fixed the runnable examples in the "About analyzers" guide (`analysis.rst`).
  The interactive `LowercaseFilter(tokenizer(...))` example raised
  `TypeError: LowercaseFilter() takes no arguments` because `LowercaseFilter`
  is a class, not a function; it now instantiates the filter first
  (`lowercase = LowercaseFilter()`). Also modernized the example blocks to
  Python 3 (`print(...)` and Python 3 `repr` output without the `u''` prefix).

### Development

- Added `benchmark/regression.py`, a deterministic, standard-library-only
  performance-regression harness. It times index build, incremental adds, and
  single-term/two-term/prefix/sorted queries against a fixed seeded corpus,
  can save results to JSON, and with `--compare baseline.json` exits non-zero
  when any metric regresses beyond a tolerance (default 25%). Maintainers run
  it against the previous release before cutting a new one. This is developer
  tooling only; it does not change the installed package.

## [3.12.0] - 2026-07-17

### Added

- `whoosh stats --top-terms FIELD` lists the most frequent indexed terms in
  FIELD, most-frequent-first, with their total frequencies; `--top N` caps
  the list (default 10). Unknown fields and field types without term
  frequencies (e.g. NUMERIC/DATETIME) print a friendly error to stderr and
  exit 2 instead of a traceback. The `--json` payload is unchanged.
  Implements gh#24. Thanks to @Nitjsefnie for the contribution.

## [3.11.7] - 2026-07-17

### Fixed

- `IndexReader.field_terms()` no longer raises `OverflowError` (or yields
  garbage values) on `NUMERIC` and `DATETIME` fields. Numeric fields store
  extra lower-precision "shifted" terms to accelerate range queries; those
  bytestrings are internal encoding artifacts, not real field values, and
  decoding them produced out-of-range dates (`OverflowError`) for `DATETIME`
  and nonsense integers for `NUMERIC`. `field_terms()` now iterates only the
  full-precision tokens (via each field's `sortable_terms()`), so it returns
  exactly the distinct values that were indexed. Ordinary text fields are
  unaffected. Fixes gh#24 (reported upstream at mchaput/whoosh#24).

## [3.11.6] - 2026-07-17

### Fixed

- Boosts on `MultiTerm` queries (`Prefix`, `Wildcard`, `FuzzyTerm`,
  `TermRange`, and friends) are now applied to the final score. Previously
  `MultiTerm.matcher()` expanded the query into generated `Term` sub-queries
  _without_ carrying the parent's boost, so e.g. `Prefix("f", "app", boost=5)`
  scored identically to `boost=1`. The generated terms now carry the boost, and
  the wrapping `Or` no longer re-applies it (which would have multiplied the
  boost twice for multi-term expansions). Fixes gh#42 (reported upstream at
  mchaput/whoosh#42).

## [3.11.5] - 2026-07-17

### Fixed

- `DateParserPlugin` no longer raises
  `AttributeError: 'NoneType' object has no attribute 'year'` on date-range
  queries when constructed without an explicit `basedate`. The plugin's
  docstring promised it would fall back to the current time, but `self.basedate`
  was left as `None`; helpers such as `timespan().disambiguated()` require a
  concrete base date. `basedate` now defaults to the current UTC time, matching
  the documented behavior, while an explicitly supplied `basedate` is still
  respected. Fixes gh#50 (reported upstream at mchaput/whoosh#50).

## [3.11.4] - 2026-07-17

### Fixed

- `MultiCorrector.suggest()` no longer raises
  `TypeError: unsupported operand type(s) for -: 'int' and 'str'`. Its internal
  `_suggestions()` accumulated results in a dict keyed by suggestion and
  returned `seen.items()`, which yields `(suggestion, score)` tuples — reversed
  from the `(score, suggestion)` order that every other corrector and
  `Corrector.suggest()` rely on. The tuples are now emitted in the correct
  order, so merging suggestions from multiple correctors works again. Fixes
  gh#21 (reported upstream at mchaput/whoosh#21).

## [3.11.3] - 2026-07-17

### Fixed

- Sortable float `NUMERIC` fields no longer raise
  `struct.error: required argument is not an integer` when adding documents.
  The column stores values in their sortable (unsigned-integer) representation,
  but the column default (`NaN` for floats) was passed through unencoded, so
  the column writer tried to pack a float into an integer typecode. The field's
  default is now consistently kept as a raw value and encoded into the sortable
  representation when the column is created, which also fixes user-supplied
  `default=` values on sortable numeric fields. Fixes gh#44
  (reported upstream at mchaput/whoosh#44).

## [3.11.2] - 2026-07-17

### Fixed

- `Searcher.correct_query()` no longer raises
  `TypeError: 'int' object is not iterable` when the schema contains a
  `NUMERIC`, `DATETIME`, or `BOOLEAN` field. These field types store terms as
  sortable non-text bytes, so they can't be used as a source of
  Damerau-Levenshtein spelling suggestions; they are now skipped when building
  default correctors (you can still pass an explicit corrector for them via the
  `correctors` argument). Field types gained a `spellable` class flag that
  drives this behaviour. Fixes gh#55 (reported upstream at mchaput/whoosh#55).

### Changed

- Extended public-API type annotations to the `Searcher` document-lookup
  methods: `doc_count()`, `doc_count_all()`, `reader()`, `document()`,
  `documents()`, `document_number()`, and `document_numbers()` now carry
  explicit return types, improving editor/mypy hints on the read path.
- Annotated `Searcher.find()` (the parse-a-query-string-and-search convenience
  method) with `-> Results`, and added it to the type-check smoke fixture.

## [3.11.1] - 2026-07-16

### Changed

- **Type annotations for the writer public API.** `Index.writer()` is now
  annotated to return an `IndexWriter`, and the public `IndexWriter` methods
  `add_document`, `update_document`, `commit`, `cancel`, and the context-manager
  protocol (`__enter__`/`__exit__`) now carry explicit type hints. Whoosh3 ships
  a `py.typed` marker, so these annotations flow directly into users' editors and
  `mypy`/`pyright` runs — completing type coverage of the core index → write →
  search round trip. The `tests/typing_smoke.py` fixture (type-checked in CI) now
  exercises the writer as a context manager and `update_document`, guarding the
  annotations against regressions. No runtime behavior changes.
- **Type annotations for the search-results public API.** The user-facing
  `Results` methods (`is_empty`, `items`, `fields`, `has_exact_length`,
  `estimated_length`, `estimated_min_length`, `scored_length`, `docs`, `copy`,
  `score`, `docnum`, `has_matched_terms`) and the `Hit` dict-like accessors
  (`fields`, `keys`, `values`, `items`) now carry explicit return-type hints.
  With `py.typed` shipped, these flow into users' editors and `mypy`/`pyright`
  runs — so iterating results, reading scores/docnums, and pulling stored
  fields off a `Hit` are now fully typed for the read-back path that follows
  every search. The CI-type-checked `tests/typing_smoke.py` fixture now
  exercises these methods end-to-end. No runtime behavior changes.

## [3.11.0] - 2026-07-16

### Added

- **Python 3.14 support.** Python 3.14.0 was released on 2025-10-07 and is now
  the latest stable CPython. The full test suite (689 tests) is verified green
  on 3.14 in CI, including the multiprocessing writer under 3.14's new
  `forkserver` default start method on Linux. Whoosh now officially supports
  Python 3.9 through 3.14 and advertises the `Programming Language :: Python
:: 3.14` classifier.

## [3.10.0] - 2026-07-16

### Added

- **`whoosh search --sort-by score|mtime`** sorts results either by relevance
  score (the default, unchanged behavior) or by file modification time
  (newest first). `--count` still reports the true total regardless of sort
  order (gh#19). Thanks to [@abhiramvsmg](https://github.com/abhiramvsmg) for
  the first community feature contribution!

### Changed

- The `whoosh` CLI now prints the project home
  (`https://github.com/priya-sundaram-dev/whoosh`) in its `--help` epilog and
  `--version` output, so users can find docs, examples, and where to report
  issues without leaving the terminal.

## [3.9.0] - 2026-07-16

### Added

- **`whoosh search --no-highlight`** prints results as a plain, grep-friendly
  leading slice of the document body with no match markup — handy when piping
  output to other tools where the `UPPERCASED` match tokens get in the way
  (gh#11).
- **`whoosh search --snippet-chars N`** controls the maximum length of the
  context snippet shown per result (default 200). Applies to both the default
  text output and JSON snippets (gh#13).

## [3.8.3] - 2026-07-16

### Fixed

- **A failed `commit()` left the index write-locked.** `SegmentWriter`
  acquires the `WRITELOCK` in its constructor and only released it in
  `_finish()`, at the very end of `commit()`. If `commit()` raised partway
  through — for example a disk error while flushing the final segment or
  writing the TOC — `_finish()` was skipped, so the write lock stayed held.
  Every subsequent writer on that index then failed with `LockError`,
  effectively making the index read-only until the stale lock was removed by
  hand. `commit()` (and `cancel()`) now release the write lock and destroy the
  temp storage on failure before re-raising the original exception, so a
  failed write no longer wedges the index. Added regression tests covering
  both `commit()` and `cancel()` failure paths.

## [3.8.2] - 2026-07-16

### Fixed

- **`AsyncWriter` silently swallowed background failures.** When the writer
  could not be obtained immediately, `AsyncWriter` finishes the commit on a
  background thread. If that thread raised (e.g. a backend error while
  acquiring the writer or replaying buffered events), the exception vanished
  into the thread and the buffered documents were dropped with no signal to
  the caller — a silent data-loss hazard for the web/wiki transaction pattern
  `AsyncWriter` is designed for. The background thread now records any
  exception on the new `AsyncWriter.exception` attribute (which callers can
  check after `join()`), attempts to release the writer's lock so a failed
  commit doesn't leave the index locked, and always clears the `running` flag.
  Added regression tests for both the failure and success paths.

## [3.8.1] - 2026-07-16

### Fixed

- **File descriptor leak when closing memory-mapped compound segments.**
  Closing a `CompoundStorage` while a memory-mapped subfile (`BufferFile`) was
  still open raised `BufferError` internally and dropped the `mmap` reference
  without closing it, leaking one file descriptor per close. On long-running
  servers doing frequent index writes (e.g. wikis), this accumulated into
  "too many open files" errors. `BufferFile.close()` now releases its
  memoryview so the parent `mmap` can close cleanly, and `CompoundStorage.close()`
  guarantees the mapping is released even when a view is still outstanding.
  Added regression tests covering the unclosed-mmap and fd-leak paths.

## [3.8.0] - 2026-07-15

### Added

- Added repeatable `whoosh search --field NAME` options for restricting a
  query to equally weighted index fields while preserving the existing
  defaults when the option is omitted. Thanks to @sahilmathur254 for the
  contribution (#14, #15).

### Changed

- Clarified the package description so PyPI search results make it obvious this
  is the actively maintained Whoosh (Python 3.9-3.13), distinct from the
  long-dormant `Whoosh` and `whoosh-reloaded` distributions.

## [3.7.0] - 2026-07-15

### Added

- **`whoosh stats` subcommand.** Print a summary of an existing index without
  running a query: document count (and count including deleted docs when they
  differ), the schema fields with their types, the index size on disk, and when
  it was last updated. Add `--json` for machine-readable output. Useful for
  quickly inspecting an index or wiring index health into scripts (#10).
- **`whoosh index --exclude`.** The CLI now supports excluding specific files or
  directories during indexing using the `--exclude` flag with glob patterns
  (e.g., `--exclude "build/*"`). It can be specified multiple times. Excluded
  directories are pruned during the walk, so they are never descended into.
  Thanks to [@PushkarP-404](https://github.com/PushkarP-404) for the
  contribution (#7, #12).

## [3.6.0] - 2026-07-15

### Added

- **`whoosh --version` / `-V`.** The CLI now has a top-level `--version` (and
  short `-V`) flag that prints the installed Whoosh version and exits. Thanks
  to [@abhiramvsmg](https://github.com/abhiramvsmg) for the contribution
  (#6, #8).

- **`whoosh search` match summary.** In the default text output mode, `whoosh
search` now prints a short summary line to **stderr** — `N matches.` when
  everything is shown, or `Showing X of Y matches.` when results are truncated
  by `--limit`. Because it goes to stderr, stdout stays clean for piping, and
  the line is suppressed entirely under `--json`, `--html`, and `--count`.
  Thanks to [@Krshs90](https://github.com/Krshs90) for the contribution
  (#13, #14).

## [3.5.0] - 2026-07-15

### Added

- **`whoosh search --limit` validation and `--fields`.** `--limit` now rejects
  non-positive values with a clear argparse error (exit code 2) instead of
  silently accepting `0`/negatives. The new `--fields` option restricts which
  stored fields appear in the output, in both text and JSON modes, and reports
  a helpful "unknown field" error (listing the valid field names) when given a
  field that is not in the schema. Thanks to
  [@Krshs90](https://github.com/Krshs90) for the contribution (#9, #10).
- **`whoosh search --count`.** New flag that prints only the number of matching
  documents as a single integer and exits, ignoring `--limit` to report the true
  total. Handy for shell pipelines and scripting. Mutually exclusive with
  `--json` and `--html`. Thanks to [@Krshs90](https://github.com/Krshs90) for the
  contribution (#11, #12).

## [3.4.0] - 2026-07-15

### Added

- **`whoosh search --json`.** The `whoosh search` command can now emit a
  machine-readable JSON array of results (path, score, snippet, and title when
  present) instead of the human-readable text output, making it easy to pipe
  results into `jq` or other tooling. The flag is mutually exclusive with
  `--html`. Thanks to [@Krshs90](https://github.com/Krshs90) for the
  contribution (#6, #7).
- **Static-site search cookbook + example.** New
  `examples/static_site_search.py` indexes a directory of Markdown/RST/text
  files and searches them from the command line with highlighted snippets
  (title boosted over body, re-indexable via a unique `path` key) — a
  server-free way to add search to a static site or ship an index alongside a
  desktop app. Documented in the cookbook. Thanks to
  [@Krshs90](https://github.com/Krshs90) (#5, #8).

### Tests

- Added `test_concurrent_writers_lock` covering the file-storage writer lock
  path: a second concurrent `writer()` raises `LockError`, and a fresh writer
  succeeds once the first is cancelled. Thanks to
  [@Krshs90](https://github.com/Krshs90) (#4, #8).

## [3.3.1] - 2026-07-14

### Fixed

- **`RamStorage` indexes no longer raise `NameError` on large writes.** When an
  in-memory index received enough documents (or used a low `limitmb`) that the
  posting pool spilled sorted "run" files, committing failed with
  `NameError: <name>.run`. The run files created in the temporary in-memory
  storage were never actually persisted, because the pool handed out the bare
  underlying buffer via `raw_file()` and the `StructFile.onclose` callback that
  saves the bytes was bypassed. The pool now keeps the `StructFile` wrapper so
  the callback fires on close; disk-backed storages are unaffected. Fixes a
  long-standing bug reported across the original tracker
  (whoosh-community#450) and the reloaded fork (Sygil-Dev/whoosh-reloaded#116).
  Added a regression test that spills multiple runs into a `RamStorage` index
  and verifies the committed index is searchable.

### Documentation

- Documented the `strict_phrase=True` option of `Hit.highlights()` /
  `Highlighter.highlight_hit()`, which highlights only the terms that form an
  actual phrase match instead of every occurrence of the individual words. This
  answers a long-standing user question (whoosh-community#486). Added a
  "Phrase-accurate highlighting" section to the highlighting guide, a cookbook
  note, and the missing `:param strict_phrase:` entry in the API docstring, plus
  a regression test.

## [3.3.0] - 2026-07-14

### Added

- **`whoosh` command-line tool.** Installing `whoosh3` now also installs a
  `whoosh` console script for indexing and searching a folder of files from
  your terminal — a pure-Python, ranked, stemmed alternative to `grep` for
  notes/docs/source trees. `whoosh index PATH` builds an on-disk index (with
  `--update` for incremental re-indexing that also drops deleted files, and
  `--ext .md,.txt` to filter by extension); `whoosh search "QUERY" PATH`
  returns BM25-ranked results with highlighted snippets and supports the full
  query language (`AND`/`OR`/`NOT`, `"phrases"`, `field:term`), plus `--limit`
  and `--html` (emit `<mark>` highlights). The implementation lives in the new
  `whoosh.cli` module and uses only the public API, so it doubles as a
  copy-pasteable example ([`examples/search_cli.py`](examples/search_cli.py)
  now re-exports it). Covered by a new `tests/test_cli.py` suite.

## [3.2.0] - 2026-07-14

### Added

- **CI type-checking smoke job (gh#121).** A new `types` job in CI runs `mypy`
  against `tests/typing_smoke.py` — a realistic downstream-usage snippet
  (create an index, build a `Schema` from the field constructors, add a
  document, parse a query, run `searcher.search(...)`, iterate results). This
  guards that the annotations on the public API stay present and correct for
  users' editors and `mypy`/`pyright` runs, failing loudly in CI if a change
  regresses them. Configured under `[tool.mypy]` in `pyproject.toml` with
  `follow_imports = "silent"` so the still-untyped internals don't produce
  noise while the public-facing surface is genuinely checked.
- **Typed searching layer (gh#121).** The search-and-results API you use on every
  query now carries type hints: `Searcher` (`__init__`, `search`, `search_page`,
  `search_with_collector`) and the result containers `Results`, `Hit`, and
  `ResultsPage`. Editors autocomplete `search(q, limit=..., ...)` and type
  checkers verify that `search()` returns a `Results` and `search_page()` a
  `ResultsPage`. Hints use `from __future__ import annotations` (no runtime cost
  or behavior change) and are guarded by a regression test.
- **Typed query parser (gh#121).** `whoosh.qparser.QueryParser` — the class you
  use to turn user input into queries — now carries type hints on its
  constructor and core methods (`parse`, `parse_`, `process`, `tag`), plus the
  premade factory functions `MultifieldParser`, `SimpleParser`, and
  `DisMaxParser`. Editors autocomplete `parse(text, normalize=..., debug=...)`
  and type checkers verify that `parse()` returns a `whoosh.query.Query`. Hints
  use `from __future__ import annotations` (no runtime cost or behavior change)
  and are guarded by a regression test.
- **Typed field constructors (gh#121).** The field types you write in every
  `Schema` — `TEXT`, `ID`, `IDLIST`, `KEYWORD`, `NUMERIC`, `DATETIME`,
  `BOOLEAN`, `STORED`, and `COLUMN` — now carry parameter and return
  annotations on their constructors. Editors autocomplete kwargs like
  `stored=`, `unique=`, `phrase=`, `commas=`, and type checkers verify your
  field definitions. Hints use `from __future__ import annotations` (no runtime
  cost or behavior change) and are guarded by a regression test.
- **More public typing (gh#121).** `whoosh.fields.Schema` — the class every user
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

- **PEP 561 typing support (gh#121).** Whoosh now ships a `py.typed` marker and
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
  _year_ of an ISO date, so the overall (end-anchored) parse failed on the rest
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
  override, so _every_ matching document came back regardless of the filter.
  The allow/restrict logic (and `filtered_count` bookkeeping) now lives in
  `FilterCollector.matches()`, so the filter is honored no matter what outer
  collector wraps it. Added a regression test.
- Sorting or faceting by a sortable/column field returned **scrambled** results
  after documents were added through a `BufferedWriter` (the quasi-real-time
  writer). Root cause: `BufferedWriter` opens a fresh short-lived per-document
  writer for every `add_document()` call, and the in-memory `MemoryCodec`
  recreated (truncated) each column file per session — so the reader, which
  reads `doc_count_all()` entries, filled every doc except the last-written one
  with the column's _default_ value. Sorting on those near-identical default
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
