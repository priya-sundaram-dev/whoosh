"""FastAPI + Whoosh: a small, production-shaped full-text search API.

This example wires Whoosh (pure-Python full-text search) into a FastAPI app.
It shows the pattern you actually need in a real service:

* a persistent on-disk index (survives restarts),
* create / update / delete documents over a REST API,
* a search endpoint with pagination, BM25F relevance ranking, and
  highlighted snippets,
* clean startup/shutdown so the index files are released (important on
  Windows, where open file handles block deletes).

The search logic lives in a small, dependency-free ``SearchIndex`` class so it
is easy to unit-test without spinning up an HTTP server. The FastAPI layer on
top is deliberately thin.

Run it
-------
    pip install "whoosh3" fastapi "uvicorn[standard]"
    uvicorn fastapi_app:app --reload

Then, in another terminal::

    # add / update a document (idempotent upsert by id)
    curl -X PUT localhost:8000/documents/1 \
        -H 'content-type: application/json' \
        -d '{"title": "Getting started with Whoosh", "body": "pure-python search"}'

    # search with pagination + highlights
    curl 'localhost:8000/search?q=python&page=1&page_size=10'

    # delete
    curl -X DELETE localhost:8000/documents/1

Interactive docs are served at http://localhost:8000/docs

Whoosh is BSD-licensed. This example targets whoosh3 >= 3.1.0.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager

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
    """

    def __init__(self, index_dir: str = INDEX_DIR) -> None:
        self.index_dir = index_dir
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
        writer = self.ix.writer()
        try:
            writer.update_document(id=doc_id, title=title, body=body)
            writer.commit()
        except Exception:
            writer.cancel()
            raise

    def delete(self, doc_id: str) -> int:
        """Delete by id. Returns the number of documents removed (0 or 1)."""
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
            "results": hits,
        }


# --------------------------------------------------------------------------
# The FastAPI layer (thin). Import errors here are expected if FastAPI/
# Pydantic aren't installed; the SearchIndex class above works on its own.
# --------------------------------------------------------------------------

try:
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - lets the module import without FastAPI
    FastAPI = None  # type: ignore[assignment]


if FastAPI is not None:

    class DocumentIn(BaseModel):
        title: str
        body: str

    # Hold the index on the app so it's created once at startup and closed
    # cleanly at shutdown (releases file handles — matters on Windows).
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.index = SearchIndex()
        try:
            yield
        finally:
            app.state.index.close()

    app = FastAPI(
        title="Whoosh Search API",
        description="A minimal full-text search API powered by whoosh3.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.put("/documents/{doc_id}", status_code=204)
    def put_document(doc_id: str, doc: DocumentIn) -> None:
        """Create or replace a document (idempotent upsert by id)."""
        app.state.index.upsert(doc_id, doc.title, doc.body)

    @app.delete("/documents/{doc_id}")
    def delete_document(doc_id: str) -> dict:
        """Delete a document by id."""
        removed = app.state.index.delete(doc_id)
        if removed == 0:
            raise HTTPException(status_code=404, detail="document not found")
        return {"deleted": removed}

    @app.get("/search")
    def search(
        q: str = Query(..., min_length=1, description="Search query"),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
    ) -> dict:
        """Full-text search with pagination and highlighted snippets."""
        return app.state.index.search(q, page=page, page_size=page_size)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}


# --------------------------------------------------------------------------
# A tiny self-test of the search layer (no HTTP server needed).
# Run:  python fastapi_app.py
# --------------------------------------------------------------------------

def _demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        idx = SearchIndex(index_dir=tmp)
        try:
            idx.upsert("1", "Getting started with Whoosh", "pure-python search library")
            idx.upsert("2", "FastAPI tutorial", "build python APIs quickly")
            # Upsert is idempotent: replacing id=1 does not duplicate it.
            idx.upsert("1", "Getting started with Whoosh", "pure-python full-text search")

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
