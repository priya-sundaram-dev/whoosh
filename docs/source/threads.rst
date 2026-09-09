====================================
Concurrency, locking, and versioning
====================================

Concurrency
===========

Quick reference: what is safe to share across threads
-----------------------------------------------------

Whoosh has no global mutable state, so the concurrency contract is
per-object. The table below is the short version; the sections that follow
explain the *why*. It applies equally on the GIL and free-threaded
(no-GIL, PEP 703) CPython builds — on a free-threaded build these same
read-only-shareable objects are what let indexing and search actually scale
across cores.

.. list-table::
   :header-rows: 1
   :widths: 26 20 54

   * - Object
     - Share across threads?
     - Contract
   * - :class:`~whoosh.index.Index` / ``FileIndex``
     - **Yes**
     - Stateless handle to the index directory. Open once and share it; each
       thread derives its own reader/searcher/writer from it.
   * - :class:`~whoosh.fields.Schema`
     - **Yes, once built**
     - Read-only after you create the index. Finish calling
       :meth:`~whoosh.fields.Schema.add` *before* you share it; don't mutate a
       schema that other threads are reading.
   * - :class:`~whoosh.reading.IndexReader` /
       :class:`~whoosh.searching.Searcher`
     - **One per thread**
     - Wraps open files and relies on consistent file-cursor positions, so it
       is *not* safe to call from two threads at once. Sharing a **read-only**
       searcher across sequential requests is a big win (it caches field data);
       just don't drive one searcher from multiple threads concurrently.
   * - :class:`~whoosh.writing.IndexWriter` (plain ``ix.writer()``)
     - **No — one at a time**
     - Holds the exclusive write lock for the whole index. A second writer
       (any thread or process) raises :class:`~whoosh.index.LockError`. Use it
       from one thread and close it to release the lock.
   * - :class:`~whoosh.writing.BufferedWriter`
     - **Yes, by design**
     - Built to be created once and shared: it serializes ``add``/``update``/
       ``commit`` with an internal ``threading.RLock`` and buffers documents
       for near-real-time search. Call :meth:`~whoosh.writing.BufferedWriter.close`
       before it goes out of scope.
   * - :class:`~whoosh.writing.AsyncWriter`
     - n/a (helper)
     - Not a shared object but a way to *cope* with the single-writer rule:
       it retries the commit on a background thread if the index is locked.

The ``FileIndex`` object is "stateless" and should be share-able between
threads.

A ``Reader`` object (which underlies the ``Searcher`` object) wraps open files and often
individual methods rely on consistent file cursor positions (e.g. they do two
``file.read()``\ s in a row, so if another thread moves the cursor between the two
read calls Bad Things would happen). You should use one Reader/Searcher per
thread in your code.

Readers/Searchers tend to cache information (such as field caches for sorting),
so if you can share one across multiple search requests, it's a big performance
win.


Locking
=======

Only one thread/process can write to an index at a time. When you open a writer,
it locks the index. If you try to open a writer on the same index in another
thread/process, it will raise :class:`whoosh.index.LockError`.

In a multi-threaded or multi-process environment your code needs to be aware
that opening a writer may raise this exception if a writer is already open.
Whoosh includes a couple of example implementations
(:class:`whoosh.writing.AsyncWriter` and :class:`whoosh.writing.BufferedWriter`)
of ways to work around the write lock.

While the writer is open and during the commit, **the index is still available
for reading**. Existing readers are unaffected and new readers can open the
current index normally.

