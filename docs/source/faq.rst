=========================
FAQ and troubleshooting
=========================

Short, practical answers to the questions and error messages that come up most
often. Every code snippet here is checked against the current release. If your
problem isn't covered, please
`open an issue or a discussion <https://github.com/priya-sundaram-dev/whoosh/issues>`_.


Installation
============

``pip install whoosh`` gives me an ancient version
------------------------------------------------------

The name ``whoosh`` on PyPI still points at the original **2.7.4** release from
2016, which is unmaintained. The actively maintained fork is published as
**whoosh3**::

    pip install whoosh3

The import name is unchanged — you still write ``import whoosh``. Only the
*distribution* name differs, so existing code keeps working after you switch::

    from whoosh.index import create_in
    from whoosh.fields import Schema, TEXT, ID

If both are installed in the same environment, uninstall the old one first
(``pip uninstall whoosh``) so imports resolve to the maintained package.


Indexing
========

``whoosh.store.LockError`` when I open a second writer
------------------------------------------------------

Whoosh allows **only one writer at a time** per index. This is by design: it is
how the on-disk format stays consistent without a server. Opening a second
``ix.writer()`` while another is still open (not yet committed or cancelled)
raises ``LockError``::

    w1 = ix.writer()
    w2 = ix.writer()          # raises whoosh.store.LockError

Fixes, in rough order of preference:

* **Reuse one writer** and batch your ``add_document`` calls, then ``commit()``
  once. This is also much faster than a writer per document.
* If several *threads* or *tasks* in one process need to add documents, use
  :class:`whoosh.writing.AsyncWriter` or :class:`whoosh.writing.BufferedWriter`,
  which serialize writes for you. See the
  `concurrency guide <https://priya-sundaram-dev.github.io/whoosh/docs/threads.html>`_.
* If a previous run crashed and left a stale lock, make sure no other process
  holds the index, then remove the lock (``ix.storage`` exposes the lock; or
  delete the ``*.lock`` file in the index directory when you are certain nothing
  else is writing).

Multiple *readers*/searchers are always fine — the single-writer rule only
applies to writes.

My searcher doesn't see documents I just added
----------------------------------------------

A searcher is a **point-in-time snapshot** of the index. A searcher you opened
*before* a commit will not see documents added by that commit — even in the same
process::

    s = ix.searcher()
    w = ix.writer(); w.add_document(title="new"); w.commit()
    s.search(qp.parse("new"))          # 0 hits — snapshot is stale

    s = ix.searcher()                  # open a fresh searcher...
    s.search(qp.parse("new"))          # 1 hit

    # ...or refresh the one you have (cheaper than reopening from scratch):
    s = s.refresh()
    s.search(qp.parse("new"))          # 1 hit

In a long-running service, reopen or ``refresh()`` your searcher after each
commit (or on a timer). ``refresh()`` reuses the parts of the index that didn't
change, so it's cheap to call often.

Nothing gets indexed / the index is empty
------------------------------------------

Almost always a missing **commit**. ``add_document`` buffers changes; they are
only written when you call ``commit()``::

    w = ix.writer()
    w.add_document(title="hello")
    w.commit()                         # <- without this, nothing persists

If you use ``with ix.writer() as w:`` note that the writer commits on a clean
exit but **cancels on an exception** — so an error inside the block discards the
batch.


Searching
=========

My search returns no results even though the word is there
----------------------------------------------------------

The single most common cause is an **analyzer mismatch** between how the text
was indexed and how your query term is spelled. A ``TEXT`` field lowercases and
tokenizes its input, so the stored term for ``"Hello World"`` is ``hello`` and
``world`` — lowercase. If you build a query term *by hand* with the original
casing, it won't match::

    from whoosh.query import Term
    s.search(Term("body", "Hello"))    # 0 hits — index stored "hello"
    s.search(Term("body", "hello"))    # 1 hit

The fix is to let the **QueryParser** run the field's analyzer for you, so query
terms are processed exactly like indexed terms::

    from whoosh.qparser import QueryParser
    qp = QueryParser("body", ix.schema)     # pass the schema!
    s.search(qp.parse("Hello"))             # 1 hit — parser lowercases it

Passing ``ix.schema`` (not just the field name) is what makes the parser apply
the same analysis your fields use. This is why hand-built ``Term`` objects are a
frequent source of "no results": they bypass analysis entirely.

Searching ``run`` doesn't find ``running`` (or vice versa)
----------------------------------------------------------

The default ``TEXT`` analyzer does **not** do stemming, so ``run`` and
``running`` are different terms::

    schema = Schema(body=TEXT)               # no stemming
    # query "run" does NOT match a document containing only "running"

