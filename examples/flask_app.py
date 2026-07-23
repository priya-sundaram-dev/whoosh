"""Flask + Whoosh: a small, production-shaped full-text search web app.

This example wires Whoosh (pure-Python full-text search) into a Flask app.
It shows the pattern you actually need in a real service:

* a persistent on-disk index (survives restarts),
* create / update / delete documents over a small JSON API,
* a search endpoint with pagination, BM25F relevance ranking, and
  highlighted snippets,
* correct concurrency: one writer at a time, a fresh short-lived searcher
  per request (searchers are cheap and must not be shared across threads).

The search logic lives in a small, framework-free ``SearchIndex`` class so it
is easy to unit-test without spinning up an HTTP server. The Flask layer on
top is deliberately thin, and mirrors ``examples/fastapi_app.py`` so you can
compare the two frameworks side by side.

Run it
-------
    pip install "whoosh3" flask
    flask --app flask_app run --debug

Then, in another terminal::

    # add / update a document (idempotent upsert by id)
    curl -X PUT localhost:5000/documents/1 \
        -H 'content-type: application/json' \
        -d '{"title": "Getting started with Whoosh", "body": "pure-python search"}'

    # search with pagination + highlights
    curl 'localhost:5000/search?q=python&page=1&page_size=10'

    # delete
    curl -X DELETE localhost:5000/documents/1

Concurrency note
----------------
Whoosh indexes allow one writer at a time but many concurrent readers. This
example serialises writes behind a lock and opens a fresh ``searcher()`` per
request. For write-heavy apps, funnel writes through a single background
thread or use :class:`whoosh.writing.AsyncWriter`.

Whoosh is BSD-licensed. This example targets whoosh3 >= 3.1.0.
"""

from __future__ import annotations

import os
import tempfile
import threading

from whoosh import index
from whoosh.fields import ID, TEXT, Schema
from whoosh.highlight import ContextFragmenter, HtmlFormatter
from whoosh.qparser import MultifieldParser

# --------------------------------------------------------------------------
# The search layer (no web framework here — just Whoosh).
# --------------------------------------------------------------------------

#: Where the index lives on disk. Override with WHOOSH_INDEX_DIR.
INDEX_DIR = os.environ.get("WHOOSH_INDEX_DIR", "indexdir")


def build_schema() -> Schema:
    """Schema for our documents.

    ``id`` is a unique key so we can upsert/delete by it. ``title`` gets a
    field boost so title matches rank above body matches.
    """
    return Schema(
        id=ID(unique=True, stored=True),
        title=TEXT(stored=True, field_boost=2.0),
        body=TEXT(stored=True),
    )


class SearchIndex:
    """A tiny wrapper around a Whoosh index with upsert/delete/search.

    Kept free of any web-framework imports so it is trivial to unit test.
    Writes are serialised behind a lock because a Whoosh index permits only
    one writer at a time; reads open a fresh, short-lived searcher.
    """

    def __init__(self, index_dir: str = INDEX_DIR) -> None:
        self.index_dir = index_dir
        self._write_lock = threading.Lock()
        if index.exists_in(index_dir):
            self.ix = index.open_dir(index_dir)
        else:
            os.makedirs(index_dir, exist_ok=True)
            self.ix = index.create_in(index_dir, build_schema())
        # A parser that searches both fields at once.
        self.parser = MultifieldParser(["title", "body"], schema=self.ix.schema)
        # <mark class="hit"> ... </mark> snippets, ~2 short fragments each.
        self.formatter = HtmlFormatter(tagname="mark", classname="hit")
        self.fragmenter = ContextFragmenter(maxchars=200, surround=40)

    def close(self) -> None:
        """Release the index (and its file handles)."""
        self.ix.close()

    def upsert(self, doc_id: str, title: str, body: str) -> None:
        """Insert or replace the document with this id.

        ``update_document`` deletes any existing doc with the same unique
        ``id`` and adds the new one, so PUT is naturally idempotent.
        """
        with self._write_lock:
            writer = self.ix.writer()
            try:
                writer.update_document(id=doc_id, title=title, body=body)
                writer.commit()
            except Exception:
                writer.cancel()
                raise

    def delete(self, doc_id: str) -> int:
        """Delete by id. Returns the number of documents removed (0 or 1)."""
        with self._write_lock:
            writer = self.ix.writer()
            try:
                n = writer.delete_by_term("id", doc_id)
                writer.commit()
                return n
            except Exception:
                writer.cancel()
                raise

    def search(self, q: str, page: int = 1, page_size: int = 10) -> dict:
        """Run a query and return a JSON-friendly page of results.

        Uses BM25F ranking (Whoosh's default) and returns highlighted body
        snippets so you can render "…matching **text**…" in a UI.
        """
        page = max(page, 1)
        page_size = max(1, min(page_size, 100))
        with self.ix.searcher() as searcher:
            query = self.parser.parse(q)
            results = searcher.search_page(query, page, pagelen=page_size)
            results.results.fragmenter = self.fragmenter
            results.results.formatter = self.formatter
            hits = [
                {
                    "id": hit["id"],
                    "title": hit["title"],
                    "score": round(hit.score, 4),
                    "snippet": hit.highlights("body", top=2),
                }
                for hit in results
            ]
        return {
            "query": q,
            "page": page,
            "page_size": page_size,
            "total": results.total,
            "pages": results.pagecount,
            "results": hits,
        }


