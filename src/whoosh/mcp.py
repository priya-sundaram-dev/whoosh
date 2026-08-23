"""Serve a Whoosh full-text index to AI agents over the Model Context Protocol.

The Model Context Protocol (MCP) is an open standard that lets AI agents
(Claude Desktop, IDE assistants, and custom agent loops) call tools over a
uniform interface. Because Whoosh is pure Python and stores a real BM25F index
as a plain directory of files, it makes an excellent *local, no-server,
no-native-dependency* search backend for an agent's ``search`` and ``fetch``
tools.

This module ships with the ``whoosh3`` package and backs the ``whoosh-mcp``
console script. Install the optional MCP dependency and run it against a folder
of your own documents::

    pip install "whoosh3[mcp]"
    whoosh-mcp ~/notes            # stdio transport, ready for an MCP client

With no path it serves a few built-in sample documents so you can try it
immediately. Point an MCP client at it, e.g. in Claude Desktop's config::

    {
      "mcpServers": {
        "whoosh": { "command": "whoosh-mcp", "args": ["/path/to/your/docs"] }
      }
    }

The search core (:class:`SearchCore`) has **no** MCP dependency, so you can
import and unit-test it directly, or reuse it behind any agent framework
(LangChain / LlamaIndex tools, OpenAI function calling, or a plain function)::

    from whoosh.mcp import SearchCore
    core = SearchCore.from_directory("~/notes")
    core.search("full text search")   # -> [{id, title, score, snippet}, ...]

Two tools are exposed, following the common connector convention::

    search(query, limit) -> list of {id, title, score, snippet}
    fetch(id)            -> full document text for a given id
"""

from __future__ import annotations

import argparse
import os.path
import sys
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from whoosh import highlight
from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import MultifieldParser

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids importing the SDK
    from collections.abc import Sequence

    from mcp.server import MCPServer

__all__ = ["SearchCore", "build_mcp_server", "main", "DEFAULT_EXTS", "SAMPLE_DOCS"]

DEFAULT_EXTS: tuple[str, ...] = (".md", ".txt", ".rst")

#: A handful of sample documents used when no corpus directory is supplied.
SAMPLE_DOCS: list[dict[str, str]] = [
    {
        "id": "py-gil",
        "title": "The Python GIL",
        "body": "The global interpreter lock serializes bytecode execution so only "
        "one thread runs Python at a time. CPython 3.13 ships an experimental "
        "free-threaded build that can disable the GIL.",
    },
    {
        "id": "bm25",
        "title": "BM25 ranking",
        "body": "BM25 is a probabilistic ranking function that scores documents by "
        "term frequency and inverse document frequency with length "
        "normalization. Whoosh uses BM25F by default.",
    },
    {
        "id": "mcp",
        "title": "Model Context Protocol",
        "body": "MCP is an open protocol that standardizes how applications provide "
        "context and tools to large language models. Servers expose tools "
        "like search and fetch that an agent can call.",
    },
    {
        "id": "embedded",
        "title": "Embedded search engines",
        "body": "An embedded search engine runs inside your process instead of a "
        "separate server. Whoosh stores its index as a directory of files, "
        "so it deploys anywhere CPython runs, including serverless and CI.",
    },
]


