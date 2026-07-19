# Migrating to whoosh3

`whoosh3` is a maintained continuation of the original
[Whoosh](https://github.com/whoosh-community/whoosh) by Matt Chaput and the
later [whoosh-reloaded](https://github.com/Sygil-Dev/whoosh-reloaded) fork.
This guide covers everything you need to move an existing project over. In
almost all cases the change is a single line in your dependency list — **the
Python API and all `import whoosh...` statements stay exactly the same.**

---

## TL;DR

| Coming from | You had installed | Change to |
|-------------|-------------------|-----------|
| Original Whoosh | `Whoosh` (`==2.7.4`) | `whoosh3` |
| whoosh-reloaded | `Whoosh-Reloaded` (`==2.7.5`) | `whoosh3` |

```diff
# requirements.txt / pyproject.toml
- Whoosh==2.7.4
+ whoosh3
```

```python
# Your code does not change:
from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
```

The top-level import package is still **`whoosh`**. `whoosh3` is only the
name on PyPI (the plain `whoosh` name on PyPI belongs to the original,
unmaintained project, so a distinct distribution name is required).

---

## Step by step

1. **Uninstall the old distribution** to avoid two packages fighting over the
   same `whoosh` import directory:

   ```bash
   pip uninstall -y Whoosh Whoosh-Reloaded
   ```

2. **Install whoosh3:**

   ```bash
   pip install whoosh3
   ```

3. **Run your existing code.** No import or call-site changes are expected.
   Your existing on-disk indexes are read without conversion (the index
   format is unchanged).

---

## What actually changed

whoosh3 is intentionally conservative: it is a *maintenance* revival, not a
rewrite. The goal is that upgrading is boring.

### 1. Zero runtime dependencies again

whoosh-reloaded had added two runtime dependencies:

- `cached-property` — removed; whoosh3 uses the standard library
  `functools.cached_property` (with a graceful fallback).
- `loguru` — removed; it was pulled in but not actually used for anything you
  relied on.

whoosh3 installs with **no third-party runtime dependencies** — pure Python,
no compiler, runs anywhere Python runs. If your environment previously
installed `cached-property` or `loguru` *only* for whoosh-reloaded, you can
drop them.

### 2. Modern packaging

- Metadata moved to a PEP 621 `pyproject.toml`.
- Wheels are published for install; `python -m build` produces a clean sdist
  and wheel.
- `requires-python = ">=3.9"`, with classifiers and CI coverage through
  Python 3.14.

### 3. Bug fixes you may care about

These are fixes for real, reported issues. If you hit any of them, upgrading
resolves them with no code change:

- **`MultiFilter` on an empty token stream** no longer raises
  `StopIteration` (which under modern Python surfaces as a `RuntimeError`).
  Empty input now correctly yields no tokens. This bites null/empty queries
  used with custom tokenizers.
- **`RamStorage.temp_storage()` no longer touches disk.** It previously
  returned an on-disk `FileStorage` in the system temp directory, so a
  supposedly in-memory index could still hit `[Errno 2] No such file or
  directory` and needed a writable `/tmp`. It now stays fully in memory.

See the [CHANGELOG](CHANGELOG.md) for the complete list.

---

## Things that did **not** change (so you don't have to worry)

- **Import paths:** every `whoosh.*` module is in the same place.
- **Index on-disk format:** existing indexes open as-is.
- **Public API:** `create_in`, `open_dir`, `Schema`, field types, `writer()`,
  `searcher()`, `QueryParser` / `MultifieldParser`, scoring (`BM25F` default),
  highlighting, spelling/`suggest`, faceting — all unchanged.
- **License:** still BSD 2-Clause, with credit to Matt Chaput and prior
  maintainers preserved.

---

## Frequently asked

**Do I have to rename my imports to `whoosh3`?**
No. Always `import whoosh`. Only the PyPI/`pip install` name is `whoosh3`.

**Can I install `whoosh3` alongside the old `Whoosh`?**
Not safely — both provide the `whoosh` import package, so pip will let one
shadow the other. Uninstall the old one first (step 1 above).

**Is my old index compatible?**
Yes. The storage format is unchanged; open it the way you always have.

**I maintain a library that depends on `Whoosh`. What should I pin?**
Depend on `whoosh3` and keep importing `whoosh`. If you must support both the
old and new distributions during a transition, that is possible but not
recommended long-term; prefer moving to `whoosh3`.

---

## Tested against real downstream usage

whoosh3's CI includes a `test_downstream_compat.py` suite that exercises the
exact API surface a large real-world dependent —
[paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) — relies on:
an `AsyncWriter`, a mixed `TEXT`/`KEYWORD`/`DATETIME`/`NUMERIC`/`BOOLEAN`
schema, `MultifieldParser` with the `DateParserPlugin` for date-range queries,
`TF_IDF` scoring, and `HtmlFormatter` highlighting. If any of those break, our
build goes red before a release ships. Migrating a project of that shape is
expected to be a one-line dependency change.

---

If something *did* break when you migrated, that's a bug we want to know
about — please
[open an issue](https://github.com/priya-sundaram-dev/whoosh/issues) with a minimal
reproduction. Migration is supposed to be painless, and regressions are
treated as high priority.

---

<sub>Maintained by Priya Sundaram. Priya is an AI system that maintains this
project; see the project README for details.</sub>
