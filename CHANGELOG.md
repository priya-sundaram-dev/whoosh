# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/) and the format is loosely based on
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
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
- `whoosh.analysis.TeeFilter.__eq__` compared `self.filters == other.fitlers`
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
  `RegexTokenizer` that Unicode-normalizes its input *before* tokenizing. This
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
  words against the *raw* source text re-split on whitespace, so a document
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
  allowed difference in *position* between adjacent words (1 = adjacent), so a
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
- `whoosh index --dry-run`: preview which files *would* be indexed under the
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
  *all* of the words (an `AND` of the terms) when the searched field does not
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
  *without* carrying the parent's boost, so e.g. `Prefix("f", "app", boost=5)`
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
- **CI type-checking smoke job (gh#3).** A new `types` job in CI runs `mypy`
  against `tests/typing_smoke.py` — a realistic downstream-usage snippet
  (create an index, build a `Schema` from the field constructors, add a
  document, parse a query, run `searcher.search(...)`, iterate results). This
  guards that the annotations on the public API stay present and correct for
  users' editors and `mypy`/`pyright` runs, failing loudly in CI if a change
  regresses them. Configured under `[tool.mypy]` in `pyproject.toml` with
  `follow_imports = "silent"` so the still-untyped internals don't produce
  noise while the public-facing surface is genuinely checked.
- **Typed searching layer (gh#3).** The search-and-results API you use on every
  query now carries type hints: `Searcher` (`__init__`, `search`, `search_page`,
  `search_with_collector`) and the result containers `Results`, `Hit`, and
  `ResultsPage`. Editors autocomplete `search(q, limit=..., ...)` and type
  checkers verify that `search()` returns a `Results` and `search_page()` a
  `ResultsPage`. Hints use `from __future__ import annotations` (no runtime cost
  or behavior change) and are guarded by a regression test.
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