@dataclass
class SearchCore:
    """A reusable Whoosh-backed search core with no MCP/agent dependency."""

    index_dir: str

    @classmethod
    def build(
        cls,
        docs: Sequence[dict[str, str]] = SAMPLE_DOCS,
        index_dir: str | None = None,
    ) -> SearchCore:
        """Build an index from an iterable of ``{id, title, body}`` dicts."""
        index_dir = index_dir or tempfile.mkdtemp(prefix="whoosh_mcp_")
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
        schema = Schema(
            id=ID(stored=True, unique=True),
            title=TEXT(stored=True),
            body=TEXT(stored=True),
        )
        ix = create_in(index_dir, schema)
        writer = ix.writer()
        for d in docs:
            writer.update_document(id=d["id"], title=d["title"], body=d["body"])
        writer.commit()
        return cls(index_dir=index_dir)

    @classmethod
    def from_directory(
        cls,
        corpus_dir: str,
        index_dir: str | None = None,
        exts: Sequence[str] = DEFAULT_EXTS,
    ) -> SearchCore:
        """Build a search core over a real directory of text/markdown files.

        Each file becomes one document: ``id`` is its path relative to
        ``corpus_dir``, ``title`` is the first non-empty line (or the filename),
        and ``body`` is the full file text. Point an agent at your own notes,
        docs, or wiki with ``SearchCore.from_directory("~/notes")``.
        """
        corpus_dir = os.path.abspath(os.path.expanduser(corpus_dir))
        docs: list[dict[str, str]] = []
        for root, _dirs, files in os.walk(corpus_dir):
            for name in sorted(files):
                if exts and not name.lower().endswith(tuple(exts)):
                    continue
                path = os.path.join(root, name)
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        text = fh.read()
                except OSError:
                    continue
                rel = os.path.relpath(path, corpus_dir)
                title = next(
                    (
                        ln.strip().lstrip("#").strip()
                        for ln in text.splitlines()
                        if ln.strip()
                    ),
                    name,
                )
                docs.append({"id": rel, "title": title, "body": text})
        if not docs:
            raise ValueError(
                f"No indexable files ({', '.join(exts)}) found under {corpus_dir!r}"
            )
        return cls.build(docs=docs, index_dir=index_dir)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Full-text search. Returns ranked ``{id, title, score, snippet}`` dicts."""
        ix = open_dir(self.index_dir)
        parser = MultifieldParser(["title", "body"], schema=ix.schema)
        q = parser.parse(query)
        out: list[dict[str, Any]] = []
        with ix.searcher() as searcher:
            results = searcher.search(q, limit=limit)
            results.fragmenter = highlight.ContextFragmenter(maxchars=160, surround=40)
            results.formatter = highlight.UppercaseFormatter()
            out.extend(
                {
                    "id": hit["id"],
                    "title": hit["title"],
                    "score": round(hit.score, 4),
                    "snippet": hit.highlights("body") or hit["body"][:160],
                }
                for hit in results
            )
        return out

    def fetch(self, doc_id: str) -> dict[str, Any]:
        """Fetch the full text of a document by its ``id`` (as returned by search)."""
        ix = open_dir(self.index_dir)
        with ix.searcher() as searcher:
            hit = searcher.document(id=doc_id)
            if hit is None:
                return {"id": doc_id, "error": "not found"}
            return {"id": hit["id"], "title": hit["title"], "text": hit["body"]}


def build_mcp_server(core: SearchCore | None = None) -> MCPServer:
    """Wrap a :class:`SearchCore` in an MCPServer exposing ``search`` + ``fetch``.

    Requires the official MCP SDK (``pip install "whoosh3[mcp]"``). If ``core``
    is ``None``, a corpus directory named in ``WHOOSH_MCP_CORPUS`` is indexed,
    otherwise the built-in sample documents are used.
    """
    try:
        from mcp.server import MCPServer  # noqa: PLC0415
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dep
        raise ModuleNotFoundError(
            "The MCP server requires the 'mcp' package. "
            'Install it with:  pip install "whoosh3[mcp]"'
        ) from exc

    if core is None:
        corpus = os.environ.get("WHOOSH_MCP_CORPUS")
        core = SearchCore.from_directory(corpus) if corpus else SearchCore.build()
    server = MCPServer("whoosh-search")

    @server.tool()
    def search(query: str, limit: int = 5) -> list[dict]:
        """Full-text search the local corpus. Returns ranked {id, title, score, snippet}."""
        return core.search(query, limit)

    @server.tool()
    def fetch(id: str) -> dict:
        """Fetch the full text of a document by its id (as returned by search)."""
        return core.fetch(id)

    return server


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``whoosh-mcp`` console script.

    Runs an MCP server over stdio, ready to be spawned by an MCP client. A
    positional ``corpus`` directory (or the ``WHOOSH_MCP_CORPUS`` environment
    variable) selects the documents to serve; with neither, built-in samples
    are used.
    """
    parser = argparse.ArgumentParser(
        prog="whoosh-mcp",
        description="Serve a Whoosh full-text index to AI agents over MCP (stdio).",
    )
    parser.add_argument(
        "corpus",
        nargs="?",
        default=os.environ.get("WHOOSH_MCP_CORPUS"),
        help="Directory of .md/.txt/.rst files to index "
        "(default: WHOOSH_MCP_CORPUS, else built-in samples).",
    )
    args = parser.parse_args(argv)

    if args.corpus:
        try:
            core = SearchCore.from_directory(args.corpus)
        except ValueError as exc:
            print(f"whoosh-mcp: {exc}", file=sys.stderr)
            return 2
    else:
        core = SearchCore.build()

    try:
        server = build_mcp_server(core)
    except ModuleNotFoundError as exc:
        # The optional MCP SDK is missing. Show a clean, actionable message
        # instead of a confusing chained traceback.
        print(f"whoosh-mcp: {exc}", file=sys.stderr)
        return 1

    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
