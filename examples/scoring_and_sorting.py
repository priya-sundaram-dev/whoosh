"""Custom scoring & sorting in Whoosh.

Ranking is where a search library earns its keep. Whoosh gives you three
independent levers, and this recipe walks through each one end to end:

    1. Tune the built-in BM25F model (global and *per-field* B / K1).
    2. Swap in a different scoring model entirely (TF-IDF, Frequency), or mix
       models per field with MultiWeighting.
    3. Score with your own Python function via FunctionWeighting -- great for
       experiments and business rules (e.g. "boost by position").
    4. Ignore relevance and sort by a field instead (sortedby=...), which is
       both faster and often what users actually want ("newest first").

Every block below runs against a real in-memory index and prints its result,
so you can see exactly what each lever does.

Run it:  python examples/scoring_and_sorting.py

Part of the Whoosh revival maintained by Priya Sundaram (an AI maintainer).
"""

from whoosh import scoring
from whoosh.fields import NUMERIC, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser


def build_index():
    """A tiny corpus where title and body both mention the query term, so
    per-field tuning and field-mixing have something visible to do."""
    schema = Schema(
        title=TEXT(stored=True),
        body=TEXT(stored=True),
        views=NUMERIC(stored=True, sortable=True),
    )
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(
        title="Python search",
        body="A short note about search in python.",
        views=10,
    )
    w.add_document(
        title="Cooking with python",
        body="python python python python -- a body that mentions python a lot.",
        views=500,
    )
    w.add_document(
        title="Snakes",
        body="The python is a large snake; the word python appears twice here.",
        views=42,
    )
    w.commit()
    return ix


def show(label, results):
    print(f"\n{label}")
    for hit in results:
        print(f"    {hit.score:8.4f}  {hit['title']!r}")


def main():
    ix = build_index()
    qp = QueryParser("body", schema=ix.schema)
    q = qp.parse("python")

    # ------------------------------------------------------------------ #
    # 1. Default BM25F.
    # ------------------------------------------------------------------ #
    with ix.searcher() as s:  # weighting defaults to scoring.BM25F
        show("1. Default BM25F (B=0.75, K1=1.2)", s.search(q))

    # ------------------------------------------------------------------ #
    # 2. Tune BM25F. B controls length normalisation (0 = ignore doc
    #    length, 1 = full normalisation). K1 controls term-frequency
    #    saturation. Field-specific values use the `<field>_B` keyword.
    # ------------------------------------------------------------------ #
    with ix.searcher(weighting=scoring.BM25F(B=0.0, K1=2.0)) as s:
        # B=0 removes length penalty, so the long spammy doc floats up.
        show("2a. BM25F with B=0.0 (no length normalisation), K1=2.0", s.search(q))

    with ix.searcher(weighting=scoring.BM25F(B=0.75, body_B=0.2)) as s:
        # Relax length normalisation for the `body` field only.
        show("2b. BM25F with per-field body_B=0.2", s.search(q))

    # ------------------------------------------------------------------ #
    # 3. A completely different model. Frequency ranks purely by raw term
    #    count; TF-IDF weights by inverse document frequency.
    # ------------------------------------------------------------------ #
    with ix.searcher(weighting=scoring.Frequency()) as s:
        show("3a. Frequency model (raw term counts)", s.search(q))

    with ix.searcher(weighting=scoring.TF_IDF()) as s:
        show("3b. TF-IDF model", s.search(q))

    # Mix models per field: TF-IDF for titles, BM25F everywhere else.
    mixed = scoring.MultiWeighting(scoring.BM25F(), title=scoring.TF_IDF())
    with ix.searcher(weighting=mixed) as s:
        show("3c. MultiWeighting: TF-IDF for title, BM25F default", s.search(q))

    # ------------------------------------------------------------------ #
    # 4. Score with your own function. The function receives
    #    (searcher, fieldname, text, matcher) and returns a float. Here we
    #    reward documents where the term appears *earliest*.
    # ------------------------------------------------------------------ #
    def earliest_position(searcher, fieldname, text, matcher):
        positions = matcher.value_as("positions")
        return 1.0 / (positions[0] + 1) if positions else 0.0

    with ix.searcher(weighting=scoring.FunctionWeighting(earliest_position)) as s:
        show("4. FunctionWeighting: boost earliest position", s.search(q))

    # ------------------------------------------------------------------ #
    # 5. Skip relevance entirely -- sort by a stored, sortable field.
    #    `sortedby` is faster than scoring and is what "newest first" or
    #    "most viewed" UIs really need. Add reverse=True to flip order.
    # ------------------------------------------------------------------ #
    with ix.searcher() as s:
        results = s.search(q, sortedby="views", reverse=True)
        print("\n5. sortedby='views', reverse=True (ignores relevance)")
        for hit in results:
            print(f"    views={hit['views']:>4}  {hit['title']!r}")


if __name__ == "__main__":
    main()
