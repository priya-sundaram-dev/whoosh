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

    # Exclude specific files and directories
    whoosh index . --exclude "build/*" --exclude "*.min.js"

    # Inspect an index (doc count, fields, size on disk)
    whoosh stats .

Everything here uses only the public Whoosh API, so the same code doubles as
a worked example you can copy into your own project and adapt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import PurePath
from typing import TYPE_CHECKING

from whoosh import __version_str__, index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, NUMERIC, TEXT, Schema
from whoosh.highlight import ContextFragmenter, HtmlFormatter, UppercaseFormatter
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.query import Every

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main", "build_parser"]

DEFAULT_EXTS: tuple[str, ...] = (
    ".txt", ".md", ".rst", ".py", ".cfg", ".ini", ".toml", ".json",
)
INDEX_DIRNAME = ".whoosh_index"
MAX_FILE_BYTES = 5_000_000  # skip anything larger; keeps indexing snappy
_SIZE_RE = re.compile(r"^\s*(\d+)\s*([kmg]?)b?\s*$", re.IGNORECASE)
_SIZE_MULTIPLIERS = {"": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}

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


def iter_files(root: str, exts: tuple[str, ...], exclude: tuple[str, ...] = (),
                max_size: int | None = None):
    """Yield ``(abspath, mtime)`` for files under *root* matching *exts*.

    Skips the index directory itself and common noise directories. Files
    larger than *max_size* bytes are skipped as well, if given.
    """
    skip = {INDEX_DIRNAME, ".git", ".hg", "__pycache__", "node_modules", ".venv"}
    for dirpath, dirnames, filenames in os.walk(root):
        new_dirnames = []
        for d in dirnames:
            if d in skip:
                continue
            rel_d = os.path.relpath(os.path.join(dirpath, d), root)
            if any(PurePath(rel_d).match(pat) for pat in exclude):
                continue
            new_dirnames.append(d)
        dirnames[:] = new_dirnames

        for name in filenames:
            if exts and not name.lower().endswith(exts):
                continue
            full = os.path.join(dirpath, name)
            rel_f = os.path.relpath(full, root)
            if any(PurePath(rel_f).match(pat) for pat in exclude):
                continue
            if max_size is not None:
                try:
                    if os.path.getsize(full) > max_size:
                        continue
                except OSError:
                    continue
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

    # --dry-run: preview which files WOULD be indexed under the current
    # --ext/--exclude filters, then exit WITHOUT creating, clearing, or
    # writing the index. Done here, before any index dir is touched, so a
    # dry run never mutates .whoosh_index. Reuses iter_files so the previewed
    # set exactly matches a real run.
    if args.dry_run:
        rels = sorted(
            os.path.relpath(full, root)
            for full, _mtime in iter_files(root, exts, exclude=tuple(args.exclude),
                                            max_size=args.max_size)
        )
        for rel in rels:
            print(rel)
        n = len(rels)
        print(f"Would index {n} file{'s' if n != 1 else ''} under {root}",
              file=sys.stderr)
        return 0

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
        for full, mtime in iter_files(root, exts, exclude=tuple(args.exclude),
                                        max_size=args.max_size):
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
    search_fields = args.field or ["title", "body"]
    for field in search_fields:
        if field not in ix.schema.names():
            print(
                f"whoosh search: error: unknown field {field!r}. "
                f"Valid fields: {', '.join(ix.schema.names())}",
                file=sys.stderr,
            )
            return 2

    # --or: match documents containing ANY query term (broader recall).
    # OrGroup.factory(0.9) applies a small coordination bonus so documents
    # matching more of the terms still rank higher.
    group = OrGroup.factory(0.9) if getattr(args, "or_", False) else None
    if args.field:
        parser = MultifieldParser(search_fields, schema=ix.schema, group=group) \
            if group is not None \
            else MultifieldParser(search_fields, schema=ix.schema)
    else:
        # Preserve the existing title/body weighting when no fields are selected.
        boosts = {"title": 2.0, "body": 1.0}
        parser = MultifieldParser(search_fields, schema=ix.schema,
                                  fieldboosts=boosts, group=group) \
            if group is not None \
            else MultifieldParser(search_fields, schema=ix.schema,
                                  fieldboosts=boosts)
    query = parser.parse(args.query)

    with ix.searcher() as s:
        # If just counting, ignore limit to give the true total.
        if getattr(args, "count", False):
            results = s.search(query, limit=None)
            print(len(results))
            return 0

        search_kwargs = {}
        if getattr(args, "sort_by", "score") == "mtime":
            search_kwargs.update(sortedby="mtime", reverse=True)
        results = s.search_page(
            query, args.page, pagelen=args.limit, **search_kwargs)

        # ResultsPage clamps an oversized page number to the last available
        # page. The CLI should instead treat it like an empty search so users
        # do not accidentally see the same final page for every larger value.
        if results.total and args.page > results.pagecount:
            if getattr(args, "json", False):
                print(json.dumps([]))
            elif not getattr(args, "jsonl", False):
                print(f"No matches for: {args.query!r}")
            return 1

        snippet_chars = getattr(args, "snippet_chars", 200)
        no_highlight = getattr(args, "no_highlight", False)
        highlight_results = results.results
        if args.html:
            highlight_results.formatter = HtmlFormatter(tagname="mark")
        else:
            highlight_results.formatter = UppercaseFormatter()
        highlight_results.fragmenter = ContextFragmenter(
            maxchars=snippet_chars, surround=snippet_chars // 5)

        def make_snippet(hit):
            """Return a display snippet for ``hit`` honoring the output flags.

            With ``--no-highlight`` (or when the highlighter finds nothing to
            fragment) fall back to a plain, whitespace-collapsed leading slice
            of the stored body so output stays readable and grep-friendly.
            """
            body = hit["body"] if "body" in hit else ""
            if no_highlight:
                text = " ".join(body.split())
                if len(text) > snippet_chars:
                    text = text[:snippet_chars].rstrip() + "..."
                return text
            snippet = hit.highlights("body")
            if not snippet:
                text = " ".join(body.split())
                snippet = text[:snippet_chars] + ("..." if len(text) > snippet_chars else "")
            return " ".join(snippet.split())

        fields_to_show = None
        if getattr(args, "fields", None):
            fields_to_show = [f.strip() for f in args.fields.split(",") if f.strip()]
            for f in fields_to_show:
                if f not in ix.schema.names():
                    print(f"whoosh search: error: unknown field {f!r}. Valid fields: {', '.join(ix.schema.names())}", file=sys.stderr)
                    return 2

        def make_hit_dict(hit):
            if fields_to_show:
                return {f: hit[f] for f in fields_to_show if f in hit}
            hit_dict = {
                "path": hit["path"],
                "score": hit.score,
                "snippet": make_snippet(hit)
            }
            if "title" in hit and hit["title"]:
                hit_dict["title"] = hit["title"]
            return hit_dict

        json_output = getattr(args, "json", False)
        jsonl_output = getattr(args, "jsonl", False)
        n = len(results)
        if n == 0:
            if json_output:
                print(json.dumps([]))
            elif not jsonl_output:
                print(f"No matches for: {args.query!r}")
            return 1

        if json_output or jsonl_output:
            json_results = []
            for hit in results:
                hit_dict = make_hit_dict(hit)
                if jsonl_output:
                    print(json.dumps(hit_dict))
                else:
                    json_results.append(hit_dict)
            if json_output:
                print(json.dumps(json_results))
            return 0

        print(f"{n} match{'es' if n != 1 else ''} for {args.query!r}:\n")
        shown = 0
        for i, hit in enumerate(results, results.offset + 1):
            shown += 1
            if fields_to_show:
                fields_str = ", ".join(f"{f}: {hit[f]}" for f in fields_to_show if f in hit)
                print(f"{i}. {fields_str}\n")
            else:
                print(f"{i}. {hit['path']}  (score {hit.score:.2f})")
                print(f"   {make_snippet(hit)}\n")

        if getattr(args, "count", False) or getattr(args, "json", False) or getattr(args, "html", False):
            pass
        else:
            if args.page > 1:
                print(
                    f"Page {results.pagenum}/{results.pagecount} "
                    f"({results.total} total).",
                    file=sys.stderr,
                )
            elif n > shown:
                print(f"Showing {shown} of {n} matches.", file=sys.stderr)
            else:
                print(f"{n} match{'es' if n != 1 else ''}.", file=sys.stderr)
    return 0


def _human_bytes(n: int) -> str:
    """Render a byte count as a short human-readable string."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def cmd_stats(args: argparse.Namespace) -> int:
    """Print a summary of an existing index: doc count, fields, size on disk.

    With ``--top-terms FIELD`` also prints the ``--top`` most frequent terms
    indexed in FIELD. The term listing is human-readable output only; the
    ``--json`` payload is intentionally unchanged (gh#24).
    """
    root = os.path.abspath(args.directory)
    index_dir = os.path.join(root, INDEX_DIRNAME)
    if not index.exists_in(index_dir):
        print(f"error: no index at {index_dir}. Run 'whoosh index' first.",
              file=sys.stderr)
        return 2

    ix = index.open_dir(index_dir)
    with ix.reader() as r:
        doc_count = r.doc_count()
        doc_count_all = r.doc_count_all()

    schema = ix.schema
    fields = [(name, type(schema[name]).__name__) for name in schema.names()]

    # Size on disk: sum of all files in the index directory.
    total_bytes = 0
    file_count = 0
    latest_mtime = 0.0
    for name in os.listdir(index_dir):
        fp = os.path.join(index_dir, name)
        try:
            st = os.stat(fp)
        except OSError:
            continue
        if os.path.isfile(fp):
            total_bytes += st.st_size
            file_count += 1
            latest_mtime = max(latest_mtime, st.st_mtime)

    if getattr(args, "json", False):
        payload = {
            "index_dir": index_dir,
            "doc_count": doc_count,
            "doc_count_all": doc_count_all,
            "fields": [{"name": n, "type": t} for n, t in fields],
            "size_bytes": total_bytes,
            "index_files": file_count,
            "last_modified": latest_mtime or None,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Index: {index_dir}")
    print(f"  documents:   {doc_count}"
          + (f"  ({doc_count_all} incl. deleted)" if doc_count_all != doc_count else ""))
    print(f"  fields:      {len(fields)}")
    for name, ftype in fields:
        print(f"    - {name} ({ftype})")
    print(f"  size on disk: {_human_bytes(total_bytes)}  ({file_count} files)")
    if latest_mtime:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest_mtime))
        print(f"  last updated: {stamp}")

    if getattr(args, "top_terms", None):
        fieldname = args.top_terms
        if fieldname not in schema.names():
            print(f"error: no field {fieldname!r} in index", file=sys.stderr)
            return 2
        field = schema[fieldname]
        # NUMERIC (and DATETIME, which subclasses it) store terms in an
        # encoded binary form that has no meaningful text representation or
        # frequency ranking, so "top terms" does not apply to them. Detect
        # this up front and give a clear, actionable message instead of
        # surfacing a low-level decoding error.
        from whoosh.fields import NUMERIC as _NUMERIC
        if isinstance(field, _NUMERIC):
            ftype = type(field).__name__
            print(
                f"error: field {fieldname!r} ({ftype}) does not store text "
                f"terms, so it has no top terms to list; try a TEXT field",
                file=sys.stderr,
            )
            return 2
        try:
            with ix.reader() as r:
                top_terms = r.most_frequent_terms(fieldname, number=args.top)
        except Exception as exc:  # noqa: BLE001
            # Any remaining edge case: show a clear message, not a traceback.
            print(f"error: cannot list top terms for field {fieldname!r}: {exc}",
                  file=sys.stderr)
            return 2
        print(f"Top terms in {fieldname!r}:")
        for freq, term in top_terms:
            text = term.decode("utf-8", "replace")
            print(f"  {int(freq)}  {text}")
    return 0


def _check_positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"invalid positive int value: '{value}'")
    return ivalue


def _parse_size(value):
    match = _SIZE_RE.match(value)
    if not match:
        raise argparse.ArgumentTypeError(f"invalid size {value!r}: expected e.g. 1024, 500k, 10MB, 2g")
    number, unit = match.groups()
    multiplier = _SIZE_MULTIPLIERS[unit.lower()]
    return int(number) * multiplier


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whoosh",
        description="Full-text search a folder of files, powered by Whoosh "
                    "(pure-Python, no server).",
        epilog="Docs, examples, and source: "
               "https://github.com/priya-sundaram-dev/whoosh",
    )
    p.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version_str__} "
                "(https://github.com/priya-sundaram-dev/whoosh)",
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
    pi.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                    help="exclude paths matching the given glob pattern "
                         "(e.g., 'build/*' or '*.min.js'). Can be specified multiple times.")
    pi.add_argument("--max-size", type=_parse_size, default=None,
                    dest="max_size", metavar="SIZE",
                    help="skip files larger than SIZE (e.g. 10MB, 500k); "
                     "no limit by default")
    pi.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="list the files that would be indexed under the "
                         "current --ext/--exclude filters and exit, without "
                         "creating, clearing, or writing the index")
    pi.set_defaults(func=cmd_index)

    ps = sub.add_parser("search", help="query the index")
    ps.add_argument("query",
                    help='search query (supports AND/OR/NOT, "phrases", '
                         'field:term)')
    ps.add_argument("directory", nargs="?", default=".",
                    help="directory whose index to search (default: current)")
    ps.add_argument("--limit", type=_check_positive_int, default=10,
                    help="max results (default: 10)")
    ps.add_argument("--page", type=_check_positive_int, default=1,
                    help="1-based results page (default: 1)")
    ps.add_argument("--fields",
                    help="comma-separated list of stored fields to include in output")
    ps.add_argument("--field", action="append", metavar="NAME",
                    help="field to search (repeatable; default: title and body)")
    ps.add_argument("--or", dest="or_", action="store_true",
                    help="match documents containing ANY query term "
                         "(default: all terms must match)")
    ps.add_argument("--snippet-chars", type=_check_positive_int, default=200,
                    metavar="N", dest="snippet_chars",
                    help="max characters of context to show per snippet "
                         "(default: 200)")
    ps.add_argument("--sort-by", choices=["score", "mtime"], default="score",
                    dest="sort_by",
                    help="sort results by relevance score (default) or "
                         "file modification time")

    # Output style/mode flags are mutually exclusive: the default UPPERCASE
    # text, HTML highlights, a plain grep-friendly slice, machine-readable
    # JSON/JSONL, or a bare count. (JSON snippets are already plain, so
    # combining --no-highlight with --json/--jsonl would be redundant.)
    group = ps.add_mutually_exclusive_group()
    group.add_argument("--html", action="store_true",
                    help="emit <mark>...</mark> HTML highlights instead of "
                         "UPPERCASE")
    group.add_argument("--no-highlight", action="store_true",
                    dest="no_highlight",
                    help="print a plain, grep-friendly leading slice of the "
                         "body with no match markup")
    group.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON output instead of "
                         "human-readable text")
    group.add_argument("--jsonl", "--ndjson", action="store_true",
                    help="emit newline-delimited JSON (one object per hit)")
    group.add_argument("--count", action="store_true",
                    help="emit only the number of matching documents")
    ps.set_defaults(func=cmd_search)

    pst = sub.add_parser("stats",
                         help="show index summary (doc count, fields, size)")
    pst.add_argument("directory", nargs="?", default=".",
                     help="directory whose index to inspect (default: current)")
    pst.add_argument("--json", action="store_true",
                     help="emit machine-readable JSON output")
    pst.add_argument("--top-terms", metavar="FIELD",
                     help="show the most frequent indexed terms in FIELD")
    pst.add_argument("--top", type=_check_positive_int, default=10,
                     help="how many top terms to show (default: 10)")
    pst.set_defaults(func=cmd_stats)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
