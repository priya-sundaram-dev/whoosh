"""
Did-you-mean / spell-checking with Whoosh
==========================================

Whoosh has built-in spelling correction that most people never discover.
It works straight out of the index — no external dictionary or extra
dependency required. Two things you can do:

  1. suggest(fieldname, word)  -> alternative spellings for a single word.
  2. correct_query(query, text) -> a fully corrected query + a nicely
     formatted "Did you mean ...?" string.

Run it:

    python examples/did_you_mean.py

This whole script is self-contained and uses an in-memory index, so it
leaves nothing behind on disk.
"""

from whoosh import qparser
from whoosh.fields import Schema, TEXT, ID
from whoosh.filedb.filestore import RamStorage
from whoosh.highlight import HtmlFormatter


def build_index():
    # An in-memory index — perfect for demos and tests.
    schema = Schema(id=ID(stored=True), text=TEXT(stored=True))
    ix = RamStorage().create_index(schema)

    writer = ix.writer()
    docs = [
        ("1", "The quick brown fox jumps over the lazy dog"),
        ("2", "Mary had a little lamb whose fleece was white as snow"),
        ("3", "A journey of a thousand miles begins with a single step"),
        ("4", "To be or not to be, that is the question"),
        ("5", "All that glitters is not gold, and elephants never forget"),
    ]
    for doc_id, text in docs:
        writer.add_document(id=doc_id, text=text)
    writer.commit()
    return ix


def demo_single_word_suggestions(ix):
    print("=" * 60)
    print("1) Single-word suggestions via searcher.suggest()")
    print("=" * 60)
    with ix.searcher() as s:
        for misspelled in ("quik", "jorney", "eliphants", "questoin"):
            suggestions = s.suggest("text", misspelled, limit=3)
            print(f"  {misspelled!r:14} -> {suggestions}")
    print()


def demo_query_correction(ix):
    print("=" * 60)
    print("2) Whole-query correction via searcher.correct_query()")
    print("=" * 60)
    qp = qparser.QueryParser("text", ix.schema)

    for qtext in ("quik brown fox", "litle lamb", "thousend miles"):
        q = qp.parse(qtext)
        with ix.searcher() as s:
            correction = s.correct_query(q, qtext)
            corrected = correction.string
            if corrected and corrected != qtext:
                # Plain-text "did you mean" line.
                print(f"  You searched: {qtext!r}")
                print(f"  Did you mean: {corrected!r}")
                # And the same thing as HTML with the changed words wrapped
                # in <b> tags — handy for a web UI.
                hf = HtmlFormatter(tagname="b")
                print(f"  As HTML:      {correction.format_string(hf)}")
            else:
                print(f"  {qtext!r} looks fine, no correction needed.")
            print()


if __name__ == "__main__":
    ix = build_index()
    demo_single_word_suggestions(ix)
    demo_query_correction(ix)
    print("Tip: pass maxdist=1 for faster, stricter matching, or")
    print("prefix=1 to require the first letter to match (much faster).")
