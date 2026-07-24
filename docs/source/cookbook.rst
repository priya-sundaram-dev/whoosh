========
Cookbook
========

This page collects short, runnable recipes for common search tasks. Each one
maps to a self-contained script in the `examples/ directory
<https://github.com/priya-sundaram-dev/whoosh/tree/main/examples>`_ of the repository,
so you can run it end to end::

    git clone https://github.com/priya-sundaram-dev/whoosh
    cd whoosh
    pip install -e .
    python examples/quickstart.py

All recipes use only the standard library plus Whoosh itself — there are no
extra runtime dependencies.


Quick start
===========

``examples/quickstart.py`` — the shortest path from an empty directory to a
working search: define a :class:`~whoosh.fields.Schema`, add a couple of
documents, parse a user query with :class:`~whoosh.qparser.QueryParser`, and
print results with keyword highlighting.


A guided tour
=============

``examples/tutorial.py`` — a longer, commented walk-through that builds a small
product catalogue in an in-memory index. It covers:

* an in-memory index with :class:`~whoosh.filedb.filestore.RamStorage`
* upserting records with ``writer.update_document``
* single-field and multi-field parsing
  (:class:`~whoosh.qparser.QueryParser` /
  :class:`~whoosh.qparser.MultifieldParser`)
* combining a parsed query with an exact-term filter
* sorting results by a numeric field
* grouping results with a :class:`~whoosh.sorting.FieldFacet`
* highlighting matched terms in stored text

The prose version of the same material lives in ``TUTORIAL.md`` at the repo root.


"Did you mean …?" spelling correction
======================================

``examples/did_you_mean.py`` — Whoosh has spelling correction built in, with no
external dependencies. The recipe shows both single-word suggestions via
``searcher.suggest`` and whole-query correction via
``searcher.correct_query``, and prints both a plain-text and an HTML
"did you mean" prompt. See also :doc:`spelling`.


Autocomplete / search-as-you-type
==================================

``examples/autocomplete.py`` — three pure-Python approaches to
search-as-you-type:

* term completion with ``reader.expand_prefix``
* prefix matching with :class:`whoosh.query.Prefix`
* "matches anywhere" fuzzy completion with an n-gram analyzer
  (see :doc:`ngrams`)

Pick the one that fits your latency and index-size budget.


Whoosh vs. SQLite FTS5
======================

``examples/benchmark_vs_sqlite.py`` — an honest, reproducible micro-benchmark
comparing build time, on-disk size, and average query latency against SQLite's
FTS5 extension over the same corpus. Use it to decide when Whoosh's pure-Python,
zero-dependency, deeply programmable model is the right trade-off for your
project, and when an embedded C engine is a better fit.


Faceted navigation (filter sidebar with counts)
===============================================

``examples/faceted_search.py`` — the pattern behind the "filter sidebar" on
almost every shopping or catalogue site. Alongside the results you show each
facet (brand, category, price band…) with a count of how many matching
documents fall into each bucket, and clicking a bucket narrows the result set.

Whoosh does this natively: pass a facet — or a dict of them — as the
``groupedby`` argument to ``Searcher.search`` and read the per-bucket counts
from ``Results.groups()``. The counts come from the same search call that
produces your results, so they always reflect the current query. The recipe
covers:

* :class:`~whoosh.sorting.FieldFacet` for single-valued fields
* :class:`~whoosh.sorting.FieldFacet` with ``allow_overlap=True`` for
  multi-valued ``KEYWORD`` fields
* :class:`~whoosh.sorting.RangeFacet` for numeric buckets
* "drill down" by AND-ing a chosen facet value onto the current query

See also :doc:`facets` for the full faceting reference.


Highlighting and snippets
=========================

``examples/highlighting.py`` — turn raw matches into the "keyword in context"
snippets you see on a real search-results page. Call ``Hit.highlights(fieldname)``
and Whoosh finds the best-scoring passages, trims them to a readable length,
and wraps each matched term in markup. The recipe covers:

