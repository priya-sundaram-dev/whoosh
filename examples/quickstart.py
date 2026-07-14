"""Whoosh quickstart: index a few documents and search them.

Run me:  python examples/quickstart.py

This is the whole loop, end to end, in one file:
  1. define a schema,
  2. create an index,
  3. add documents,
  4. parse a query and search.
"""

import os.path
import tempfile

from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in
from whoosh.qparser import QueryParser

# 1. A schema describes the fields each document has and how they are handled.
#    - TEXT is analyzed (tokenized, lowercased) and full-text searchable.
#    - stored=True means we can read the value back from search results.
schema = Schema(
    title=TEXT(stored=True),
    path=ID(stored=True),
    content=TEXT(stored=True),
)

# 2. An index lives in a directory. Here we use a throwaway temp dir.
index_dir = tempfile.mkdtemp(prefix="whoosh-quickstart-")
ix = create_in(index_dir, schema)

# 3. Add some documents.
docs = [
    ("First document", "/a", "This is the first document we've added!"),
    ("Second document", "/b", "The second one is even more interesting!"),
    ("Third document", "/c", "Pure-Python full text search, no compiler required."),
]
writer = ix.writer()
for title, path, content in docs:
    writer.add_document(title=title, path=path, content=content)
writer.commit()

# 4. Search. The QueryParser turns a user string into a query object.
with ix.searcher() as searcher:
    query = QueryParser("content", ix.schema).parse("first OR python")
    results = searcher.search(query)
    print(f"Query: {query}")
    print(f"Matched {len(results)} document(s):")
    for hit in results:
        print(f"  - {hit['title']}  ({hit['path']})")
        print(f"      {hit.highlights('content')}")

print(f"\n(Index written to {os.path.abspath(index_dir)})")
