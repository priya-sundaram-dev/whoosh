#!/usr/bin/env python3
"""A tiny command-line full-text search tool built on Whoosh.

Index a folder of text/markdown/source files and search it from your
terminal -- no server, no external service, pure Python.

    # Index the current directory (creates ./.whoosh_index/)
    python search_cli.py index .

    # Search it, with highlighted snippets
    python search_cli.py search "full text search"

    # Re-index only changed files (fast; uses file mtimes)
    python search_cli.py index . --update

    # Limit which files get indexed
    python search_cli.py index ~/notes --ext .md,.txt,.rst

This is a runnable example that ships with Whoosh (whoosh3 on PyPI). It is
deliberately a single, dependency-free file you can copy into your own project
and adapt. Everything here uses only the public Whoosh API.

Author: Priya Sundaram (maintainer of the Whoosh revival). This example was
written with the help of an AI assistant.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import DATETIME, ID, NUMERIC, TEXT, Schema
from whoosh.highlight import ContextFragmenter, HtmlFormatter, UppercaseFormatter
from whoosh.qparser import MultifieldParser
from whoosh.query import Every

DEFAULT_EXTS = (".txt", ".md", ".rst", ".py", ".cfg", ".ini", ".toml", ".json")
INDEX_DIRNAME = ".whoosh_index"


def build_schema() -> Schema:
    """Schema: a stored path/title, a stemmed full-text body, and mtime.

    ``body`` is stored so we can highlight snippets without re-reading the file.
    """
    return Schema(
        path=ID(unique=True, stored=True),
        title=TEXT(stored=True),
        body=TEXT(analyzer=StemmingAnalyzer(), stored=True),
        mtime=NUMERIC(stored=True),
    )


def iter_files(root: str, exts: tuple[str, ...]):
    """Yield (abspath, mtime) for files under *root* matching *exts*.

    Skips the index directory itself and common noise dirs.
    """
    skip = {INDEX_DIRNAME, ".git", ".hg", "__pycache__", "node_modules", ".venv"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if exts and not name.lower().endswith(exts):
                continue
            full = os.path.join(dirpath, name)
            try:
                yield full, os.path.getmtime(full)
            except OSError:
                continue


def read_text(path: str) -> str | None:
    """Read a file as UTF-8 text, skipping anything that looks binary."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(1_000_000)  # cap at 1 MB per file for the demo
    except OSError:
        return None
    if b"\x00" in raw:
        return None  # crude binary check
    return raw.decode("utf-8", errors="replace")


def open_or_create(index_dir: str) -> index.Index:
    if index.exists_in(index_dir):
        return index.open_dir(index_dir)
    os.makedirs(index_dir, exist_ok=True)
    return index.create_in(index_dir, build_schema())


def cmd_index(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.directory)
    if not os.path.isdir(root):
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    exts = tuple(e if e.startswith(".") else "." + e
                 for e in (args.ext.split(",") if args.ext else DEFAULT_EXTS))
    index_dir = os.path.join(root, INDEX_DIRNAME)

    # For a full (non-incremental) index, start clean.
    if not args.update and index.exists_in(index_dir):
        for f in os.listdir(index_dir):
            os.remove(os.path.join(index_dir, f))

    ix = open_or_create(index_dir)

    # Snapshot what's already indexed (path -> mtime) for incremental updates.
    indexed: dict[str, float] = {}
    if args.update:
        with ix.searcher() as s:
            for fields in s.search(Every(), limit=None):
                indexed[fields["path"]] = float(fields["mtime"])

    added = updated = skipped = 0
    seen: set[str] = set()
    t0 = time.time()
    writer = ix.writer()
    try:
        for full, mtime in iter_files(root, exts):
            rel = os.path.relpath(full, root)
            seen.add(rel)
            if args.update and rel in indexed and indexed[rel] >= mtime:
                skipped += 1
                continue
            text = read_text(full)
            if text is None:
                continue
            writer.update_document(
                path=rel,
                title=os.path.basename(full),
                body=text,
                mtime=mtime,
            )
            if rel in indexed:
                updated += 1
            else:
                added += 1

        # In --update mode, drop docs whose files were deleted.
        removed = 0
        if args.update:
            for gone in set(indexed) - seen:
                writer.delete_by_term("path", gone)
                removed += 1
        writer.commit()
    except Exception:
        writer.cancel()
        raise

    dt = time.time() - t0
    with ix.reader() as r:
        total = r.doc_count()
    parts = [f"{added} added"]
    if args.update:
        parts += [f"{updated} updated", f"{skipped} unchanged", f"{removed} removed"]
    print(f"Indexed {root}")
    print("  " + ", ".join(parts) + f"  ->  {total} docs total in {dt:.2f}s")
    print(f"  index stored at {index_dir}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.directory)
    index_dir = os.path.join(root, INDEX_DIRNAME)
    if not index.exists_in(index_dir):
        print(f"error: no index at {index_dir}. Run 'index' first.", file=sys.stderr)
        return 2

    ix = index.open_dir(index_dir)
    # Search title + body; title matches are weighted higher.
    parser = MultifieldParser(["title", "body"], schema=ix.schema,
                              fieldboosts={"title": 2.0, "body": 1.0})
    query = parser.parse(args.query)

    with ix.searcher() as s:
        results = s.search(query, limit=args.limit)
        if args.html:
            results.formatter = HtmlFormatter(tagname="mark")
        else:
            results.formatter = UppercaseFormatter()
        results.fragmenter = ContextFragmenter(maxchars=200, surround=40)

        n = len(results)
        if n == 0:
            print(f"No matches for: {args.query!r}")
            return 1
        print(f"{n} match{'es' if n != 1 else ''} for {args.query!r}:\n")
        for i, hit in enumerate(results, 1):
            snippet = hit.highlights("body") or (hit["body"][:160] + "...")
            snippet = " ".join(snippet.split())  # collapse whitespace
            print(f"{i}. {hit['path']}  (score {hit.score:.2f})")
            print(f"   {snippet}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Full-text search a folder of files, powered by Whoosh.")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("index", help="build/refresh the search index")
    pi.add_argument("directory", nargs="?", default=".",
                    help="directory to index (default: current)")
    pi.add_argument("--update", action="store_true",
                    help="incremental: only (re)index changed/new files, drop deleted")
    pi.add_argument("--ext", default="",
                    help="comma-separated extensions to include (default: common text/source)")
    pi.set_defaults(func=cmd_index)

    ps = sub.add_parser("search", help="query the index")
    ps.add_argument("query", help='search query (supports AND/OR/NOT, "phrases", field:term)')
    ps.add_argument("directory", nargs="?", default=".",
                    help="directory whose index to search (default: current)")
    ps.add_argument("--limit", type=int, default=10, help="max results (default: 10)")
    ps.add_argument("--html", action="store_true",
                    help="emit <mark>...</mark> HTML highlights instead of UPPERCASE")
    ps.set_defaults(func=cmd_search)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