.. warning::

    Always go through the write lock. If two processes write to the same index
    at the same time *without* coordinating through the lock (for example by
    forcibly clearing the lock, or by writing to a shared index from separate
    machines over a filesystem that doesn't honor the lock), they can overwrite
    each other's segment files and leave the index corrupted. A corrupted index
    typically fails at *read* time with a
    :class:`whoosh.reading.CorruptIndexError` (a damaged postings block), which
    reports the affected file and this likely cause. If you hit it, rebuild the
    index from your source data.


Lock files
----------

Locking the index is accomplished by acquiring an exclusive file lock on the
``<indexname>_WRITELOCK`` file in the index directory. The file is not deleted
after the file lock is released, so the fact that the file exists **does not**
mean the index is locked.

Under the hood the write lock uses an OS-level file lock: ``fcntl.flock`` on
UNIX/macOS and ``msvcrt.locking`` on Windows (see
:mod:`whoosh.util.filelock`). OS-level locks are released automatically if the
process crashes, so a stale ``_WRITELOCK`` file left behind by a crash does
**not** keep the index permanently locked — the next writer can acquire it.


Windows
-------

Whoosh runs on Windows, but the platform's file semantics differ from
UNIX/macOS in two ways that matter for long-running services (for example
paperless-ngx or MoinMoin re-indexing on Windows):

1. **File locks are mandatory, not advisory.** ``msvcrt.locking`` takes a
   real kernel lock, so a second writer reliably fails fast with
   :class:`whoosh.index.LockError` instead of silently interleaving writes.
   This is the safe behaviour, but it means you must handle ``LockError``
   (retry, back off, or queue the write) rather than assuming a writer is
   always available.

2. **An open file handle blocks deletion and rename.** On Windows you cannot
   ``os.remove`` or ``os.rename`` a file while any handle to it is open;
   the call raises ``PermissionError`` (WinError 32, *"The process cannot
   access the file because it is being used by another process"*). Whoosh
   deletes and replaces segment files during ``commit()`` and ``optimize()``,
   so a **reader or searcher that is still open on an old segment can make a
   concurrent commit/optimize fail on Windows** even though the same code runs
   fine on Linux and macOS.

   The fix is to make sure readers and searchers are closed before (or
   promptly after) writing. Use them as context managers so their handles are
   released deterministically rather than whenever the garbage collector runs::

       # Preferred: handles released at the end of the block.
       with ix.searcher() as s:
           results = s.search(query)
           # ... use results inside the block ...

       # Now it is safe to write, optimize, or rebuild on Windows.
       with ix.writer() as w:
           w.add_document(...)

   If you keep a long-lived searcher for performance, refresh it (see
   :meth:`whoosh.searching.Searcher.refresh` below) rather than holding a
   handle to a segment that a later ``optimize()`` needs to delete. Relying on
   CPython reference-counting to close readers "eventually" is not enough on
   Windows and is not guaranteed on other implementations such as PyPy.

The close-then-delete contract is guarded by a regression test
(``test_index_files_deletable_after_close``) so it keeps working release to
release.


Parallel indexing (free-threaded builds)
========================================

Indexing is CPU-bound *pure-Python* work — tokenizing, stemming, filtering,
and building postings. On a normal (GIL-enabled) build, spreading that work
across threads does not speed it up: only one thread runs Python at a time. On
a **free-threaded** build (``3.13t``/``3.14t``, PEP 703) the GIL is gone, so
that same work can finally scale across real cores without dropping into C.

Because a plain :class:`~whoosh.writing.IndexWriter` is single-writer (see the
quick-reference table above), the blessed pattern is **not** to share one
writer across threads. Instead, fan out into one sub-index per worker thread,
then fan in by merging the finished sub-indexes with
:meth:`whoosh.writing.IndexWriter.add_reader`:

1. Build the :class:`~whoosh.fields.Schema` once (it is immutable and safe to
   share).
2. Split the corpus into *N* shards; each worker thread creates **its own**
   index in **its own** directory and writes its shard — one writer per thread,
   so the write lock is never contended.
3. On the main thread, open a read-only reader on each finished sub-index and
   ``writer.add_reader(reader)`` them into one final index, then
   ``commit(optimize=True)``.

The merged result is an ordinary Whoosh index, identical to what a single
serial writer would have produced. This is the same ``add_reader`` primitive
Whoosh's own multiprocessing writer uses. A complete, runnable implementation
with a serial-vs-parallel timing harness and a correctness check ships as
``examples/parallel_indexing.py``::

    python examples/parallel_indexing.py --docs 40000 --workers 4

On a GIL build the parallel path is about the same as (or slightly slower than)
the serial baseline — the merge adds a little work the serial path avoids, and
that is expected. Run it on a free-threaded build to see the parallel path pull
ahead as workers increase.


Parallel search (free-threaded builds)
======================================

Searching is CPU-bound *pure-Python* work too — parsing the query, walking
postings, scoring, and collecting hits. The same free-threading win applies to
the read side, and it is the classic search-server shape: many concurrent
read-only requests against one shared index.

A built :class:`~whoosh.index.Index` is read-only and safe to share across
threads, but a :class:`~whoosh.searching.Searcher` is **not** safe to drive
from two threads at once (see the quick-reference table above). So the blessed
pattern is:

1. Build (or open) the index **once** and share that one handle.
2. Give each worker thread **its own** searcher, opened from the shared index
   and **reused** for every query that thread handles. Do not open a fresh
   searcher per query — that throws away the field caches that make search
   fast — and do not share one searcher between threads.
3. Fan the query batch out across the pool; collect the results.

Because every searcher is thread-local, no searcher is ever driven by two
threads at once, so the results are identical to a serial run — correct by
construction. A complete, runnable implementation with a serial-vs-parallel
timing harness and a results-equivalence check ships as
``examples/parallel_search.py``::

    python examples/parallel_search.py --docs 20000 --queries 4000 --workers 4

As with indexing, a GIL build shows a speedup near 1x (thread-pool overhead can
even make it slightly slower); a free-threaded build lets the query batch scale
across cores without any C extension.


Versioning
==========

When you open a reader/searcher, the reader represents a view of the **current
version** of the index. If someone writes changes to the index, any readers
that are already open **will not** pick up the changes automatically. A reader
always sees the index as it existed when the reader was opened.

If you are reusing a Searcher across multiple search requests, you can check
whether the Searcher is a view of the latest version of the index using
:meth:`whoosh.searching.Searcher.up_to_date`. If the searcher is not up to date,
you can get an up-to-date copy of the searcher using
:meth:`whoosh.searching.Searcher.refresh`::

    # If 'searcher' is not up-to-date, replace it
    searcher = searcher.refresh()

(If the searcher has the latest version of the index, ``refresh()`` simply
returns it.)

Calling ``Searcher.refresh()`` is more efficient that closing the searcher and
opening a new one, since it will reuse any underlying readers and caches that
haven't changed.
