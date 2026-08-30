#!/usr/bin/env python3
"""Bump the whoosh package version *and* every place the site advertises it, in
one atomic edit, so cutting a release never leaves CI red.

Background
----------
The packaged version lives in ``src/whoosh/__init__.py`` as the ``__version__``
tuple (the single source of truth; ``pyproject.toml`` reads
``whoosh.__version_str__``). A couple of static marketing pages under ``demo/``
also state the current release number, and ``tests/test_site_version_sync.py``
fails CI if they drift. Historically the version bump and the site update landed
in *separate* commits, so every release commit went red until the follow-up docs
commit fixed the site. This script updates all of them together.

Usage
-----
    python scripts/bump_version.py 3.29.0        # apply the bump
    python scripts/bump_version.py 3.29.0 --check # verify everything is in sync
    python scripts/bump_version.py --check        # verify current version is consistent

After running, review ``git diff``, add a ``## [X.Y.Z]`` section to
``CHANGELOG.md``, commit everything together, then tag ``vX.Y.Z``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))

INIT = os.path.join(ROOT, "src", "whoosh", "__init__.py")
INDEX_HTML = os.path.join(ROOT, "demo", "index.html")
MAINTAINED_HTML = os.path.join(ROOT, "demo", "is-whoosh-still-maintained.html")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

# Every file whose contents must move together in the single release commit.
# Keeping the version bump and the site pages in one commit is what stops the
# release commit's CI from going red before a follow-up docs fix.
RELEASE_FILES = [INIT, INDEX_HTML, MAINTAINED_HTML, CHANGELOG]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def current_version() -> str:
    text = _read(INIT)
    m = re.search(r"__version__:\s*[Tt]uple\[int, \.\.\.\]\s*=\s*\(([^)]+)\)", text)
    if not m:
        raise SystemExit("Could not find __version__ tuple in %s" % INIT)
    parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
    return ".".join(parts)


def _sub_once(text: str, pattern: str, repl: str, path: str) -> str:
    new, n = re.subn(pattern, repl, text)
    if n != 1:
        raise SystemExit(
            "Expected exactly 1 version reference matching %r in %s, found %d"
            % (pattern, path, n)
        )
    return new


def set_version(new: str) -> None:
    a, b, c = new.split(".")

    init = _read(INIT)
    init = _sub_once(
        init,
        r"(__version__:\s*[Tt]uple\[int, \.\.\.\]\s*=\s*\()[^)]+(\))",
        r"\g<1>%s, %s, %s\g<2>" % (a, b, c),
        INIT,
    )
    _write(INIT, init)

    idx = _read(INDEX_HTML)
    idx = _sub_once(
        idx,
        r'("softwareVersion"\s*:\s*")\d+\.\d+\.\d+(")',
        r"\g<1>%s\g<2>" % new,
        INDEX_HTML,
    )
    _write(INDEX_HTML, idx)

    mnt = _read(MAINTAINED_HTML)
    mnt = _sub_once(
        mnt,
        r"(whoosh3(?:&nbsp;|\s)+)\d+\.\d+\.\d+",
        r"\g<1>%s" % new,
        MAINTAINED_HTML,
    )
    _write(MAINTAINED_HTML, mnt)


def check(expected: str | None = None) -> int:
    pkg = current_version()
    expected = expected or pkg
    problems = []

    idx = _read(INDEX_HTML)
    m = re.search(r'"softwareVersion"\s*:\s*"([^"]+)"', idx)
    if not m:
        problems.append("index.html: missing softwareVersion")
    elif m.group(1) != expected:
        problems.append("index.html softwareVersion=%s != %s" % (m.group(1), expected))

    mnt = _read(MAINTAINED_HTML)
    m = re.search(r"whoosh3(?:&nbsp;|\s)+(\d+\.\d+\.\d+)", mnt)
    if not m:
        problems.append("is-whoosh-still-maintained.html: no whoosh3 release named")
    elif m.group(1) != expected:
        problems.append(
            "is-whoosh-still-maintained.html whoosh3 %s != %s" % (m.group(1), expected)
        )

    if expected != pkg:
        problems.append("package __version__=%s != requested %s" % (pkg, expected))

    if problems:
        print("OUT OF SYNC:")
        for p in problems:
            print("  -", p)
        return 1
    print("In sync: package and site all report %s" % expected)
    return 0


def changelog_has_section(version: str) -> bool:
    """True if CHANGELOG.md has a released heading for ``version``.

    Accepts either ``## [X.Y.Z] - DATE`` or ``## X.Y.Z`` styles so the guard
    does not fight a maintainer's exact heading formatting.
    """
    text = _read(CHANGELOG)
    esc = re.escape(version)
    return bool(re.search(r"^##\s+\[?%s\]?" % esc, text, re.MULTILINE))


def commit_release(version: str) -> int:
    """Stage the version + site + changelog files and make one release commit.

    Refuses to run unless everything is in sync and the CHANGELOG already has a
    heading for this version, so a release can never land the site pages in a
    separate commit (which would turn the release commit's CI red).
    """
    import subprocess

    if check(version) != 0:
        print("Refusing to commit: package/site are out of sync.")
        return 1
    if not changelog_has_section(version):
        print(
            "Refusing to commit: CHANGELOG.md has no '## %s' section yet.\n"
            "Add the release notes for %s first, then re-run with --commit."
            % (version, version)
        )
        return 1
    subprocess.run(["git", "add", "--"] + RELEASE_FILES, cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", "release: %s" % version], cwd=ROOT, check=True
    )
    print(
        "Committed 'release: %s'. Now tag it: git tag v%s && git push --tags"
        % (version, version)
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version", nargs="?", help="new X.Y.Z version")
    ap.add_argument("--check", action="store_true", help="verify sync, do not edit")
    ap.add_argument(
        "--commit",
        action="store_true",
        help="stage the version+site+CHANGELOG files and make one 'release: X.Y.Z' "
        "commit (requires CHANGELOG section to already exist)",
    )
    args = ap.parse_args()

    if args.check and not args.version:
        return check()
    if not args.version:
        ap.error("a version argument is required (or use --check alone)")
    if not SEMVER_RE.match(args.version):
        ap.error("version must be X.Y.Z, got %r" % args.version)

    if args.check:
        return check(args.version)

    if args.commit:
        return commit_release(args.version)

    set_version(args.version)
    print("Bumped package + site to %s" % args.version)
    print(
        "Now: update CHANGELOG.md, review `git diff`, then either commit by hand or\n"
        "re-run `python scripts/bump_version.py %s --commit` for one atomic commit; "
        "finally tag v%s" % (args.version, args.version)
    )
    return check(args.version)


if __name__ == "__main__":
    sys.exit(main())
