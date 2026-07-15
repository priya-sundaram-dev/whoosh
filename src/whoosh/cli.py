"""Command-line full-text search for a folder of files, powered by Whoosh.

This module backs the ``whoosh`` console script that ships with the
``whoosh3`` package. It lets you index a directory of text/markdown/source
files and search it from your terminal -- no server, no external service,
pure Python::

    # Index the current directory (creates ./.whoosh_index/)
    whoosh index .

    # Search it, with highlighted snippets
    whoosh search "full text search"

    # Re-index only changed files (fast; uses file mtimes)
    whoosh index . --update

    # Limit which files get indexed
    whoosh index ~/notes --ext .md,.txt,.rst

Everything here uses only the public Whoosh API, so the same code doubles as
a worked example you can copy into your own project and adapt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import TYPE_CHECKING

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, NUMERIC, TEXT, Schema
from whoosh.highlight import ContextFragmenter, HtmlFormatter, UppercaseFormatter
from whoosh.qparser import MultifieldParser
from whoosh.query import Every

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main", "build_parser"]

DEFAULT_EXTS: tuple[str, ...] = (
    ".txt", ".md", ".rst", ".py", ".cfg", ".ini", ".toml", ".json",
)
INDEX_DIRNAME = ".whoosh_index"
MAX_FILE_BYTES = 5_000_000  # skip anything larger; keeps indexing snappy


def build_schema() -> Schema:
    """Schema: a stored path/title, a stemmed full-text body, and mtime.

    ``body`` is stored so we can highlight snippets without re-reading files.
    """
    return Schema(
        path=ID(unique=True, stored=True),
        title=TEXT(stored=True),
        body=TEXT(analyzer=StemmingAnalyzer(), stored=True),
        mtime=NUMERIC(stored=True),
    )


def iter_files(root: str, exts: tuple[str, ...]):
    """Yield ``(abspath, mtime)`` for files under *root* matching *exts*.

    Skips the index directory itself and common noise directories.
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
            raw = fh.read(MAX_FILE_BYTES)
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


def _resolve_exts(raw: str) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_EXTS
    return tuple(
        (e if e.startswith(".") else "." + e).lower()
        for e in raw.split(",")
        if e.strip()
    )


def cmd_index(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.directory)
    if not os.path.isdir(root):
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    exts = _resolve_exts(args.ext)
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
        print(f"error: no index at {index_dir}. Run 'whoosh index' first.",
              file=sys.stderr)
        return 2

    ix = index.open_dir(index_dir)
    # Search title + body; title matches are weighted higher.
    parser = MultifieldParser(["title", "body"], schema=ix.schema,
                              fieldboosts={"title": 2.0, "body": 1.0})
    query = parser.parse(args.query)

    with ix.searcher() as s:
        # If just counting, ignore limit to give the true total.
        if getattr(args, "count", False):
            results = s.search(query, limit=None)
            print(len(results))
            return 0

        results = s.search(query, limit=args.limit)
        if args.html:
            results.formatter = HtmlFormatter(tagname="mark")
        else:
            results.formatter = UppercaseFormatter()
        results.fragmenter = ContextFragmenter(maxchars=200, surround=40)

        fields_to_show = None
        if getattr(args, "fields", None):
            fields_to_show = [f.strip() for f in args.fields.split(",") if f.strip()]
            for f in fields_to_show:
                if f not in ix.schema.names():
                    print(f"whoosh search: error: unknown field {f!r}. Valid fields: {', '.join(ix.schema.names())}", file=sys.stderr)
                    return 2

        n = len(results)
        if n == 0:
            if getattr(args, "json", False):
                print(json.dumps([]))
                return 1
            print(f"No matches for: {args.query!r}")
            return 1
            
        if getattr(args, "json", False):
            json_results = []
            for i, hit in enumerate(results, 1):
                if fields_to_show:
                    hit_dict = {f: hit[f] for f in fields_to_show if f in hit}
                else:
                    snippet = hit.highlights("body") or (hit["body"][:160] + "...")
                    snippet = " ".join(snippet.split())
                    hit_dict = {
                        "path": hit['path'],
                        "score": hit.score,
                        "snippet": snippet
                    }
                    if "title" in hit and hit["title"]:
                        hit_dict["title"] = hit["title"]
                json_results.append(hit_dict)
            print(json.dumps(json_results))
            return 0

        print(f"{n} match{'es' if n != 1 else ''} for {args.query!r}:\n")
        shown = 0
        for i, hit in enumerate(results, 1):
            shown += 1
            if fields_to_show:
                fields_str = ", ".join(f"{f}: {hit[f]}" for f in fields_to_show if f in hit)
                print(f"{i}. {fields_str}\n")
            else:
                snippet = hit.highlights("body") or (hit["body"][:160] + "...")
                snippet = " ".join(snippet.split())  # collapse whitespace
                print(f"{i}. {hit['path']}  (score {hit.score:.2f})")
                print(f"   {snippet}\n")
        
        if getattr(args, "count", False) or getattr(args, "json", False) or getattr(args, "html", False):
            pass
        else:
            if n > shown:
                print(f"Showing {shown} of {n} matches.", file=sys.stderr)
            else:
                print(f"{n} match{'es' if n != 1 else ''}.", file=sys.stderr)
    return 0


def _check_positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"invalid positive int value: '{value}'")
    return ivalue


def build_parser() -> argparse.ArgumentParser:
    from whoosh import __version_str__
    
    p = argparse.ArgumentParser(
        prog="whoosh",
        description="Full-text search a folder of files, powered by Whoosh "
                    "(pure-Python, no server).")
    
    # Add version flag before subparsers
    p.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version_str__}",
    )
    
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("index", help="build/refresh the search index")
    pi.add_argument("directory", nargs="?", default=".",
                    help="directory to index (default: current)")
    pi.add_argument("--update", action="store_true",
                    help="incremental: only (re)index changed/new files, "
                         "drop deleted")
    pi.add_argument("--ext", default="",
                    help="comma-separated extensions to include "
                         "(default: common text/source)")
    pi.set_defaults(func=cmd_index)

    ps = sub.add_parser("search", help="query the index")
    ps.add_argument("query",
                    help='search query (supports AND/OR/NOT, "phrases", '
                         'field:term)')
    ps.add_argument("directory", nargs="?", default=".",
                    help="directory whose index to search (default: current)")
    ps.add_argument("--limit", type=_check_positive_int, default=10,
                    help="max results (default: 10)")
    ps.add_argument("--fields",
                    help="comma-separated list of stored fields to include in output")
    
    group = ps.add_mutually_exclusive_group()
    group.add_argument("--html", action="store_true",
                    help="emit <mark>...</mark> HTML highlights instead of "
                         "UPPERCASE")
    group.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON output instead of "
                         "human-readable text")
    group.add_argument("--count", action="store_true",
                    help="emit only the number of matching documents")
    ps.set_defaults(func=cmd_search)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())