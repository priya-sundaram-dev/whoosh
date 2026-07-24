"""Django + Whoosh: portable full-text search without Postgres or Elasticsearch.

Django's built-in full-text search only works on PostgreSQL. This example
wires Whoosh (pure-Python full-text search) into a Django app so you get
relevance-ranked search with highlighted snippets on *any* database — or no
database at all — with a no-compile ``pip install``.

It shows the pattern you actually need in a real service:

* a persistent on-disk index (survives restarts),
* create / update / delete documents over a small JSON API,
* a search endpoint with pagination, BM25F relevance ranking, and
  highlighted snippets,
* correct concurrency: one writer at a time, a fresh short-lived searcher
  per request (searchers are cheap and must not be shared across threads).

The search logic lives in a small, framework-free ``SearchIndex`` class so it
is easy to unit-test without spinning up a server. The Django layer on top is
deliberately thin and mirrors ``examples/flask_app.py`` and
``examples/fastapi_app.py`` so you can compare the three frameworks side by
side. In a real project the ``SearchIndex`` typically lives in its own module
and is kept in sync with your models via ``post_save``/``post_delete`` signals
(see "Wiring it to your models" below).

Run it
------
This is a single-file Django project (settings, URLs, and views all live
here) so it runs without a full ``startproject`` layout::

    pip install "whoosh3" django
    python django_app.py runserver

Then, in another terminal::

    # add / update a document (idempotent upsert by id)
    curl -X PUT localhost:8000/documents/1 \
        -H 'content-type: application/json' \
        -d '{"title": "Getting started with Whoosh", "body": "pure-python search"}'

    # search with pagination + highlights
    curl 'localhost:8000/search?q=python&page=1&page_size=10'

    # delete
    curl -X DELETE localhost:8000/documents/1

Wiring it to your models
------------------------
In a real app you would keep the index in sync with the ORM. Register
signal handlers once (e.g. in your app's ``apps.py`` ``ready()``)::

    from django.db.models.signals import post_save, post_delete
    from django.dispatch import receiver
    from myapp.models import Article

    search_index = SearchIndex(index_dir="indexdir")

    @receiver(post_save, sender=Article)
    def _index_article(sender, instance, **kwargs):
        search_index.upsert(str(instance.pk), instance.title, instance.body)

    @receiver(post_delete, sender=Article)
    def _deindex_article(sender, instance, **kwargs):
        search_index.delete(str(instance.pk))

To (re)build the index from scratch, iterate your queryset and call
``upsert`` for each row — for example from a small management command.

Concurrency note
-----------------
Whoosh indexes allow one writer at a time but many concurrent readers. This
example serialises writes behind a lock and opens a fresh ``searcher()`` per
request. For write-heavy apps, funnel writes through a single background
thread or use :class:`whoosh.writing.AsyncWriter`.

Whoosh is BSD-licensed. This example targets whoosh3 >= 3.1.0.
"""

from __future__ import annotations

import json
import os
import sys
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
# The Django layer (thin). Import errors here are expected if Django isn't
# installed; the SearchIndex class above works on its own.
# --------------------------------------------------------------------------

try:
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from django.http import HttpResponse, JsonResponse
    from django.urls import path
    from django.views.decorators.csrf import csrf_exempt
except ImportError:  # pragma: no cover - lets the module import without Django
    settings = None  # type: ignore[assignment]


def _configure_settings() -> None:
    """Configure a minimal single-file Django project.

    A real project keeps these in ``settings.py``; we inline them so the
    example is a single runnable file. ``ROOT_URLCONF = __name__`` tells
    Django to look for ``urlpatterns`` in this very module.
    """
    if settings is None:  # pragma: no cover
        raise RuntimeError("Django is not installed: pip install django")
    if settings.configured:
        return
    settings.configure(
        DEBUG=True,
        # In production set SECRET_KEY from the environment.
        SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret"),
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        # No database needed: Whoosh owns the index. We keep the default
        # middleware minimal since this is a JSON API.
        MIDDLEWARE=[],
        INSTALLED_APPS=[],
    )


# A single, process-wide index instance shared across requests. Reads are
# concurrent; the SearchIndex serialises writes internally.
_search_index: SearchIndex | None = None


def get_search_index() -> SearchIndex:
    global _search_index
    if _search_index is None:
        _search_index = SearchIndex()
    return _search_index


if settings is not None:

    @csrf_exempt
    def document_view(request, doc_id: str):
        """Create/replace (PUT) or delete (DELETE) a document by id."""
        idx = get_search_index()
        if request.method == "PUT":
            try:
                data = json.loads(request.body or b"{}")
            except json.JSONDecodeError:
                return JsonResponse({"error": "invalid JSON body"}, status=400)
            title = data.get("title")
            body = data.get("body")
            if not isinstance(title, str) or not isinstance(body, str):
                return JsonResponse(
                    {"error": "title and body (strings) are required"}, status=400
                )
            idx.upsert(doc_id, title, body)
            return HttpResponse(status=204)
        if request.method == "DELETE":
            removed = idx.delete(doc_id)
            if removed == 0:
                return JsonResponse({"error": "document not found"}, status=404)
            return JsonResponse({"deleted": removed})
        return JsonResponse({"error": "method not allowed"}, status=405)

    def search_view(request):
        """Full-text search with pagination and highlighted snippets."""
        q = request.GET.get("q", "").strip()
        if not q:
            return JsonResponse(
                {"error": "query parameter 'q' is required"}, status=400
            )
        try:
            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", 10))
        except ValueError:
            return JsonResponse(
                {"error": "page and page_size must be integers"}, status=400
            )
        return JsonResponse(get_search_index().search(q, page, page_size))

    def health_view(request):
        return JsonResponse({"status": "ok"})

    urlpatterns = [
        path("documents/<str:doc_id>", document_view),
        path("search", search_view),
        path("health", health_view),
    ]

    # ``application`` is what a WSGI server (gunicorn/uWSGI) imports.
    def get_application():
        _configure_settings()
        return get_wsgi_application()


# --------------------------------------------------------------------------
# A tiny self-test of the search layer (no HTTP server needed).
# Run:  python django_app.py            -> runs the self-test
#       python django_app.py runserver  -> starts Django's dev server
# --------------------------------------------------------------------------


def _demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        idx = SearchIndex(index_dir=tmp)
        try:
            idx.upsert("1", "Getting started with Whoosh", "pure-python search library")
            idx.upsert("2", "Django tutorial", "build python web apps quickly")
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
    # With a Django subcommand (e.g. "runserver"), boot Django. Otherwise run
    # the framework-free self-test so the example is easy to try instantly.
    if len(sys.argv) > 1 and settings is not None:
        _configure_settings()
        from django.core.management import execute_from_command_line

        execute_from_command_line(sys.argv)
    else:
        _demo()
