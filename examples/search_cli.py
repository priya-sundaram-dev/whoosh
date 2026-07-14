#!/usr/bin/env python3
"""A tiny command-line full-text search tool built on Whoosh.

Index a folder of text/markdown/source files and search it from your
terminal -- no server, no external service, pure Python.

Since Whoosh 3.3.0 this ships as a real console script, so after
``pip install whoosh3`` you can just run::

    whoosh index ~/notes
    whoosh search "full text search" ~/notes

This example file simply re-exports that implementation
(:mod:`whoosh.cli`) so you can still run it directly::

    python search_cli.py index .
    python search_cli.py search "full text search"

    # Re-index only changed files (fast; uses file mtimes)
    python search_cli.py index . --update

    # Limit which files get indexed
    python search_cli.py index ~/notes --ext .md,.txt,.rst

Everything uses only the public Whoosh API, so you can copy
``whoosh/cli.py`` into your own project and adapt it freely.

Author: Priya Sundaram (maintainer of the Whoosh revival). Written with the
help of an AI assistant.
"""
from __future__ import annotations

# The implementation now lives in the installable package so the same code
# powers both the ``whoosh`` console script and this runnable example.
from whoosh.cli import (  # noqa: F401
    DEFAULT_EXTS,
    INDEX_DIRNAME,
    build_parser,
    build_schema,
    cmd_index,
    cmd_search,
    iter_files,
    main,
    read_text,
)

if __name__ == "__main__":
    raise SystemExit(main())
