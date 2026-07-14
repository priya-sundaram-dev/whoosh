"""
Search-as-you-type / autocomplete with Whoosh
==============================================

One of the most common real-world search features is autocomplete: as the
user types, you show live suggestions. Whoosh gives you several pure-Python,
zero-dependency ways to build this. This example demonstrates three, from
simplest to most powerful:

  1. Term completion   -- complete the *word* being typed (reader.expand_prefix)
  2. Prefix search     -- match documents whose field starts with the input
  3. N-gram matching   -- fuzzy "matches anywhere" suggestions as-you-type

Run it:  python examples/autocomplete.py

Everything here runs in memory (RamStorage) so there are no files to clean up.
"""

from whoosh.analysis import NgramWordAnalyzer
from whoosh.fields import Schema, TEXT, STORED
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser
from whoosh.query import Prefix

TITLES = [
    "Python programming for beginners",
    "Pythonic patterns and idioms",
    "PyTorch deep learning tutorial",
    "JavaScript: the good parts",
    "Java concurrency in practice",
    "Rust systems programming",
    "Programming Elixir",
]


def build_index():
    """One index, three fields -- each field powers one autocomplete strategy.

    - ``title``       : a normal analyzed field (for prefix + term completion)
    - ``title_ngram`` : n-gram indexed for fuzzy "contains as-you-type" matching
    - ``title_store`` : the original text, stored so we can display results
    """
    schema = Schema(
        title=TEXT(stored=True, spelling=True),
        title_ngram=TEXT(analyzer=NgramWordAnalyzer(minsize=2, maxsize=8), phrase=False),
        title_store=STORED,
    )
    ix = RamStorage().create_index(schema)
    writer = ix.writer()
    for t in TITLES:
        writer.add_document(title=t, title_ngram=t, title_store=t)
    writer.commit()
    return ix


def complete_word(searcher, prefix):
    """Strategy 1: complete the single word currently being typed.

    Great for a single-line search box where you want to finish the last word.
    ``reader.expand_prefix`` walks the term index, so it is fast even on large
    vocabularies.
    """
    reader = searcher.reader()
    terms = set()
    for term in reader.expand_prefix("title", prefix.lower()):
        # expand_prefix yields raw (bytes) terms; decode for display
        terms.add(term.decode("utf-8") if isinstance(term, bytes) else term)
    return sorted(terms)


def complete_prefix(searcher, prefix):
    """Strategy 2: find documents whose title starts with the typed text.

    A :class:`whoosh.query.Prefix` query matches on the *term* level, so this
    matches any title that contains a word starting with ``prefix``.
    """
    query = Prefix("title", prefix.lower())
    return [hit["title"] for hit in searcher.search(query, limit=10)]


def complete_ngram(searcher, text):
    """Strategy 3: fuzzy "matches anywhere" suggestions.

    N-gram indexing lets a partial, mid-word query still match -- ideal for
    tolerant, typo-friendly as-you-type suggestions ("prog" -> "programming").
    """
    parser = QueryParser("title_ngram", schema=searcher.schema)
    query = parser.parse(text.lower())
    return [hit["title_store"] for hit in searcher.search(query, limit=10)]


def main():
    ix = build_index()
    with ix.searcher() as searcher:
        print("=== 1. Term completion (finish the current word) ===")
        for prefix in ("py", "prog", "jav"):
            print(f"  {prefix!r:8} -> {complete_word(searcher, prefix)}")

        print("\n=== 2. Prefix search (titles starting with...) ===")
        for prefix in ("py", "prog"):
            print(f"  {prefix!r:8} -> {complete_prefix(searcher, prefix)}")

        print("\n=== 3. N-gram matching (fuzzy, matches anywhere) ===")
        for text in ("prog", "yth", "concur"):
            print(f"  {text!r:8} -> {complete_ngram(searcher, text)}")


if __name__ == "__main__":
    main()
