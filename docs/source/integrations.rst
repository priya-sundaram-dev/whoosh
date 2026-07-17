=================================================
Adding full-text search to your Python app
=================================================

This guide shows how to add fast, pure-Python full-text search to a real
application with Whoosh — no external search server (no Elasticsearch, no Solr),
no C extensions, and no database extension to compile. Whoosh is a library you
``pip install`` and import, so the search index lives right next to your app.

If you just want the 30-second version, see :doc:`quickstart`. This page is the
practical, task-oriented walkthrough: building an index, keeping it in sync with
your data, searching it well (ranking, pagination, highlighting), and wiring it
into **Flask** and **Django**.

.. contents::
    :local:
    :depth: 2


Install
=======

::

    pip install whoosh3

Then import it as ``whoosh`` (the package name is unchanged; only the
distribution name on PyPI is ``whoosh3``)::

    import whoosh
    print(whoosh.__version__)   # (3, 16, 1) or newer


When should I use Whoosh?
=========================

Whoosh is a great fit when you want:

* **Search inside a single app / process** — a docs site, a note app, a CLI, a
  desktop tool, a small-to-medium web app.
* **Zero-ops deployment** — no server to run, monitor, or secure. The index is
  just files on disk.
* **Pure Python** — installs anywhere Python runs, including locked-down or
  offline environments where you can't compile C extensions.
* **Rich query features out of the box** — BM25F ranking, fielded queries,
  phrases, wildcards, ranges, faceting, highlighting, and spelling correction.

Reach for a dedicated search server (Elasticsearch, OpenSearch, Solr, Typesense)
when you need to search across many services, need horizontal scaling to very
large corpora, or need near-real-time distributed indexing. Whoosh shines at the
"I have some documents in one app and I want good search over them" scale, which
is most apps.


A complete, minimal example
===========================

Create a schema, add documents, and search — the whole loop::

    import os.path
    from whoosh.index import create_in, open_dir, exists_in
    from whoosh.fields import Schema, TEXT, ID
    from whoosh.qparser import MultifieldParser

    INDEX_DIR = "indexdir"

    schema = Schema(
        id=ID(stored=True, unique=True),           # your primary key
        title=TEXT(stored=True, field_boost=2.0),  # title matches count double
        body=TEXT(stored=True),
    )

    def get_index():
        """Open the index, creating it on first run."""
        if exists_in(INDEX_DIR):
            return open_dir(INDEX_DIR)
        os.makedirs(INDEX_DIR, exist_ok=True)
        return create_in(INDEX_DIR, schema)

    ix = get_index()

    writer = ix.writer()
    writer.add_document(id="1", title="Getting started",
                        body="Install Python and write your first script.")
    writer.add_document(id="2", title="Full-text search",
                        body="Whoosh is a fast pure-Python search engine.")
    writer.commit()

    with ix.searcher() as searcher:
        parser = MultifieldParser(["title", "body"], schema=ix.schema)
        query = parser.parse("python search")
        for hit in searcher.search(query, limit=10):
            print(hit["id"], hit["title"], hit.score)

Two things to notice:

* ``MultifieldParser`` lets a single query string match across ``title`` **and**
  ``body``, which is almost always what you want for a search box.
* ``field_boost=2.0`` on ``title`` means a title match ranks higher than a body
  match — a simple, effective relevance tweak.


Keeping the index in sync with your data
=========================================

Real apps change data. The key method is ``update_document``, which is an
**insert-or-replace** keyed on a field you mark ``unique=True``::

    def upsert(ix, doc):
        writer = ix.writer()
        writer.update_document(**doc)   # replaces any existing doc with same id
        writer.commit()

    def delete(ix, doc_id):
        writer = ix.writer()
        writer.delete_by_term("id", doc_id)
        writer.commit()

Because ``id`` is ``unique=True``, calling ``update_document`` with an existing
``id`` deletes the old version and adds the new one atomically on commit. This is
exactly the pattern you use to mirror rows from a database table into the index.

**Committing is relatively expensive.** If you're indexing many documents (an
initial import, a nightly re-sync), batch them into one writer and commit once::

    writer = ix.writer(limitmb=256, procs=4, multisegment=True)
    for row in rows:
        writer.update_document(id=str(row.id), title=row.title, body=row.body)
    writer.commit()

See :doc:`batch` for tuning ``limitmb``, ``procs``, and ``multisegment``.


Better search results
======================

Ranking (BM25F)
---------------

Whoosh ranks with BM25F by default — a strong, modern relevance model. You can
make it explicit or swap it out::

    from whoosh import scoring

    with ix.searcher(weighting=scoring.BM25F()) as s:
        ...

Pagination
----------

Don't slice a full result list — use ``search_page`` so Whoosh only does the
work for the page you show::

    with ix.searcher() as s:
        query = MultifieldParser(["title", "body"], ix.schema).parse("python")
        page = s.search_page(query, pagenum=1, pagelen=10)
        print(f"Page {page.pagenum} of {page.pagecount}, {page.total} hits")
        for hit in page:
            print(hit["title"])

Highlighting matched terms
--------------------------