# --------------------------------------------------------------------------
# The Flask layer (thin). Import errors here are expected if Flask isn't
# installed; the SearchIndex class above works on its own.
# --------------------------------------------------------------------------

try:
    from flask import Flask, jsonify, request
except ImportError:  # pragma: no cover - lets the module import without Flask
    Flask = None  # type: ignore[assignment]


def create_app(index_dir: str = INDEX_DIR) -> Flask:
    """Application factory. Builds the index once and wires the routes.

    Using a factory (rather than a module-level ``app``) plays nicely with
    testing and with ``flask --app flask_app run``.
    """
    if Flask is None:  # pragma: no cover
        raise RuntimeError("Flask is not installed: pip install flask")

    app = Flask(__name__)
    app.config["search_index"] = SearchIndex(index_dir)

    @app.put("/documents/<doc_id>")
    def put_document(doc_id: str):
        """Create or replace a document (idempotent upsert by id)."""
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        body = data.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            return jsonify(error="title and body (strings) are required"), 400
        app.config["search_index"].upsert(doc_id, title, body)
        return "", 204

    @app.delete("/documents/<doc_id>")
    def delete_document(doc_id: str):
        """Delete a document by id."""
        removed = app.config["search_index"].delete(doc_id)
        if removed == 0:
            return jsonify(error="document not found"), 404
        return jsonify(deleted=removed)

    @app.get("/search")
    def search():
        """Full-text search with pagination and highlighted snippets."""
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify(error="query parameter 'q' is required"), 400
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))
        except ValueError:
            return jsonify(error="page and page_size must be integers"), 400
        return jsonify(app.config["search_index"].search(q, page, page_size))

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app


# ``flask --app flask_app run`` looks for a module-level ``app`` (or calls
# ``create_app``). We expose ``app`` when Flask is importable.
if Flask is not None:
    app = create_app()


# --------------------------------------------------------------------------
# A tiny self-test of the search layer (no HTTP server needed).
# Run:  python flask_app.py
# --------------------------------------------------------------------------


def _demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        idx = SearchIndex(index_dir=tmp)
        try:
            idx.upsert("1", "Getting started with Whoosh", "pure-python search library")
            idx.upsert("2", "Flask tutorial", "build python web apps quickly")
            # Upsert is idempotent: replacing id=1 does not duplicate it.
            idx.upsert(
                "1", "Getting started with Whoosh", "pure-python full-text search"
            )

            out = idx.search("python", page=1, page_size=10)
            print(f"query={out['query']!r} total={out['total']}")
            for r in out["results"]:
                print(f"  {r['id']}  score={r['score']}  {r['title']!r}")
                print(f"      snippet: {r['snippet']}")

            removed = idx.delete("2")
            print(f"deleted id=2 -> {removed} doc removed")
            out = idx.search("python", page=1, page_size=10)
            print(f"after delete: total={out['total']}")
        finally:
            idx.close()


if __name__ == "__main__":
    _demo()
