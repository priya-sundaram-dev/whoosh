====================================
Concurrency, locking, and versioning
====================================

Concurrency
===========

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


Versioning
==========

When you open a reader/searcher, the reader represents a view of the **current
version** of the index. If someone writes changes to the index, any readers
that are already open **will not** pick up the changes automatically. A reader
always sees the index as it existed when the reader was opened.

If you are re-using a Searcher across multiple search requests, you can check
whether the Searcher is a view of the latest version of the index using
:meth:`whoosh.searching.Searcher.up_to_date`. If the searcher is not up to date,
you can get an up-to-date copy of the searcher using
:meth:`whoosh.searching.Searcher.refresh`::

    # If 'searcher' is not up-to-date, replace it
    searcher = searcher.refresh()

(If the searcher has the latest version of the index, ``refresh()`` simply
returns it.)

Calling ``Searcher.refresh()`` is more efficient that closing the searcher and
opening a new one, since it will re-use any underlying readers and caches that
haven't changed.
