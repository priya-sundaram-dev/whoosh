=====================================================
How to tune relevance (why is my "best" result last?)
=====================================================

You wired up search, typed a query, and the result you *expected* to rank first
came in last. This is the most common complaint about any search feature, and
it is almost never a bug -- it is a ranking decision the library made on your
behalf. With Whoosh every one of those decisions is a knob you can turn, and you
can *see* the score that produced the order (``result.score``).

This page is a practical tour of the four levers that actually move results, in
the order you should reach for them. Every snippet and every score below is
produced by the current release.


A tiny corpus that misbehaves
=============================

::

    from whoosh.fields import Schema, TEXT, ID
    from whoosh.filedb.filestore import RamStorage
    from whoosh.qparser import MultifieldParser

    schema = Schema(title=TEXT(stored=True), body=TEXT(stored=True), id=ID(stored=True))
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    docs = [
        ("1", "python tutorial for beginners", "A friendly walkthrough of variables, loops and functions."),
        ("2", "cooking with a snake",          "python python python python python python python everywhere here."),
        ("3", "advanced metaclasses",          "deep dive python internals, python descriptors, python python."),
    ]
    for i, t, b in docs:
        w.add_document(id=i, title=t, body=b)
    w.commit()

    with ix.searcher() as s:
        q = MultifieldParser(["title", "body"], schema=ix.schema).parse("python")
        print([(r["id"], round(r.score, 3)) for r in s.search(q, limit=None)])
    # [('2', 1.832), ('3', 1.666), ('1', 1.258)]

Doc 1 is the *actual python tutorial*. It comes dead last, because doc 2 (about
snakes) and doc 3 (metaclasses) simply say "python" more often in their bodies.
This is the problem we are going to fix, one lever at a time.


Lever 1: field boosts (structure beats frequency)
=================================================

A match in the **title** should count for more than a match buried in the body.
Declare that once, at schema time, with ``field_boost``::

    schema = Schema(
        title=TEXT(stored=True, field_boost=2.0),  # a title hit is worth double
        body=TEXT(stored=True),
        id=ID(stored=True),
    )

Re-index and search again::

    [('2', 1.832), ('1', 1.789), ('3', 1.666)]

Doc 1 climbs from last to second, nudging past the metaclasses post purely
because "python" sits in its title. Field boosts are the single highest-leverage
tuning you can do, because they encode *what your data means*: titles, tags and
headings are stronger signals than body text, and you almost always know that up
front.


Lever 2: length normalization (stop rewarding keyword stuffing)
===============================================================

Doc 2 still leads -- because :class:`~whoosh.scoring.BM25F`, Whoosh's default
scoring, rewards term frequency. But it also ships a defence against keyword
stuffing called length normalization, governed by the parameter **B** (0.0-1.0,
default 0.75). Turn it off and long, repetitive documents stop getting a free
pass::

    from whoosh import scoring

    # on the field-boosted index from Lever 1:
    with ix.searcher(weighting=scoring.BM25F(B=0.0)) as s:  # ignore document length
        ...
    # [('1', 1.933), ('2', 1.878), ('3', 1.692)]

There it is: the tutorial finally ranks #1. ``B=0.0`` means "document length
does not matter", so doc 2 no longer profits from cramming "python" seven times
into one line. The companion knob, **K1** (default 1.2), controls how fast
repeated terms hit diminishing returns -- lower it toward zero and the 2nd, 3rd,
4th occurrence of a word barely helps. If one loud document keeps drowning out
concise, precise ones, that is your pair of dials: raise ``B`` *or* lower ``K1``.


Lever 3: per-field scoring with MultiWeighting
==============================================

``B=0.0`` everywhere is a blunt instrument -- you probably want *no* length
penalty on short titles but a *strong* one on long, rambling bodies.
:class:`~whoosh.scoring.MultiWeighting` lets you set different rules per field,
stacked on top of your field boost::

    from whoosh import scoring
    from whoosh.query import Term, Or

    mw = scoring.MultiWeighting(
        scoring.BM25F(B=0.75),        # default for any field not named below
        title=scoring.BM25F(B=0.0),   # titles are short; don't length-normalize
        body=scoring.BM25F(B=1.0),    # bodies vary wildly; normalize hard
    )
    with ix.searcher(weighting=mw) as s:   # field_boost=2.0 still on the title
        q = Or([Term("title", "python"), Term("body", "python")])
        print([(r["id"], round(r.score, 3)) for r in s.search(q, limit=None)])
    # [('1', 1.933), ('2', 1.818), ('3', 1.658)]

Doc 1 holds first place, and now you are not just doubling a number -- you are
saying titles and bodies obey different physics, which is the honest version of
"the title matters more".


Lever 4: query-time boosts (context you only know at search time)
=================================================================

The first three levers are baked into the index or the searcher. But sometimes a
field's importance depends on *this* query -- a search box that knows the user is
really after a tag, say. Boost individual query terms at search time::

    from whoosh.query import Term, Or

    # weight the title match 3x for THIS query only
    q = Or([Term("title", "python", boost=3.0), Term("body", "python")])

::

    no boost:          [('2', 1.832), ('3', 1.666), ('1', 1.258)]
    title boost 3.0:   [('1', 3.775), ('2', 1.832), ('3', 1.666)]

The query parser understands this too -- the string ``python^3 tutorial`` parses
to a boosted term, so you can even hand this dial to power users inside the
search box.


How to actually tune, without guessing forever
===============================================

#. **Start with structure, not scoring math.** Set ``field_boost`` on
   titles/tags first -- it fixes most "wrong best result" complaints on its own.
#. **Only then touch B and K1**, and change one at a time.
#. **Write down 5-10 real queries and the result you want ranked #1.** Print
   scores like the snippets above and watch the *whole* ordering as you turn a
   knob -- a change that helps one query often quietly hurts another.
#. **Reach for** :class:`~whoosh.scoring.MultiWeighting` **once your fields
   genuinely differ** in length and importance.

Relevance tuning feels like a dark art mostly because most engines hide the
score. Whoosh does not: ``r.score`` is right there, every weighting class is a
few lines of readable Python you can read or subclass, and the whole thing runs
in-process with no cluster to babysit. Start with a title boost, keep a list of
test queries, and turn one dial at a time.

.. seealso::

   :doc:`searching` for the scoring/sorting API, and the
   :mod:`whoosh.scoring` module reference for every weighting model.
