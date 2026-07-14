# Whoosh in 5 minutes

A hands-on tour of full-text search with Whoosh. Every snippet below is real,
runnable code — copy it into a Python file and go. No database, no server, no
compiler: Whoosh is pure Python.

> New here? Install with `pip install whoosh3`, then follow along.
> A single runnable script version of this tutorial lives at
> [`examples/tutorial.py`](examples/tutorial.py).

## 1. Define a schema

A **schema** lists your fields and how each one is treated. The field *type*
decides whether a field is tokenized for full-text search (`TEXT`), matched
exactly (`ID`, `KEYWORD`), or sorted/filtered as a number or date (`NUMERIC`,
`DATETIME`).

```python
from whoosh.fields import Schema, TEXT, ID, KEYWORD, NUMERIC, DATETIME

schema = Schema(
    id=ID(stored=True, unique=True),   # exact, one-per-doc key
    title=TEXT(stored=True),           # analyzed: tokenized + lowercased
    tags=KEYWORD(stored=True, commas=True, lowercase=True),
    price=NUMERIC(stored=True, sortable=True),
    added=DATETIME(stored=True, sortable=True),
)
```

- `stored=True` keeps the original value so you can read it back from a hit.
- `unique=True` lets `update_document` replace a doc by its key.
- `sortable=True` builds a column so you can sort/facet on the field.

## 2. Create an index

An index is just a directory of files. Use `create_in` for an on-disk index:

```python
import os
from whoosh.index import create_in

os.makedirs("indexdir", exist_ok=True)
ix = create_in("indexdir", schema)
```

Prefer a throwaway, in-memory index for tests and small caches:

```python
from whoosh.filedb.filestore import RamStorage

ix = RamStorage().create_index(schema)   # nothing touches disk
```

## 3. Add documents

Open a writer, add documents, and `commit()`:

```python
import datetime

w = ix.writer()
w.add_document(id="1", title="Cheap red widget", tags="red,widget",
               price=5, added=datetime.datetime(2024, 1, 1))
w.add_document(id="2", title="Premium blue widget", tags="blue,widget,premium",
               price=50, added=datetime.datetime(2024, 6, 1))
w.add_document(id="3", title="Red gadget deluxe", tags="red,gadget",
               price=25, added=datetime.datetime(2024, 3, 1))
w.commit()
```

Changed your mind about a document? Because `id` is `unique`, `update_document`
replaces the matching one (or inserts it if new):

```python
w = ix.writer()
w.update_document(id="1", title="Cheap red widget v2", tags="red,widget",
                  price=6, added=datetime.datetime(2024, 1, 2))
w.commit()
```

## 4. Search

Turn a user's search string into a query with `QueryParser`, then search inside
a `with` block so the searcher is closed for you:

```python
from whoosh.qparser import QueryParser

with ix.searcher() as s:
    q = QueryParser("title", ix.schema).parse("widget")
    for hit in s.search(q, sortedby="price"):
        print(hit["id"], hit["title"], hit["price"])
```

The parser understands the usual operators out of the box: `red AND widget`,
`blue OR gadget`, `widget NOT premium`, quoted `"red widget"` phrases, and
wildcards like `wid*`.

## 5. Filter, sort, and facet

Search more than one field at once with `MultifieldParser`:

```python
from whoosh.qparser import MultifieldParser

with ix.searcher() as s:
    mp = MultifieldParser(["title", "tags"], ix.schema)
    results = s.search(mp.parse("blue OR gadget"))
    print([h["id"] for h in results])
```

Match an exact term without the parser, and sort results by any sortable field:

```python
from whoosh import query

with ix.searcher() as s:
    results = s.search(query.Term("tags", "red"), sortedby="price")
    print([(h["id"], h["price"]) for h in results])
```

Group results into facets — here, count documents per tag:

```python
from whoosh import sorting, query

with ix.searcher() as s:
    facet = sorting.FieldFacet("tags", allow_overlap=True)
    results = s.search(query.Every(), groupedby=facet)
    counts = {tag: len(ids) for tag, ids in results.groups("tags").items()}
    print(counts)
```

## 6. Highlight matches

Show users *why* a document matched by highlighting the query terms in context:

```python
from whoosh.qparser import QueryParser

with ix.searcher() as s:
    q = QueryParser("title", ix.schema).parse("widget")
    results = s.search(q)
    for hit in results:
        print(hit.highlights("title"))
```

## Where to next?

- **Full reference docs:** the `docs/` directory (Sphinx) covers analyzers,
  custom scoring (BM25F and friends), spelling correction, sorting, and more.
- **Runnable examples:** [`examples/`](examples/) — start with
  [`quickstart.py`](examples/quickstart.py) and [`tutorial.py`](examples/tutorial.py).
- **Live demo:** try searching in your browser (no install) on the project's
  GitHub Pages site.

Have a question or found a bug? Open an issue — this project is actively
maintained again and issues get answered.

---
<sub>Maintained by Priya Sundaram. Priya is an AI system that maintains this
project; documentation and code are reviewed before release.</sub>
