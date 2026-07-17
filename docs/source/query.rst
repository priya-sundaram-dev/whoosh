=============
Query objects
=============

.. highlight:: python

The classes in the :mod:`whoosh.query` module implement the *queries* you can run
against an index. When a user types a search string, Whoosh's :doc:`query parser
<querylang>` turns it into a tree of these objects. You can also skip the parser
entirely and build query objects yourself — this is useful when you're
constructing queries in code (for example, filters, faceting, or an "advanced
search" form) and don't want to serialize your intent to a string just to parse
it back again.

See :doc:`searching` for how to run a query once you've built it, and
:doc:`querylang` for the text syntax the parser understands.


Building queries in code
========================

Every query is an object. The simplest is :class:`whoosh.query.Term`, which
matches documents containing a single term in a single field::

    from whoosh.query import Term

    myquery = Term("content", "hobbit")

The first argument is the field name and the second is the term text. You pass a
query object straight to :meth:`~whoosh.searching.Searcher.search`::

    with ix.searcher() as searcher:
        results = searcher.search(Term("content", "hobbit"))

Compound queries take a *list* of sub-queries. For example,
:class:`~whoosh.query.And` matches documents that match *all* of its
sub-queries, and :class:`~whoosh.query.Or` matches documents that match *any* of
them::

    from whoosh.query import And, Or, Term

    # content:quick AND content:fox
    q = And([Term("content", "quick"), Term("content", "fox")])

    # content:quick OR content:lazy
    q = Or([Term("content", "quick"), Term("content", "lazy")])

Because the sub-queries are just objects, you can nest them to any depth::

    # (content:quick OR content:fast) AND content:fox
    q = And([
        Or([Term("content", "quick"), Term("content", "fast")]),
        Term("content", "fox"),
    ])


Combining queries with operators
================================

For convenience, query objects support the ``&`` (and), ``|`` (or), and ``-``
(and-not) operators, so the nested example above can be written more compactly::

    q = (Term("content", "quick") | Term("content", "fast")) & Term("content", "fox")

    # content:brown AND NOT content:fox
    q = Term("content", "brown") - Term("content", "fox")

.. note::

   Query objects do **not** support the unary ``~`` operator. To negate a query,
   wrap it in :class:`whoosh.query.Not` explicitly::

       from whoosh.query import Not, Term

       q = Term("content", "brown") & Not(Term("content", "fox"))

   (This is equivalent to the ``-`` operator shown above.)


A tour of the query classes
===========================

Whoosh ships a query type for each kind of matching. The most commonly used are:

============================================  ==================================================
Class                                         Matches
============================================  ==================================================
:class:`~whoosh.query.Term`                   A single term in a field.
:class:`~whoosh.query.And`                    Documents matching *all* sub-queries.
:class:`~whoosh.query.Or`                     Documents matching *any* sub-query.
:class:`~whoosh.query.Not`                    Documents *not* matching the wrapped query.
:class:`~whoosh.query.Phrase`                 A sequence of terms in order in one field.
:class:`~whoosh.query.Prefix`                 Terms starting with a given prefix.
:class:`~whoosh.query.Wildcard`               Terms matching a ``?``/``*`` glob pattern.
:class:`~whoosh.query.Regex`                  Terms matching a regular expression.
:class:`~whoosh.query.FuzzyTerm`              Terms within an edit distance of the given text.
:class:`~whoosh.query.Variations`             Morphological variations of a word.
:class:`~whoosh.query.TermRange`              Terms in a lexical range.
:class:`~whoosh.query.NumericRange`           Numeric values in a range.
:class:`~whoosh.query.DateRange`              Datetime values in a range.
:class:`~whoosh.query.Every`                  Every document (optionally with a value in a field).
============================================  ==================================================

Some examples::

    from whoosh.query import Phrase, Prefix, Wildcard, FuzzyTerm

    # content:"all was well"  (the words in order)
    Phrase("content", ["all", "was", "well"])

    # content:render*  (terms beginning with "render")
    Prefix("content", "render")

    # content:comp*t?on
    Wildcard("content", "comp*t?on")

    # content:render~2  (within edit distance 2 of "render")
    FuzzyTerm("content", "render", maxdist=2)

Range queries take low and high bounds::

    from whoosh.query import TermRange, NumericRange

    # title:[apple TO banana]
    TermRange("title", "apple", "banana")

    # price:[10 TO 100]
    NumericRange("price", 10, 100)

For a complete list — including the span queries, binary queries such as
:class:`~whoosh.query.AndMaybe` and :class:`~whoosh.query.Require`, and the
nested-document queries — see the :doc:`api/query` reference.


Boosting a query
================

Most query objects accept a ``boost`` keyword to weight matches higher (or
lower) in the score::

    # Matches on the title count for twice as much as usual.
    Term("title", "python", boost=2.0)

You can boost any query, including compound ones::

    Or([Term("content", "python"), Term("content", "django")], boost=1.5)


Inspecting queries
==================

Query objects are introspectable, which is handy for debugging or for building
tooling on top of Whoosh.

``str(query)`` renders the query in the default query language::

    >>> str(And([Term("content", "quick"), Term("content", "fox")]))
    '(content:quick AND content:fox)'

:meth:`~whoosh.query.Query.leaves` yields the leaf (non-compound) sub-queries::

    >>> q = And([Term("c", "x"), Or([Term("c", "y"), Term("d", "z")])])
    >>> [str(leaf) for leaf in q.leaves()]
    ['c:x', 'c:y', 'd:z']

:meth:`~whoosh.query.Query.all_terms` returns the set of ``(fieldname, text)``
pairs used anywhere in the query::

    >>> q.all_terms()
    {('c', 'x'), ('c', 'y'), ('d', 'z')}

.. note::

   Calling ``.terms()`` on a *compound* query returns an empty list — it only
   reports terms attached directly to a leaf node. Use ``.all_terms()`` (or
   ``.leaves()``) to walk the whole tree.

:meth:`~whoosh.query.Query.normalize` simplifies a query by collapsing
redundant structure, which the searcher does for you before running a search::

    >>> str(And([Term("c", "x")]).normalize())
    'c:x'


Mixing parsed and hand-built queries
====================================

The query parser produces the same objects, so you can freely combine a parsed
query with one you build yourself. A common pattern is to let users type a free
query and then AND it with a filter you control::

    from whoosh.qparser import QueryParser
    from whoosh.query import Term

    user_q = QueryParser("content", ix.schema).parse(user_input)
    q = user_q & Term("category", "news")

    with ix.searcher() as searcher:
        results = searcher.search(q)

You can also pass a query object as the ``filter`` argument to
:meth:`~whoosh.searching.Searcher.search`, which restricts (and caches) the
result set without affecting scores — see :doc:`searching`.
