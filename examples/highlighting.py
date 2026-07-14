"""Search-result highlighting and snippets with Whoosh.

Run:  python examples/highlighting.py

Shows how to turn raw matches into the kind of "keyword-in-context" snippets
you see on a real search-results page:

  1. Basic highlighting straight off a Hit (HTML <b> tags).
  2. Choosing *where* snippets are cut (ContextFragmenter vs SentenceFragmenter).
  3. Choosing *how* matches are marked (HtmlFormatter classes, UppercaseFormatter).
  4. Plain-text marking with UppercaseFormatter (for terminals or logs).
  5. Fast "pinpoint" highlighting for large documents: store character
     positions in the field (``chars=True``) and use PinpointFragmenter so
     Whoosh never has to re-tokenize the text.
  6. Highlighting a field you did *not* store, by passing the text back in.

Everything here runs against an in-memory index, so there are no files to
clean up.
"""

from whoosh import highlight
from whoosh.analysis import StandardAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser

DOCS = [
    (
        "1",
        "Whoosh basics",
        "Whoosh is a fast, featureful, pure-Python full-text indexing and "
        "search library. Because it is pure Python, you can embed it in an "
        "application without a separate search server. Whoosh lets you index "
        "free-form or structured text and then quickly find matching "
        "documents based on simple or complex search criteria.",
    ),
    (
        "2",
        "Analyzers",
        "An analyzer turns the text of a document into a stream of tokens. "
        "Whoosh ships with analyzers for stemming, stop words, and n-grams. "
        "You can compose your own analyzer from a tokenizer and a chain of "
        "filters. The same analyzer is used when you index text and when you "
        "parse a query, so the two always agree.",
    ),
]


def build_index(store_field=True):
    """Build a tiny in-memory index.

    When store_field is True the body text is stored in the index, so a Hit
    can highlight itself with no extra work. We also ask Whoosh to record
    character positions (``analyzer=... , stored=True`` plus ``phrase``/chars)
    which enables the fast "pinpoint" highlighter.
    """
    schema = Schema(
        id=ID(stored=True),
        title=TEXT(stored=True),
        # chars=True stores per-term character offsets -> pinpoint highlighting.
        body=TEXT(analyzer=StandardAnalyzer(), stored=store_field, chars=True),
    )
    ix = RamStorage().create_index(schema)
    with ix.writer() as w:
        for doc_id, title, body in DOCS:
            w.add_document(id=doc_id, title=title, body=body)
    return ix


def show(label, text):
    print(f"\n--- {label} ---")
    print(text)


def main():
    ix = build_index(store_field=True)
    with ix.searcher() as s:
        parser = QueryParser("body", schema=ix.schema)
        q = parser.parse("pure python search")
        results = s.search(q, terms=True)

        # 1. Default highlighting: ContextFragmenter + <b> tags.
        for hit in results:
            show(
                f"[default] doc {hit['id']}: {hit['title']}",
                hit.highlights("body"),
            )

        # 2. Sentence-level snippets instead of a sliding window.
        results.fragmenter = highlight.SentenceFragmenter()
        show(
            "[sentence fragmenter] doc 1",
            results[0].highlights("body"),
        )

        # 3. A different formatter: wrap matches in a CSS class so the front
        #    end controls the styling, and cap it at a single fragment.
        results.fragmenter = highlight.ContextFragmenter(maxchars=120, surround=30)
        results.formatter = highlight.HtmlFormatter(tagname="mark", classname="hit")
        show(
            "[css <mark class=hit>] doc 1",
            results[0].highlights("body", top=1),
        )

        # 4. Plain-text marking (e.g. for a terminal or a log line).
        results.fragmenter = highlight.ContextFragmenter()
        results.formatter = highlight.UppercaseFormatter()
        show(
            "[uppercase / plain text] doc 1",
            results[0].highlights("body"),
        )

        # 5. Pinpoint highlighting. Because the body field was indexed with
        #    chars=True, Whoosh stored each term's character offsets. Combined
        #    with a PinpointFragmenter, it can build snippets WITHOUT
        #    re-tokenizing the stored text -- a big win for long documents.
        results.fragmenter = highlight.PinpointFragmenter(maxchars=120, surround=30)
        results.formatter = highlight.HtmlFormatter(tagname="b")
        hl = highlight.Highlighter(fragmenter=results.fragmenter)
        print("\n--- [pinpoint] doc 1 ---")
        print("re-tokenizing needed?", not hl.can_load_chars(results, "body"))
        print(results[0].highlights("body", top=1))

    # 6. Highlight a field that was NOT stored, by handing the text back in.
    #    This is common when the full document lives in your own database and
    #    you only index a copy. Whoosh re-tokenizes the text you pass.
    ix2 = build_index(store_field=False)
    with ix2.searcher() as s:
        q = QueryParser("body", schema=ix2.schema).parse("analyzer tokens")
        results = s.search(q, terms=True)
        original_text = dict((d[0], d[2]) for d in DOCS)
        for hit in results:
            text = original_text[hit["id"]]
            show(
                f"[unstored field] doc {hit['id']}",
                hit.highlights("body", text=text),
            )


if __name__ == "__main__":
    main()