* the one-liner: ``hit.highlights("body")`` off a stored field
* choosing *where* snippets are cut —
  :class:`~whoosh.highlight.ContextFragmenter` (a window around each match)
  vs :class:`~whoosh.highlight.SentenceFragmenter` (whole sentences)
* choosing *how* matches are marked —
  :class:`~whoosh.highlight.HtmlFormatter` with your own tag and CSS class,
  or :class:`~whoosh.highlight.UppercaseFormatter` for plain text
* fast "pinpoint" highlighting: index the field with ``chars=True`` and use
  :class:`~whoosh.highlight.PinpointFragmenter` so long documents are
  highlighted *without* being re-tokenized
* highlighting a field you did **not** store, by passing the original text to
  ``hit.highlights("body", text=...)``
* highlighting *only* real phrase matches (not stray occurrences of the
  individual words) with ``hit.highlights("body", strict_phrase=True)``

See also :doc:`highlight` for the full highlighting reference.


Custom analyzers (build your own text pipeline)
===============================================

``examples/custom_analyzers.py`` — the feature that sets Whoosh apart: instead
of a fixed set of "language modes", you compose your own text-processing
pipeline from a tokenizer and a chain of filters using the ``|`` operator::

    from whoosh.analysis import RegexTokenizer, LowercaseFilter, StopFilter
    analyzer = RegexTokenizer() | LowercaseFilter() | StopFilter()

The first item must be a tokenizer; everything after it is a filter. Attach the
analyzer to a field (``TEXT(analyzer=analyzer)``) and Whoosh runs the *same*
pipeline at index time and query time, so the two always agree. The recipe
covers:

* watching a pipeline take shape one stage at a time — tokenize, lowercase,
  drop stop words, then stem with :class:`~whoosh.analysis.StemFilter`
* accent folding with :class:`~whoosh.analysis.CharsetFilter` and the bundled
  ``accent_map`` so ``cafe`` matches ``café``
* normalising tokens with :class:`~whoosh.analysis.SubstitutionFilter` so
  ``wi-fi``, ``wi_fi`` and ``wifi`` collapse to one term
* character :class:`~whoosh.analysis.NgramFilter` for substring / "matches
  anywhere" search
* wiring a custom analyzer onto a field and confirming, with a real index, that
  ``run`` finds ``running``/``runner``/``ran`` and ``ZURICH`` finds ``Zürich``

See also :doc:`analysis` for the full analysis reference.


Custom scoring & sorting (control the ranking)
==============================================

``examples/scoring_and_sorting.py`` — ranking is where a search library earns
its keep. Whoosh gives you several independent levers, and this recipe runs each
one against a real index so you can see the ranking change:

* **tuning the default** :class:`~whoosh.scoring.BM25F` model — ``B`` controls
  document-length normalisation and ``K1`` controls term-frequency saturation;
  per-field values use a ``<field>_B`` keyword (for example
  ``BM25F(B=0.75, body_B=0.2)``)
* **swapping the model entirely** for :class:`~whoosh.scoring.TF_IDF` or
  :class:`~whoosh.scoring.Frequency`
* **mixing models per field** with :class:`~whoosh.scoring.MultiWeighting`
  (for example ``TF_IDF`` for titles, ``BM25F`` everywhere else)
* **scoring with your own function** via
  :class:`~whoosh.scoring.FunctionWeighting`, which receives
  ``(searcher, fieldname, text, matcher)`` and returns a float — ideal for
  experiments and business rules
* **skipping relevance altogether** and sorting by a stored, sortable field
  with ``search(q, sortedby="views", reverse=True)`` — faster than scoring and
  often exactly what "newest first" / "most viewed" UIs need

Pass any weighting model to the searcher::

    from whoosh import scoring
    with ix.searcher(weighting=scoring.BM25F(B=0.0, K1=2.0)) as s:
        results = s.search(q)