To match across word inflections, index the field with a
:class:`~whoosh.analysis.StemmingAnalyzer`::

    from whoosh.analysis import StemmingAnalyzer
    schema = Schema(body=TEXT(analyzer=StemmingAnalyzer()))

Whoosh's built-in stemmer is deliberately conservative (it collapses common
suffixes, not every irregular form), but it makes inflected searches like
``running`` → documents about *running* work as users expect. Because the
``QueryParser`` uses the field's analyzer, your queries are stemmed the same way
automatically. See the
`stemming & folding guide <https://priya-sundaram-dev.github.io/whoosh/docs/stemming.html>`_.

``ID`` and ``KEYWORD`` fields are case-sensitive and exact
----------------------------------------------------------

``ID`` fields are stored **verbatim** — not lowercased, not tokenized. That's the
point (they hold things like paths, slugs, and UUIDs), but it means matches are
exact and case-sensitive::

    schema = Schema(tag=ID)
    # document indexed with tag="Fiction"
    s.search(Term("tag", "Fiction"))   # 1 hit
    s.search(Term("tag", "fiction"))   # 0 hits — case matters for ID

If you want case-insensitive keyword matching, use
``KEYWORD(lowercase=True)``, or normalize the value yourself before indexing and
querying.

Special characters in my query raise a parse error
--------------------------------------------------

Characters like ``:``, ``[``, ``]``, ``~``, ``*``, ``(``, ``)``, and ``AND/OR``
have meaning in the query language. If you are passing **untrusted user input**
and want it treated as literal words, either catch the parse error and fall
back, or restrict the parser's plugins. A minimal parser with the fewest
surprises::

    from whoosh.qparser import QueryParser, PlusMinusPlugin
    qp = QueryParser("body", ix.schema)
    qp.remove_plugin_class(...)        # drop plugins you don't want to expose

See the `query-language reference
<https://priya-sundaram-dev.github.io/whoosh/docs/querylang.html>`_ for the full
grammar and which behaviours are opt-in plugins.

Range queries on numbers/dates return nothing
----------------------------------------------

Numeric and date range queries only work when the field is a
:class:`~whoosh.fields.NUMERIC` or :class:`~whoosh.fields.DATETIME` field — a
number stored in a ``TEXT`` field is indexed as text and won't compare
numerically. With the right field type, ranges work through the parser::

    schema = Schema(price=NUMERIC(stored=True), name=TEXT)
    qp = QueryParser("name", ix.schema)
    qp.parse("price:[0 to 50]")         # matches price 0..50 inclusive

For dates, add the ``DateParserPlugin`` so natural-language ranges parse. See the
`dates guide <https://priya-sundaram-dev.github.io/whoosh/docs/dates.html>`_.

Negative numbers lose their sign in a ``TEXT`` field
----------------------------------------------------

The default tokenizer used by every stock analyzer matches on ``\w+``, which does
**not** include ``-`` or ``+``. A leading sign is dropped, so in a ``TEXT`` field
``-100`` and ``100`` index to the same token::

    from whoosh.analysis import RegexTokenizer
    [t.text for t in RegexTokenizer()("balance -100 usd")]   # -> ['balance', '100', 'usd']

This is expected for prose (you rarely want ``-`` glued onto words), but it
surprises people indexing prices, deltas or temperatures. Two fixes, depending on
what you need:

* **You want to filter or range on the number** — store it in a
  :class:`~whoosh.fields.NUMERIC` field (use ``signed=True`` for negatives). Then
  ``NumericRange`` and ``price:[lo to hi]`` compare numerically, which is what you
  almost always want for quantities::

      schema = Schema(id=ID(stored=True), delta=NUMERIC(signed=True, stored=True))

* **You genuinely want the signed token searchable as text** — give the field a
  tokenizer whose pattern keeps the sign::

      from whoosh.analysis import RegexTokenizer
      signed = RegexTokenizer(r"[-+]?\w+(\.?\w+)*")
      schema = Schema(note=TEXT(analyzer=signed))
      [t.text for t in signed("balance -100 usd")]   # -> ['balance', '-100', 'usd']


Still stuck?
============

* Check the `quickstart <https://priya-sundaram-dev.github.io/whoosh/docs/quickstart.html>`_
  for an end-to-end example.
* Try your query in the `live browser demo
  <https://priya-sundaram-dev.github.io/whoosh/>`_ to isolate whether it's a
  schema/analyzer issue or something in your code.
* Search `existing issues <https://github.com/priya-sundaram-dev/whoosh/issues?q=is%3Aissue>`_,
  or open a new one with a small reproducer — a schema, one or two documents, and
  the query — and we'll take a look.
