"""Guard tests: the published demo/marketing site must not advertise a stale
version.

Several static pages under ``demo/`` state the current release number (in
schema.org JSON-LD and in human-readable prose). These are easy to forget when
cutting a release, and a stale "latest is X" claim on the "is Whoosh still
maintained?" page actively undermines the project's credibility. These tests
tie those references back to ``whoosh.__version_str__`` so a forgotten bump
fails CI instead of shipping.
"""

import os
import re

import whoosh

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, os.pardir, "demo")

VERSION = whoosh.__version_str__


def _read(name):
    path = os.path.join(DEMO, name)
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_index_jsonld_software_version_matches_package():
    html = _read("index.html")
    m = re.search(r'"softwareVersion"\s*:\s*"([^"]+)"', html)
    assert m, "index.html is missing a schema.org softwareVersion field"
    assert m.group(1) == VERSION, (
        "index.html JSON-LD softwareVersion=%r but package version is %r; "
        "bump the site when cutting a release." % (m.group(1), VERSION)
    )


def test_maintained_page_latest_release_matches_package():
    html = _read("is-whoosh-still-maintained.html")
    # e.g. "the latest is <strong>whoosh3&nbsp;3.24.0</strong>"
    m = re.search(r"whoosh3(?:&nbsp;|\s)+(\d+\.\d+\.\d+)", html)
    assert m, "is-whoosh-still-maintained.html no longer names a whoosh3 release"
    assert m.group(1) == VERSION, (
        "is-whoosh-still-maintained.html advertises whoosh3 %r but package "
        "version is %r; update the page when cutting a release."
        % (m.group(1), VERSION)
    )
