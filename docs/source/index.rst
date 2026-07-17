==============================
Whoosh |release| documentation
==============================

Whoosh is a fast, pure-Python full-text indexing, search, and spell-checking
library. It adds ranked search — a query language, faceting, highlighting, and
"did you mean?" spelling correction — to any Python program, with **no
compiler, no server, and no native dependencies**. If you can open a file, you
can build an index.

**Try it live in your browser** — no install needed — at the
`interactive demo <https://priya-sundaram-dev.github.io/whoosh/>`_. It runs the
real library compiled to WebAssembly (via Pyodide) and answers your queries with
BM25 ranking and highlighting, entirely client-side.

New here? Start with the :doc:`quickstart`.

.. admonition:: Project status (2026): actively maintained again

    This fork continues Whoosh — originally created by
    `Matt Chaput <mailto:matt@whoosh.ca>`_ — after two rounds of abandonment,
    now running on Python 3.9–3.14. Install it as ``pip install whoosh3``.
    You can report bugs and request features on the
    `issue tracker <https://github.com/priya-sundaram-dev/whoosh/issues>`_ and
    ask questions in
    `Discussions <https://github.com/priya-sundaram-dev/whoosh/discussions>`_.
    If Whoosh is useful to you, a ⭐ on
    `GitHub <https://github.com/priya-sundaram-dev/whoosh>`_ helps other people
    find a search library that's alive again.


Contents
========

.. toctree::
    :maxdepth: 2

    releases/index
    quickstart
    cli
    comparison
    integrations
    cookbook
    intro
    glossary
    schema
    indexing
    searching
    parsing
    querylang
    dates
    query
    analysis
    stemming
    ngrams
    facets
    highlight
    keywords
    spelling
    fieldcaches
    batch
    threads
    nested
    recipes
    api/api
    tech/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
