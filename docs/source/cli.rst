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
    usage: whoosh [-h] [-V] {index,search,stats} ...

Check your installed version at any time with ``whoosh --version`` or
``whoosh -V``::

    $ whoosh --version
    whoosh 3.18.0 (https://github.com/priya-sundaram-dev/whoosh)


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

You can exclude specific folders or files using `--exclude` with glob patterns. This can be specified multiple times::

    $ whoosh index ~/notes --exclude "build/*" --exclude "*.min.js"

Preview which files *would* be indexed — under the current ``--ext`` and
``--exclude`` filters — without building anything, using ``--dry-run``. It
prints one relative path per line to stdout (easy to pipe or ``grep``) and a
short summary count to stderr, then exits without creating, clearing, or
writing the ``.whoosh_index`` directory::

    $ whoosh index ~/notes --dry-run --exclude "build/*"
    ideas.md
    todo.txt
    Would index 2 files under /home/you/notes

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

A brief summary line indicating how many matches were found is also printed to stderr.

Because matching is **stemmed**, a search for ``search`` also matches
``searching`` and ``searched`` — something a literal ``grep`` will not do.

The query supports Whoosh's full query language:

* boolean operators: ``python AND search``, ``index OR store``, ``search NOT sqlite``
* exact phrases: ``"full text search"``
* field terms: ``title:readme`` (documents are indexed with ``title``, ``path``,
  and ``body`` fields; ``title`` is boosted so filename matches rank higher)

Useful options::

    $ whoosh search "index writer" ~/notes --limit 20       # show up to 20 hits
    $ whoosh search "index writer" ~/notes --limit 20 --page 2  # show the next page
    $ whoosh search "index writer" ~/notes --html           # <mark>...</mark> snippets
    $ whoosh search "index writer" ~/notes --no-highlight   # plain, grep-friendly snippets
    $ whoosh search "index writer" ~/notes --snippet-chars 80  # shorter snippets
    $ whoosh search "index writer" ~/notes --json           # JSON array output
    $ whoosh search "index writer" ~/notes --jsonl          # JSON Lines output
    $ whoosh search "index writer" ~/notes -l               # matching file paths only
    $ whoosh search "index writer" ~/notes --count          # output just the number of matches
    $ whoosh search "index writer" ~/notes --sort-by mtime  # newest files first
    $ whoosh search "index writer" ~/notes --field title    # search titles only
    $ whoosh search "index writer" ~/notes --or             # match ANY term, not all

``--page N`` selects a 1-based page of results, with ``--limit`` as the page
size. Page 1 is the default. Human-readable output includes page metadata after
the first page; JSON, JSON Lines, and count output remain machine-friendly.

By default a multi-term query such as ``index writer`` requires **both** terms
to appear in a document (``index AND writer``). Pass ``--or`` to match documents
containing **any** of the terms (``index OR writer``) for broader, more
exploratory searches; documents matching more of the terms still rank higher::

    $ whoosh search "index writer" ~/notes --or            # index OR writer

Repeat ``--field`` to search more than one selected field with equal weighting.
When it is omitted, Whoosh searches ``title`` and ``body`` with the usual title
boost::

    $ whoosh search "index writer" ~/notes --field title --field body

``--field`` controls which fields are searched. The similarly named
``--fields`` option accepts a comma-separated list of stored fields to include
in the output instead.

``--html`` emits ``<mark>...</mark>`` around matched terms instead of the
default UPPERCASE highlighting, which is handy when piping results into a web
page or a note-taking tool.

``--no-highlight`` prints a plain, whitespace-collapsed leading slice of the
document body with no match markup at all. This keeps output readable and
grep-friendly when piping into other tools where the ``UPPERCASED`` match
tokens get in the way.

``--snippet-chars N`` sets the maximum number of characters shown per snippet
(default 200). It applies to the default text output, ``--no-highlight``, and
the ``snippet`` field of ``--json`` and ``--jsonl`` output.

``--json`` emits a machine-readable JSON array of matches, making it easy to
parse results with tools like ``jq``.

``--jsonl`` (alias ``--ndjson``) emits newline-delimited JSON (JSON Lines):
one standalone object per match, with the same fields as an element of the
``--json`` array. There are no surrounding brackets or trailing commas, so
line-oriented tools can process each match as soon as it is written. No matches
produces no output and exits with status ``1``::

    $ whoosh search "install guide" --jsonl | jq -c 'select(.score > 1.5)'

``-l`` (alias ``--files-with-matches``) prints one bare matching file path per
line, with no numbering, scores, snippets, or summary text. It respects
``--limit`` and ``--page``, making it useful in shell pipelines such as::

    $ whoosh search "index writer" ~/notes -l | xargs wc -l

No matches produces no output and exits with status ``1``.

The output-style flags (``--html``, ``--no-highlight``, ``--json``,
``--jsonl``/``--ndjson``, ``-l``/``--files-with-matches`` and ``--count``) are
mutually exclusive.

``--count`` prints only the total number of matching documents as a single integer
and exits, which is great for shell pipelines. As an output-style flag, it
cannot be combined with the other modes above.


Inspect an index
================

``whoosh stats`` prints a quick summary of an existing index without running a
query — handy for confirming an index built correctly, or for wiring index
health into a script::

    $ whoosh stats ~/notes
    Index: /home/you/notes/.whoosh_index
      documents:   128
      fields:      4
        - body (TEXT)
        - mtime (NUMERIC)
        - path (ID)
        - title (TEXT)
      size on disk: 2.1 MB  (7 files)
      last updated: 2026-07-15 12:56:46

Add ``--json`` for machine-readable output (document count, fields with their
types, size in bytes, and last-modified timestamp), which parses cleanly with
tools like ``jq``::

    $ whoosh stats ~/notes --json

To see what a field actually contains, ``--top-terms FIELD`` lists that field's
most frequent indexed terms, most-frequent-first, with their total
frequencies. Use ``--top N`` to cap the list (default 10)::

    $ whoosh stats ~/notes --top-terms body --top 5
    ...
    Top terms in 'body':
      312  the
      190  and
      143  index
       98  search
       71  python

This is a quick way to eyeball a corpus or sanity-check your analyzer. Naming a
field that does not exist, or a field type that has no text terms to rank
(such as ``NUMERIC`` or ``DATETIME``), prints a short, clear error to stderr
and exits ``2`` rather than a traceback::

    $ whoosh stats ~/notes --top-terms mtime
    error: field 'mtime' (NUMERIC) does not store text terms, so it has no top terms to list; try a TEXT field

The term listing is human-readable output only — the ``--json`` payload is
unchanged.


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
opens that index and runs a :doc:`MultifieldParser <parsing>` query across the
selected ``--field`` values (``title`` and ``body`` by default), then renders
:doc:`highlighted <highlight>` snippets.
``whoosh stats`` opens the index read-only and reports counts and metadata from
the reader and the on-disk files.

Everything the command does is achievable directly from the library — the CLI
just wires the pieces together with sensible defaults. If you outgrow it (custom
analyzers, extra fields, faceting, incremental writers in a long-running
process), reach for the API directly; the :doc:`quickstart` is the place to
start.


.. raw:: html

   <p style="font-size:0.85em;color:#777;">This documentation is maintained by
   Priya Sundaram, an AI software agent maintaining the Whoosh project. A human
   is looped in for anything that needs one.</p>
