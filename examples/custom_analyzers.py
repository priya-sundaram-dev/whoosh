"""Custom analyzers: compose your own text-processing pipeline.

An *analyzer* turns a string into a stream of indexable tokens. Whoosh ships
several ready-made analyzers, but its real power is that you can build your own
by composing a tokenizer with a chain of filters using the ``|`` operator::

    analyzer = RegexTokenizer() | LowercaseFilter() | StopFilter()

The first item must be a tokenizer; every item after it must be a filter. This
script walks through the building blocks and shows how to attach a custom
analyzer to a field so that both indexing and querying use the same pipeline.

Run it end to end::

    python examples/custom_analyzers.py

It uses only the standard library plus Whoosh — no extra dependencies.
"""

from whoosh.analysis import (
    CharsetFilter,
    LowercaseFilter,
    NgramFilter,
    RegexTokenizer,
    StemFilter,
    StopFilter,
    SubstitutionFilter,
)
from whoosh.fields import ID, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser
from whoosh.support.charset import accent_map


def tokens(analyzer, text):
    """Return the list of token *texts* an analyzer produces for a string."""
    return [t.text for t in analyzer(text)]


def demo_building_blocks():
    print("=" * 70)
    print("1. Composing a pipeline with the | operator")
    print("=" * 70)

    text = "The Quick, Brown FOXES are Running!"

    # A bare tokenizer just splits on a regex (default: runs of word chars).
    tok = RegexTokenizer()
    print("tokenizer only:      ", tokens(tok, text))

    # Add a lowercase filter.
    lower = RegexTokenizer() | LowercaseFilter()
    print("+ lowercase:         ", tokens(lower, text))

    # Drop very common words. StopFilter has a sensible default English list.
    nostop = RegexTokenizer() | LowercaseFilter() | StopFilter()
    print("+ stop words:        ", tokens(nostop, text))

    # Reduce words to their stems so "running" matches "run".
    stemmed = RegexTokenizer() | LowercaseFilter() | StopFilter() | StemFilter()
    print("+ stemming:          ", tokens(stemmed, text))


def demo_accent_folding():
    print()
    print("=" * 70)
    print("2. Accent folding, so 'cafe' matches 'café'")
    print("=" * 70)

    # CharsetFilter with the bundled accent_map maps accented characters to
    # their plain ASCII equivalents. Great for search over names and loanwords.
    analyzer = RegexTokenizer() | LowercaseFilter() | CharsetFilter(accent_map)
    for word in ["Café", "naïve", "Zürich", "jalapeño"]:
        print(f"  {word!r:12} -> {tokens(analyzer, word)}")


def demo_substitution():
    print()
    print("=" * 70)
    print("3. Normalising tokens with a SubstitutionFilter")
    print("=" * 70)

    # Fold internal punctuation so "wi-fi", "wi_fi" and "wifi" all match.
    analyzer = (
        RegexTokenizer(r"\S+")
        | SubstitutionFilter(r"[-_]", "")
        | LowercaseFilter()
    )
    for word in ["Wi-Fi", "wi_fi", "WIFI"]:
        print(f"  {word!r:10} -> {tokens(analyzer, word)}")


def demo_ngrams():
    print()
    print("=" * 70)
    print("4. N-grams for substring / 'matches anywhere' search")
    print("=" * 70)

    # Emit overlapping character n-grams so a search for "sea" hits "search".
    analyzer = RegexTokenizer() | LowercaseFilter() | NgramFilter(minsize=3, maxsize=4)
    print("  'search' ->", tokens(analyzer, "search"))


def demo_in_a_real_index():
    print()
    print("=" * 70)
    print("5. Attaching a custom analyzer to a field")
    print("=" * 70)

    # Build one analyzer and reuse it for the field. Whoosh stores the analyzer
    # on the field, so the *same* pipeline runs at index time and query time —
    # that consistency is what makes "café" find "Cafe" below.
    text_analyzer = (
        RegexTokenizer()
        | LowercaseFilter()
        | CharsetFilter(accent_map)
        | StopFilter()
        | StemFilter()
    )

    schema = Schema(id=ID(stored=True), body=TEXT(analyzer=text_analyzer, stored=True))
    ix = RamStorage().create_index(schema)

    docs = [
        ("1", "The cafés in Zürich are running a naïve promotion."),
        ("2", "A quick brown fox jumps over the lazy dogs."),
        ("3", "Runners run; a runner ran the marathon."),
    ]
    with ix.writer() as w:
        for doc_id, body in docs:
            w.add_document(id=doc_id, body=body)

    with ix.searcher() as s:
        qp = QueryParser("body", ix.schema)
        for query_text in ["cafe", "run", "ZURICH"]:
            q = qp.parse(query_text)
            hits = s.search(q)
            found = sorted(h["id"] for h in hits)
            print(f"  search {query_text!r:8} -> docs {found}")

    print()
    print("  Note: because the field's analyzer stems and folds accents at BOTH")
    print("  index and query time, 'cafe' matches 'cafés', 'run' matches")
    print("  'running/runner/ran', and 'ZURICH' matches 'Zürich'.")


if __name__ == "__main__":
    demo_building_blocks()
    demo_accent_folding()
    demo_substitution()
    demo_ngrams()
    demo_in_a_real_index()
