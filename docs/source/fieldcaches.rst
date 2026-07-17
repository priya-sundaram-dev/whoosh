============
Field caches
============

.. note::

   This page describes an older mechanism. In current Whoosh, the way to make
   sorting and faceting fast is to store per-document values in a **column** by
   passing ``sortable=True`` when you define a field. See
   :doc:`facets` for the full, up-to-date guide. The rest of this page explains
   how field caches relate to that, and what changed.

What field caches are
=====================

When you sort or facet on a field, Whoosh needs a per-document value for that
field so it can order the documents. Historically the ``filedb`` backend would
build this ordering on demand and keep it in a *field cache* — a structure that
pre-computes the order of documents in the index to speed up sorting and
faceting.

Building that ordering the first time can take a moment on a large index, so
Whoosh keeps it in memory for the life of the searcher and reuses it for
subsequent sorted or faceted searches.

The modern replacement: sortable columns
=========================================

The recommended approach today is to tell Whoosh up front which fields you will
sort or facet on, by passing ``sortable=True`` when you define them::

    from whoosh import fields

    schema = fields.Schema(title=fields.TEXT(sortable=True),
                           content=fields.TEXT,
                           modified=fields.DATETIME(sortable=True))

When a field is ``sortable``, Whoosh stores its per-document values in a
:mod:`whoosh.columns` column on disk at index time. Sorting and faceting then
read directly from that column, so there is no need to build an in-memory field
cache first, and the values persist with the index instead of being recomputed
for each new searcher.

You *can* still sort or facet on a field that was not created with
``sortable=True`` — in that case Whoosh falls back to computing the ordering in
memory (an internal field cache) the first time it is needed. This works, but it
is slower and uses more memory on large indexes, so prefer ``sortable=True`` for
any field you know you will order by. See :doc:`facets` for details on column
types (``VarBytesColumn``, ``NumericColumn``, ``RefBytesColumn``, and friends)
and how to choose one.

What changed
============

Earlier versions of Whoosh exposed a configurable *caching policy* for the
on-disk field cache — a ``set_caching_policy()`` method on readers and searchers
and a ``whoosh.filedb.fieldcache.FieldCachingPolicy`` base class you could
subclass to control where caches were written or when they expired.

That machinery has been **removed**. The ``whoosh.filedb.fieldcache`` module and
the ``set_caching_policy()`` method no longer exist, and calling them will raise
an error. Sortable columns cover the same need — persistent, fast sort/facet
values — in a simpler and more reliable way, so there is no separate caching
policy to configure. Any per-field ordering that a column does not provide is
computed in memory automatically, with no configuration required.

If you are migrating old code that called ``set_caching_policy()`` or referenced
``FieldCachingPolicy``, remove those calls and add ``sortable=True`` (or a custom
column via the ``sortable=`` argument) to the fields you sort or facet on. See
the :doc:`facets` guide.
