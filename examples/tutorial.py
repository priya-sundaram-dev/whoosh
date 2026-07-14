"""Whoosh in 5 minutes — the whole tutorial as one runnable script.

Run me:  python examples/tutorial.py

Companion to TUTORIAL.md. Uses an in-memory index so it leaves nothing behind.
"""

import datetime

from whoosh.fields import Schema, TEXT, ID, KEYWORD, NUMERIC, DATETIME
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser, MultifieldParser
from whoosh import query, sorting


def build_index():
    # 1. Schema: what fields exist and how they behave.
    schema = Schema(
        id=ID(stored=True, unique=True),
        title=TEXT(stored=True),
        tags=KEYWORD(stored=True, commas=True, lowercase=True),
        price=NUMERIC(stored=True, sortable=True),
        added=DATETIME(stored=True, sortable=True),
    )

    # 2. In-memory index (nothing hits disk).
    ix = RamStorage().create_index(schema)

    # 3. Add documents, then commit.
    w = ix.writer()
    w.add_document(id="1", title="Cheap red widget", tags="red,widget",
                   price=5, added=datetime.datetime(2024, 1, 1))
    w.add_document(id="2", title="Premium blue widget", tags="blue,widget,premium",
                   price=50, added=datetime.datetime(2024, 6, 1))
    w.add_document(id="3", title="Red gadget deluxe", tags="red,gadget",
                   price=25, added=datetime.datetime(2024, 3, 1))
    w.commit()

    # update_document replaces the matching unique doc.
    w = ix.writer()
    w.update_document(id="1", title="Cheap red widget v2", tags="red,widget",
                      price=6, added=datetime.datetime(2024, 1, 2))
    w.commit()
    return ix


def main():
    ix = build_index()

    with ix.searcher() as s:
        # 4. Parse a user string and search, sorted by price.
        q = QueryParser("title", ix.schema).parse("widget")
        print("Search 'widget' (sorted by price):")
        for hit in s.search(q, sortedby="price"):
            print(f"  {hit['id']}  {hit['title']}  ${hit['price']}")

        # 5a. Search across multiple fields.
        mp = MultifieldParser(["title", "tags"], ix.schema)
        r = s.search(mp.parse("blue OR gadget"))
        print("\nMultifield 'blue OR gadget':", [h["id"] for h in r])

        # 5b. Exact-term filter + sort.
        r = s.search(query.Term("tags", "red"), sortedby="price")
        print("Tagged 'red' (by price):", [(h["id"], h["price"]) for h in r])

        # 5c. Facet counts per tag.
        facet = sorting.FieldFacet("tags", allow_overlap=True)
        r = s.search(query.Every(), groupedby=facet)
        counts = {tag: len(ids) for tag, ids in r.groups("tags").items()}
        print("Tag counts:", counts)

        # 6. Highlight the matched terms.
        r = s.search(QueryParser("title", ix.schema).parse("widget"))
        print("\nHighlights:")
        for hit in r:
            print("  ", hit.highlights("title"))


if __name__ == "__main__":
    main()
