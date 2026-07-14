"""Faceted navigation — sidebar filter counts and drill-down.

This is the pattern behind the "filter sidebar" on almost every shopping or
catalogue site: alongside the search results you show each facet (brand,
category, price band...) with a count of how many matching documents fall into
each bucket, and clicking a bucket narrows the result set.

Whoosh does this natively with :mod:`whoosh.sorting` facets and the
``groupedby`` argument to ``Searcher.search`` — no extra dependencies, and the
counts come straight out of the same search call that produces your results.

Run it::

    python examples/faceted_search.py

Concepts shown:

* :class:`whoosh.sorting.FieldFacet` for single-valued fields (``brand``)
* :class:`whoosh.sorting.FieldFacet` with ``allow_overlap=True`` for
  multi-valued KEYWORD fields (``tags``)
* :class:`whoosh.sorting.RangeFacet` for numeric buckets (``price``)
* combining a user query with a chosen facet value to "drill down"
* reading per-bucket counts from ``Results.groups()``
"""

from whoosh.fields import ID, KEYWORD, NUMERIC, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser
from whoosh.query import And, Every, Term
from whoosh.sorting import FieldFacet, RangeFacet

# A small product catalogue. In a real app these rows come from your database.
CATALOGUE = [
    # title, brand, tags (comma-separated), price
    ("Trail Runner GTX", "acme", "shoes,running,waterproof", 80),
    ("Road Racer Pro", "acme", "shoes,running", 120),
    ("Cozy Slipper", "globex", "shoes,home", 30),
    ("Hiking Boot Alpine", "initech", "shoes,hiking,waterproof", 150),
    ("Rain Jacket Shell", "acme", "outerwear,waterproof", 90),
    ("Down Puffer", "globex", "outerwear", 140),
    ("Everyday Sneaker", "initech", "shoes,casual", 60),
    ("Summit Backpack", "acme", "bags,hiking", 110),
]


def build_index():
    schema = Schema(
        title=TEXT(stored=True),
        brand=ID(stored=True),
        # commas=True lets one document carry several tags at once
        tags=KEYWORD(stored=True, commas=True, lowercase=True),
        price=NUMERIC(stored=True),
    )
    ix = RamStorage().create_index(schema)
    with ix.writer() as w:
        for title, brand, tags, price in CATALOGUE:
            w.add_document(title=title, brand=brand, tags=tags, price=price)
    return ix


# The facets we want to show in the sidebar. RangeFacet(field, start, stop,
# gap) buckets a numeric field into [start, start+gap), [start+gap, ...), ...
FACETS = {
    "brand": FieldFacet("brand"),
    "tags": FieldFacet("tags", allow_overlap=True),  # multi-valued
    "price": RangeFacet("price", 0, 200, 50),
}


def facet_counts(searcher, query):
    """Return {facet_name: {bucket: count}} for the given query."""
    results = searcher.search(query, groupedby=FACETS, limit=None)
    counts = {}
    for name in FACETS:
        groups = results.groups(name)
        counts[name] = {bucket: len(docnums) for bucket, docnums in groups.items()}
    return counts


def show(searcher, query, heading):
    print("\n" + heading)
    print("-" * len(heading))

    results = searcher.search(query, limit=None)
    print(f"{len(results)} result(s):")
    for hit in results:
        print(f"  - {hit['title']}  [{hit['brand']}, ${hit['price']}]")

    print("Facets you could filter by:")
    for name, buckets in facet_counts(searcher, query).items():
        pretty = ", ".join(f"{b} ({c})" for b, c in sorted(buckets.items(), key=str))
        print(f"  {name:6}: {pretty}")


def main():
    ix = build_index()
    with ix.searcher() as s:
        # 1. No query yet: show the whole catalogue with facet counts.
        show(s, Every(), "All products")

        # 2. A text search. Facet counts now reflect only the matching set.
        qp = QueryParser("tags", schema=ix.schema)
        waterproof = qp.parse("waterproof")
        show(s, waterproof, "Search: tags:waterproof")

        # 3. Drill down: the user clicked the "acme" brand facet, so AND the
        #    chosen facet value onto the current query.
        drilldown = And([waterproof, Term("brand", "acme")])
        show(s, drilldown, "Search: waterproof  +  brand:acme")


if __name__ == "__main__":
    main()
