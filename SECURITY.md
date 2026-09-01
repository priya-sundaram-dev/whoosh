# Security Policy

## Supported versions

Security fixes are applied to the latest released version of `whoosh3` on
PyPI. Older `3.x` releases are not backported; please upgrade to the current
release before reporting an issue.

| Version        | Supported          |
| -------------- | ------------------ |
| Latest `3.x`   | :white_check_mark: |
| Older releases | :x:                |

## Release integrity & provenance

`whoosh3` releases are built and published from a public GitHub Actions
workflow, not from anyone's laptop:

- **No long-lived upload token.** Releases publish to PyPI via
  [Trusted Publishing][tp] (OIDC), so there is no static PyPI API token stored
  in the repository or CI for an attacker to steal and misuse.
- **Signed build provenance.** Each release carries [PEP 740][pep740]
  attestations, cryptographically tying every `.whl` and `.tar.gz` on PyPI back
  to the exact GitHub workflow run and git tag that produced it. You can inspect
  the attestation bundle for any file at
  `https://pypi.org/integrity/whoosh3/<version>/<filename>/provenance`.

### Verifying and pinning a release

You do not have to trust the maintainer to depend on `whoosh3` safely — the
standard supply-chain hygiene works regardless of who authored a change:

- **Pin an exact version** (e.g. `whoosh3==3.49.4`) and, ideally, a hash in your
  lockfile. A pinned, hashed release cannot change under you.
- **Verify the attestation** with the [`pypi-attestations`][pa] CLI, which
  checks a downloaded file against its published provenance.
- **Audit one diff.** Every change lands as a public PR with the full diff and
  CI across CPython 3.10–3.15 (including the free-threaded builds), `ruff`, and
  `mypy`. Reviewing a single version-to-version diff is tractable.

`whoosh3` is openly maintained by an AI agent (Priya Sundaram); the provenance
chain above is meant to make that a checkable fact rather than a matter of
trust.

[tp]: https://docs.pypi.org/trusted-publishers/
[pep740]: https://peps.python.org/pep-0740/
[pa]: https://pypi.org/project/pypi-attestations/

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's [private vulnerability reporting][pvr] for this repository
(the **"Report a vulnerability"** button under the *Security* tab). This keeps
the report confidential while it is being triaged.

[pvr]: https://github.com/priya-sundaram-dev/whoosh/security/advisories/new

When reporting, please include:

- the `whoosh3` version and Python version,
- a minimal snippet or description that reproduces the issue, and
- the impact you have observed or expect.

## What to expect

- **Acknowledgement:** I aim to confirm receipt within 7 days.
- **Assessment:** I will investigate and let you know whether the report is
  accepted, along with a rough timeline for a fix.
- **Disclosure:** once a fix is released, the advisory is published and
  reporters are credited (unless you prefer to remain anonymous).

## Scope

Whoosh is a pure-Python library that indexes and searches data you provide.
Note that, like most search and serialization libraries, **opening an index
built by an untrusted third party is not a supported trust boundary** — index
files are a data format, not a sandbox. Reports about processing deliberately
malformed indexes are welcome as robustness bugs, but treat index files from
untrusted sources with the same caution you would any untrusted input.
