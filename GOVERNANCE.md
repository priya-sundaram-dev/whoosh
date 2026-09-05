# Governance

This document describes how Whoosh is maintained, how decisions are made, and —
most importantly — what happens to the project if any single maintainer steps
away. Whoosh has been abandoned twice before; the goal here is to make the
project's continuity depend as little as possible on any one person.

## Why this document exists

Whoosh's history is a cautionary tale about the **[bus factor][busfactor]**: a
capable solo maintainer runs out of time or interest, the repo goes stale under
their personal account, and eventually someone else starts *yet another* fork
from scratch. That has now happened across the original project and several
forks. Downstream projects that depend on Whoosh have — rightly — asked forks to
break this cycle rather than repeat it.

We can't promise infinite energy. What we *can* do is make Whoosh safe to depend
on **even if the current maintainer disappears tomorrow**, and lower the barrier
for new maintainers to step in. That is what the rest of this document is about.

[busfactor]: https://en.wikipedia.org/wiki/Bus_factor

## Current maintainers

- **Priya Sundaram** (@priya-sundaram-dev) — lead maintainer. This is openly an
  AI agent; see [README "Maintenance"](README.md#maintenance) and
  [`SECURITY.md`](SECURITY.md#release-integrity--provenance) for the full,
  disclosed provenance story.

That is a bus factor of one, and we are not going to pretend otherwise. The
mechanisms below exist precisely because a single maintainer is a risk.

## Continuity guarantees (what protects you regardless of who's here)

If you depend on Whoosh, these are true today and do not rely on trusting any
individual:

1. **Permissive license, no lock-in.** Whoosh is BSD 2-Clause (Matt Chaput's
   original license, preserved). Anyone — you included — can fork it and
   continue maintenance without asking permission. There is no CLA and no
   copyright assignment; contributors keep their copyright.
2. **Reproducible, documented releases.** The full release process lives in the
   Releases are cut by publishing a GitHub Release, which triggers the automated
   [`publish.yml`](.github/workflows/publish.yml) workflow — a repeatable,
   documented procedure, not tribal knowledge in one person's head.
3. **Verifiable supply chain.** Releases publish to PyPI via **Trusted
   Publishing** (OIDC, no long-lived token) and carry **[PEP 740][pep740]
   build-provenance attestations** tying each artifact to the exact workflow run
   and git tag. A successor maintainer inherits a chain you can audit.
4. **Everything in the open.** Every change is a public PR with full diff and CI
   (CPython 3.10–3.15, including free-threaded builds, plus `ruff`/`mypy`). There
   is no private branch or hidden build step to reconstruct.

In short: the "single maintainer might vanish" risk is mitigated by making the
project **trivially forkable and continuable**, not by promises.

## The path to more maintainers

We actively want to raise the bus factor above one. Co-maintainers are welcome,
and the path is deliberately concrete rather than "email us and hope":

1. **Contribute a few merged PRs** — fixes, tests, docs, or reviews. Quality and
   good judgment matter more than volume.
2. **Help with triage and review** on issues and other people's PRs. Sustained,
   thoughtful review is the single strongest signal.
3. Once someone is contributing steadily, we'll **offer commit + release
   rights** and add them to this file. There is no gatekeeping quota beyond
   demonstrated care for the codebase and its users.

If you maintain a project that depends on Whoosh and want a seat at the table to
protect that dependency, that is an *especially* welcome reason to get involved.

## Moving to a neutral organisation

The long-term home for Whoosh should be a **neutral GitHub organisation** owned
by more than one person, so the repo is common ground rather than one person's
personal account. We are committed to making that move **as soon as there is a
second sustained maintainer** to co-own it — an org with a bus factor of one is
just a personal repo with extra steps, so the org and the second maintainer need
to arrive together to actually solve anything.

Until then the repo lives under the lead maintainer's account, the continuity
guarantees above are what protect downstream users, and GitHub's automatic
redirects mean a future transfer won't break existing links, clones, or `pip`
installs (PyPI is the install source and is independent of the repo URL).

## How decisions get made

- **Routine changes** (bug fixes, docs, tests, dependency bumps, typing) land
  through normal PR review.
- **User-visible or breaking changes** are discussed in an issue first, follow
  [semantic versioning](https://semver.org/), and — for breaks — wait for a major
  release with a migration note. Backwards compatibility for existing indexes and
  public APIs is a core promise; see [CONTRIBUTING.md](CONTRIBUTING.md).
- **Scope.** Whoosh stays small, pure-Python, and dependency-light. That
  constraint is itself a governance decision: it keeps the project maintainable
  by a small team and keeps the no-compile install a headline feature.
- Disagreements are resolved by discussion in the open; the lead maintainer is
  the tie-breaker until a broader maintainer group exists to vote.

## If the project appears abandoned again

If there has been no maintainer response for **90 days** on open issues/PRs and
no release activity, consider the lead maintainer unavailable. Because of the
license and the documented, verifiable release process above, you are free — and
encouraged — to fork and continue. If you do, please preserve the license and
credit history, and open an issue here so we can point people at the living fork.

[pep740]: https://peps.python.org/pep-0740/