To show "…matched **snippet**…" excerpts in your results::

    from whoosh import highlight

    with ix.searcher() as s:
        results = s.search(query, limit=10)
        results.fragmenter = highlight.ContextFragmenter(maxchars=200, surround=40)
        results.formatter = highlight.HtmlFormatter(tagname="mark")
        for hit in results:
            snippet = hit.highlights("body")   # HTML with <mark> around matches

See :doc:`highlight` for fragmenters, formatters, and performance notes.


Flask integration
==================

A minimal search endpoint. The index is opened once at startup; each request
uses a short-lived searcher (searchers are cheap to open and should not be shared
across threads)::

    from flask import Flask, request, jsonify
    from whoosh.index import open_dir
    from whoosh.qparser import MultifieldParser
    from whoosh import highlight

    app = Flask(__name__)
    ix = open_dir("indexdir")   # built ahead of time by your import script

    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        page = int(request.args.get("page", 1))
        if not q:
            return jsonify(results=[], total=0)

        with ix.searcher() as searcher:
            parser = MultifieldParser(["title", "body"], schema=ix.schema)
            query = parser.parse(q)
            results = searcher.search_page(query, page, pagelen=10)
            results.results.fragmenter = highlight.ContextFragmenter(maxchars=200)
            results.results.formatter = highlight.HtmlFormatter(tagname="mark")
            hits = [
                {"id": h["id"], "title": h["title"],
                 "snippet": h.highlights("body"), "score": h.score}
                for h in results
            ]
        return jsonify(results=hits, total=results.total, pages=results.pagecount)

**Concurrency note:** Whoosh indexes support one writer at a time but many
concurrent readers. Open a fresh ``searcher()`` per request (as above) rather
than sharing one across threads. For write-heavy apps, funnel writes through a
single background thread or use :class:`~whoosh.writing.AsyncWriter`.


Django integration
===================

For Django, keep indexing logic in a service module and trigger updates from
model signals so the index tracks your database automatically::

    # search_index.py
    import os.path
    from whoosh.index import create_in, open_dir, exists_in
    from whoosh.fields import Schema, TEXT, ID
    from whoosh.qparser import MultifieldParser

    INDEX_DIR = "search_index"
    schema = Schema(id=ID(stored=True, unique=True),
                    title=TEXT(stored=True, field_boost=2.0),
                    body=TEXT(stored=True))

    def get_index():
        if exists_in(INDEX_DIR):
            return open_dir(INDEX_DIR)
        os.makedirs(INDEX_DIR, exist_ok=True)
        return create_in(INDEX_DIR, schema)

    def index_article(article):
        ix = get_index()
        w = ix.writer()
        w.update_document(id=str(article.pk), title=article.title, body=article.body)
        w.commit()

    def unindex_article(pk):
        ix = get_index()
        w = ix.writer()
        w.delete_by_term("id", str(pk))
        w.commit()

    def search(q, page=1, pagelen=10):
        ix = get_index()
        with ix.searcher() as s:
            query = MultifieldParser(["title", "body"], ix.schema).parse(q)
            results = s.search_page(query, page, pagelen=pagelen)
            return [{"id": h["id"], "title": h["title"], "score": h.score}
                    for h in results], results.total

Wire it up with signals::

    # signals.py
    from django.db.models.signals import post_save, post_delete
    from django.dispatch import receiver
    from .models import Article
    from . import search_index

    @receiver(post_save, sender=Article)
    def on_save(sender, instance, **kwargs):
        search_index.index_article(instance)

    @receiver(post_delete, sender=Article)
    def on_delete(sender, instance, **kwargs):
        search_index.unindex_article(instance.pk)

For the initial import, add a management command that loops over your queryset
and commits once (see the batch pattern above). Because commits serialize
writers, prefer committing on a background worker (Celery, ``django-q``) in
production so a save request never blocks on index I/O.


Whoosh vs. SQLite FTS5 and other options
=========================================

A quick, honest comparison for people choosing a tool:

* **SQLite FTS5** — built into SQLite, extremely lightweight, great if your data
  already lives in SQLite and you want basic ``MATCH`` queries. Whoosh gives you
  richer, more tunable relevance (BM25F with per-field boosts), a friendlier
  Python query-parser API, faceting, and built-in spelling correction, without
  tying your search index to your relational store.
* **Elasticsearch / OpenSearch / Solr** — the right call for distributed,
  multi-service, very-large-scale search, but they are servers you have to run
  and operate. Whoosh needs none of that.
* **Typesense / Meilisearch** — fast, friendly search servers; still a separate
  process to deploy. Whoosh trades some scale for zero operational overhead.

Whoosh is the sweet spot when you want *good* search embedded directly in a
Python app with nothing extra to deploy.


Where to go next
================

* :doc:`quickstart` — the shortest possible intro.
* :doc:`schema` — field types (``TEXT``, ``KEYWORD``, ``NUMERIC``, ``DATETIME``…).
* :doc:`searching` — searchers, results, filtering, and collectors.
* :doc:`parsing` and :doc:`querylang` — the query parser and query syntax.
* :doc:`facets` — grouping and sorting results.
* :doc:`batch` — fast bulk indexing.
* :doc:`threads` — concurrency and writer coordination.
