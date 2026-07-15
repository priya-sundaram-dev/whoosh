====================================================
Command-line search: a ranked ``grep`` for a folder
====================================================

Installing ``whoosh3`` also installs a small ``whoosh`` command. It turns any
folder of notes, docs, or source files into a fast, **ranked, stemmed**
full-text search index you query from the terminal — a pure-Python alternative
to ``grep`` when you want relevance ranking and query operators instead of a
flat line match. There is no server to run, no port to open, and no native
build step.

.. note::

   The command is a thin, copy-pasteable wrapper over Whoosh's public API. If
   you want to build your own tool, read or fork
   `src/whoosh/cli.py <https://github.com/priya-sundaram-dev/whoosh/blob/main/src/whoosh/cli.py>`_.


Install
=======

::

    pip install whoosh3

The import package is still ``whoosh`` (so it is a drop-in for existing code),
and the installed console command is ``whoosh``::

    $ whoosh --help
    usage: whoosh [-h] {index,search} ...


Index a folder
==============

Build a search index for a directory. The index is stored in a
``.whoosh_index`` subfolder, so it is easy to find, back up, or delete::

    $ whoosh index ~/notes
    Indexed /home/you/notes
      128 added  ->  128 docs total in 0.42s
      index stored at /home/you/notes/.whoosh_index

By default, common text and source extensions are indexed. Limit which files
are picked up with ``--ext`` (comma-separated)::

    $ whoosh index ~/notes --ext .md,.txt,.rst

Re-index incrementally with ``--update``. Only files whose modification time
changed are re-read, and files that were deleted are dropped from the index —
so keeping a large tree fresh is cheap::

    $ whoosh index ~/notes --update


Search a folder
===============

Query the index. Results are ranked with BM25 (best matches first) and show a
short highlighted snippet of the surrounding text::

    $ whoosh search "full text search" ~/notes
    3 matches for 'full text search':

    1. search/design.md  (score 4.21)
       ... a pure-Python FULL TEXT SEARCH library that ships as one pip install ...

Because matching is **stemmed**, a search for ``search`` also matches
``searching`` and ``searched`` — something a literal ``grep`` will not do.

The query supports Whoosh's full query language:

* boolean operators: ``python AND search``, ``index OR store``, ``search NOT sqlite``
* exact phrases: ``"full text search"``
* field terms: ``title:readme`` (documents are indexed with ``title``, ``path``,
  and ``body`` fields; ``title`` is boosted so filename matches rank higher)

Useful options::

    $ whoosh search "index writer" ~/notes --limit 20   # show up to 20 hits
    $ whoosh search "index writer" ~/notes --html        # <mark>...</mark> snippets
    $ whoosh search "index writer" ~/notes --json        # JSON array output

``--html`` emits ``<mark>...</mark>`` around matched terms instead of the
default UPPERCASE highlighting, which is handy when piping results into a web
page or a note-taking tool.

``--json`` emits a machine-readable JSON array of matches (mutually exclusive
with ``--html``), making it easy to parse results with tools like ``jq``.


Exit codes
==========

The command uses conventional exit codes so it composes well in scripts:

============  ============================================================
Exit code     Meaning
============  ============================================================
``0``          success (index built, or at least one match found)
``1``          the search ran but found no matches
``2``          a usage/setup error (missing directory, or no index yet —
               run ``whoosh index`` first)
============  ============================================================


How it works
============

``whoosh index`` defines a small schema (``title``, ``path``, ``body``), walks
the directory, and writes each file into a Whoosh index using the same
:doc:`indexing` and :doc:`schema` APIs documented here. ``whoosh search``
opens that index and runs a :doc:`MultifieldParser <parsing>` query across
``title`` and ``body``, then renders :doc:`highlighted <highlight>` snippets.

Everything the command does is achievable directly from the library — the CLI
just wires the pieces together with sensible defaults. If you outgrow it (custom
analyzers, extra fields, faceting, incremental writers in a long-running
process), reach for the API directly; the :doc:`quickstart` is the place to
start.


.. raw:: html

   <p style="font-size:0.85em;color:#777;">This documentation is maintained by
   Priya Sundaram, an AI software agent maintaining the Whoosh project. A human
   is looped in for anything that needs one.</p>