See also :doc:`api/scoring` and :doc:`facets` for the full reference.


Closing indexes cleanly (and avoiding Windows file-lock errors)
===============================================================

Whoosh keeps an index's on-disk files open while a reader or searcher is
alive, so it can answer queries without re-opening files each time. If you
let those objects be cleaned up by the garbage collector instead of closing
them, the files stay open until the object is actually collected.

On POSIX systems that is usually harmless. On **Windows**, an open file
handle prevents the file from being deleted or replaced, so deleting or
rebuilding an index while a reader is still open surfaces as
``PermissionError: [WinError 32] The process cannot access the file because
it is being used by another process``. The robust fix is not to sprinkle
``gc.collect()`` calls around — it is to close what you open.

Every reader and searcher is a context manager, so a ``with`` block releases
the handles deterministically as soon as the block exits, even on error::

    from whoosh.qparser import QueryParser

    qp = QueryParser("body", ix.schema)
    q = qp.parse("pure AND search")

    with ix.searcher() as searcher:          # searcher closes on exit
        results = searcher.search(q, limit=10)
        titles = [hit["title"] for hit in results]

    with ix.reader() as reader:              # readers are context managers too
        total = reader.doc_count()

When you are completely finished with an index object, call ``ix.close()`` to
release any cached readers it is holding on your behalf::

    ix.close()

After everything is closed, the index directory can be deleted or rebuilt
immediately — including on Windows — with no ``gc.collect()`` workaround.

If you use :class:`~whoosh.writing.AsyncWriter`, remember that its background
thread must finish (via ``commit()``) before the segment's files are released.
Track any writers you create and join them before tearing down the index.

A complete, runnable version of this pattern lives in
``examples/resource_management.py``.


A command-line folder search tool
=================================

``examples/search_cli.py`` — a tiny, dependency-free command-line program that
indexes a folder of text, Markdown, reStructuredText, or source files and lets
you search it straight from your terminal. No server, no external service::

    # Index the current directory (creates ./.whoosh_index/)
    python examples/search_cli.py index .

    # Search it, with highlighted snippets
    python examples/search_cli.py search "full text search"

    # Re-index only changed/new files and drop deleted ones (fast; uses mtimes)
    python examples/search_cli.py index . --update

    # Choose which extensions to index, or emit HTML <mark> highlights
    python examples/search_cli.py index ~/notes --ext .md,.txt
    python examples/search_cli.py search "ranking" --html

It demonstrates several everyday patterns in one place: a
:class:`~whoosh.fields.Schema` with a ``unique`` :class:`~whoosh.fields.ID`
path, ``writer.update_document`` for idempotent upserts,
``writer.delete_by_term`` to prune deleted files, incremental indexing driven by
a stored :class:`~whoosh.fields.NUMERIC` ``mtime``, field-boosted
:class:`~whoosh.qparser.MultifieldParser` queries, and result highlighting with
:class:`~whoosh.highlight.ContextFragmenter`. It is a single file you can copy
into your own project and adapt.


A full-text search API with FastAPI
====================================

``examples/fastapi_app.py`` — a small, production-shaped REST API that adds
full-text search to a web service. It exposes ``PUT /documents/{id}`` (an
idempotent upsert), ``DELETE /documents/{id}``, and ``GET /search`` with
pagination and highlighted snippets::

    pip install "whoosh3" fastapi "uvicorn[standard]"
    uvicorn fastapi_app:app --reload

    curl -X PUT localhost:8000/documents/1 \
        -H 'content-type: application/json' \
        -d '{"title": "Getting started with Whoosh", "body": "pure-python search"}'

    curl 'localhost:8000/search?q=python&page=1&page_size=10'

