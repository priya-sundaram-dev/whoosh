# Contributing to Whoosh

Thanks for your interest in Whoosh! Contributions of all kinds are welcome:
bug reports, reproductions, docs, examples, and code.

## Ground rules

- **Be kind.** This is a small, volunteer-scale project. Assume good faith.
- **Keep Whoosh pure Python.** No mandatory native dependencies — the
  no-compile install is a headline feature. Optional accelerators, if any, go
  behind extras and must never be required.
- **Backwards compatibility matters.** Existing indexes and public APIs should
  keep working across minor releases. Breaking changes wait for a major release
  and come with a migration note.

## Getting set up

```bash
git clone https://github.com/priya-sundaram-dev/whoosh
cd whoosh
python -m venv .venv && source .venv/bin/activate
pip install --editable ".[dev]"
pytest
```

## Making a change

1. Open an issue first for anything non-trivial, so we can agree on the approach.
2. Add or update tests for any behavior change; keep the suite green.
3. Run `ruff check .` and `pytest` locally before opening a PR.
4. Keep PRs focused — one logical change per PR is much easier to review.
5. Update `CHANGELOG.md` under "Unreleased" if your change is user-visible.

## Reporting a bug

Please include:
- Your Python version and OS.
- The Whoosh version (`python -c "import whoosh; print(whoosh.versionstring())"`).
- A minimal, runnable snippet that reproduces the problem.

## Reviews and releases

Maintainers aim to respond to issues and PRs promptly and kindly. Releases are
cut only from green CI across all supported Python versions. Before a release,
maintainers also run the performance-regression benchmark against the previous
release to make sure nothing got noticeably slower:

```bash
python benchmark/regression.py --compare baseline.json
```

See [`benchmark/README.md`](benchmark/README.md) for details.

Thank you for helping keep Whoosh healthy!
