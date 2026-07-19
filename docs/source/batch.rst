===================================
Tips for speeding up batch indexing
===================================


Overview
========

Indexing documents tends to fall into two general patterns: adding documents
one at a time as they are created (as in a web application), and adding a bunch
of documents at once (batch indexing).

The following settings and alternate workflows can make batch indexing faster.


StemmingAnalyzer cache
======================

The stemming analyzer by default uses a least-recently-used (LRU) cache to limit
the amount of memory it uses, to prevent the cache from growing very large if
the analyzer is reused for a long period of time. However, the LRU cache can
slow down indexing by almost 200% compared to a stemming analyzer with an
"unbounded" cache.

When you're indexing in large batches with a one-shot instance of the
analyzer, consider using an unbounded cache::

    from whoosh.analysis import StemFilter

    w = myindex.writer()
    # Get the analyzer object from a text field
    field_analyzer = w.schema["content"].analyzer
    # The analyzer is a pipeline of tokenizer + filters; find the StemFilter
    for item in field_analyzer:
        if isinstance(item, StemFilter):
            # Set the cachesize to -1 to indicate unbounded caching
            item.cachesize = -1
            # Reset the filter to pick up the changed attribute
            item.clear()

    # Use the writer to index documents...


The ``limitmb`` parameter
=========================

The ``limitmb`` parameter to :meth:`whoosh.index.Index.writer` controls the
*maximum* memory (in megabytes) the writer will use for the indexing pool. The
higher the number, the faster indexing will be.

The default value of ``128`` is actually somewhat low, considering many people
have multiple gigabytes of RAM these days. Setting it higher can speed up
indexing considerably::

    from whoosh import index

    ix = index.open_dir("indexdir")
    writer = ix.writer(limitmb=256)

.. note::
    The actual memory used will be higher than this value because of interpreter
    overhead (up to twice as much!). It is very useful as a tuning parameter,
    but not for trying to exactly control the memory usage of Whoosh.


The ``procs`` parameter
=======================

The ``procs`` parameter to :meth:`whoosh.index.Index.writer` controls the
number of processors the writer will use for indexing (via the
``multiprocessing`` module)::

    from whoosh import index

    ix = index.open_dir("indexdir")
    writer = ix.writer(procs=4)

Note that when you use multiprocessing, the ``limitmb`` parameter controls the
amount of memory used by *each process*, so the actual memory used will be
``limitmb * procs``::

    # Each process will use a limit of 128, for a total of 512
    writer = ix.writer(procs=4, limitmb=128)


The ``multisegment`` parameter
==============================

The ``procs`` parameter causes the default writer to use multiple processors to
do much of the indexing, but then still uses a single process to merge the pool
of each sub-writer into a single segment.

You can get much better indexing speed by also using the ``multisegment=True``
keyword argument, which instead of merging the results of each sub-writer,
simply has them each just write out a new segment::

    from whoosh import index

    ix = index.open_dir("indexdir")
    writer = ix.writer(procs=4, multisegment=True)

The drawback is that instead
of creating a single new segment, this option creates a number of new segments
**at least** equal to the number of processes you use.

For example, if you use ``procs=4``, the writer will create four new segments.
(If you merge old segments or call ``add_reader`` on the parent writer, the
parent writer will also write a segment, meaning you'll get five new segments.)

So, while ``multisegment=True`` is much faster than a normal writer, you should
only use it for large batch indexing jobs (or perhaps only for indexing from
scratch). It should not be the only method you use for indexing, because
otherwise the number of segments will tend to increase forever!


The ``start_method`` parameter
==============================

By default, the multiprocessing writer launches its sub-processes using the
interpreter's default start method (historically ``"fork"`` on POSIX systems).
On CPython 3.12 and later, using ``fork`` from a multi-threaded parent process
emits a ``DeprecationWarning``, and CPython is moving away from ``fork`` as the
default start method in future versions.

If you see that warning, or you want behavior that is stable across Python
versions and platforms, pass an explicit ``start_method``::

    from whoosh import index

    ix = index.open_dir("indexdir")
    writer = ix.writer(procs=4, start_method="spawn")

Valid values are the names returned by
:func:`multiprocessing.get_all_start_methods` for your platform, typically
``"fork"``, ``"spawn"`` and ``"forkserver"``. When you leave ``start_method``
unset, Whoosh keeps its original behavior and uses the interpreter default.

.. note::
   The ``"spawn"`` and ``"forkserver"`` start methods re-import your program in
   each sub-process, so on those methods your top-level indexing code must be
   guarded by ``if __name__ == "__main__":`` (this is a standard requirement of
   the :mod:`multiprocessing` module, not specific to Whoosh).