The search logic lives in a small, framework-free ``SearchIndex`` class so it
is easy to unit-test without an HTTP server (run ``python fastapi_app.py`` for a
self-contained demo). It shows the pattern you actually need in a service: a
persistent on-disk index opened once at startup and
:meth:`closed <whoosh.index.Index.close>` at shutdown (so file handles are
released — important on Windows), ``writer.update_document`` upserts keyed on a
unique :class:`~whoosh.fields.ID`, BM25F ranking, ``searcher.search_page`` for
pagination, and highlighted snippets via
:class:`~whoosh.highlight.HtmlFormatter`. See :doc:`integrations` for the
broader "adding search to your app" guide, including a Django variant.


A full-text search app with Flask
==================================

``examples/flask_app.py`` — the same search API as the FastAPI example, built
on Flask so you can compare the two frameworks side by side. It exposes an
idempotent ``PUT /documents/<id>`` upsert, ``DELETE /documents/<id>``, and
``GET /search`` with pagination and highlighted snippets::

    pip install "whoosh3" flask
    flask --app flask_app run --debug

    curl -X PUT localhost:5000/documents/1 \
        -H 'content-type: application/json' \
        -d '{"title": "Getting started with Whoosh", "body": "pure-python search"}'

    curl 'localhost:5000/search?q=python&page=1&page_size=10'

Like the FastAPI example, the Whoosh logic lives in a framework-free
``SearchIndex`` class (run ``python flask_app.py`` for a self-contained demo),
so the Flask layer — wired up with a standard ``create_app`` application
factory — stays thin. It highlights the concurrency rule that matters in a
threaded WSGI server: a Whoosh index allows one writer at a time but many
concurrent readers, so writes are serialised behind a lock and each request
opens a fresh, short-lived ``searcher()`` rather than sharing one across
threads. See :doc:`integrations` for the broader guide.


A full-text search app with Django
==================================

``examples/django_app.py`` — the same search API as the FastAPI and Flask
examples, built on Django. Django's built-in full-text search only works on
PostgreSQL; Whoosh gives you relevance-ranked search with highlighted snippets
on *any* database (or none) with a no-compile ``pip install``. It is a
single-file Django project — settings, URLs, and views all live in the one
module — so it runs without a full ``startproject`` layout::

    pip install "whoosh3" django
    python django_app.py runserver

    curl -X PUT localhost:8000/documents/1 \
        -H 'content-type: application/json' \
        -d '{"title": "Getting started with Whoosh", "body": "pure-python search"}'

    curl 'localhost:8000/search?q=python&page=1&page_size=10'

As in the other examples, the Whoosh logic lives in a framework-free
``SearchIndex`` class (run ``python django_app.py`` with no arguments for a
self-contained demo). In a real project you keep the index in sync with the
ORM by calling ``upsert``/``delete`` from ``post_save``/``post_delete``
signals — the module docstring shows the exact wiring. The same concurrency
rule applies: one writer at a time behind a lock, a fresh ``searcher()`` per
request. See :doc:`integrations` for the broader guide.


Adding search to a static site
==============================

``examples/static_site_search.py`` — a lightweight script to index a directory of static files (e.g. Markdown or ReStructuredText) and perform a search on them. Because Whoosh is pure Python and doesn't require a server, it's perfect for static sites::

    python examples/static_site_search.py index docs/source
    python examples/static_site_search.py search "whoosh"

The script walks the directory to find ``.md`` and ``.rst`` files, strips out simple markup using standard library regular expressions, and builds a Whoosh index. The schema boosts the ``title`` over the ``body`` content. When searching, it opens the index and prints highlighted snippets. This approach allows you to build the index at CI time or distribute it alongside a desktop application without external database dependencies.


Migrating from Whoosh 2.x / whoosh-reloaded
===========================================

Already using the original ``Whoosh`` or ``Whoosh-Reloaded``? The
``MIGRATING.md`` guide at the repo root explains what changed: the import
package is still ``whoosh``, the on-disk index format is unchanged, and the
public API is the same. In most cases the only change you make is the package
you install.
