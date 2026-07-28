"""Type-checker smoke fixture for Whoosh3's public API (gh#3).

This module is *not* run as a normal test. Instead, CI type-checks it with
``mypy`` (see the ``types`` job in ``.github/workflows/ci.yml``). It exercises
the annotated public entry points the way a downstream user would, so that if a
future change breaks or removes an annotation, the type checker fails loudly
here rather than silently degrading the editor/mypy experience for users.

Keep this snippet realistic and minimal: index creation, a schema built from
the field-type constructors, adding a document, and running a query through the
searching layer.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from operator import add
from typing import TYPE_CHECKING, Any

from whoosh import classify, highlight, index, scoring, spelling
from whoosh.fields import DATETIME, ID, NUMERIC, TEXT, Schema
from whoosh.qparser import QueryParser
from whoosh.query import (
    And,
    AndNot,
    ConstantScoreQuery,
    DateRange,
    DisjunctionMax,
    FuzzyTerm,
    Not,
    NumericRange,
    Or,
    Ordered,
    Phrase,
    Prefix,
    Sequence,
    Term,
    TermRange,
    Variations,
    Wildcard,
)

if TYPE_CHECKING:
    from whoosh.matching import Matcher
    from whoosh.query import Query
    from whoosh.searching import Hit, Results
    from whoosh.writing import IndexWriter


def build_schema() -> Schema:
    # Field-type constructors are annotated, so kwargs type-check.
    return Schema(
        id=ID(stored=True, unique=True),
        title=TEXT(stored=True),
        views=NUMERIC(stored=True),
        created=DATETIME(stored=True),
    )


def run() -> list[str]:
    schema = build_schema()
    tmpdir = tempfile.mkdtemp()

    # index.create_in returns an Index; open/exists helpers are annotated too.
    ix = index.create_in(tmpdir, schema)
    assert index.exists_in(tmpdir)

    # ix.writer() is annotated to return an IndexWriter; add_document /
    # update_document / commit are annotated ``-> None`` on the public base
    # class, and the writer works as a context manager.
    writer: IndexWriter = ix.writer()
    writer.add_document(id="1", title="First document about search")
    writer.commit()

    with ix.writer() as w:
        w.add_document(id="2", title="Second document about indexing")
        w.update_document(id="2", title="Second document about indexing v2")

    # The scoring public API is annotated, so tuning constructors and the
    # WeightingModel/BaseScorer surface type-check for downstream users.
    weighting: scoring.WeightingModel = scoring.BM25F(B=0.75, K1=1.2)
    pl2: scoring.WeightingModel = scoring.PL2(c=1.0)
    combined: scoring.WeightingModel = scoring.MultiWeighting(weighting, title=pl2)
    supports_quality: bool = weighting.use_final is False

    titles: list[str] = []
    with ix.searcher(weighting=combined) as searcher:
        parser = QueryParser("title", schema=ix.schema)
        query = parser.parse("search")
        results: Results = searcher.search(query, limit=10)
        assert supports_quality in (True, False)

        # Results inspection helpers are annotated, so their return types
        # flow into user code and type-check here.
        empty: bool = results.is_empty()
        scored: int = results.scored_length()
        est: int = results.estimated_length()
        exact: bool = results.has_exact_length()
        assert not empty or scored == 0
        assert est >= 0 and exact in (True, False)

        if scored:
            top_score: float | None = results.score(0)
            top_docnum: int = results.docnum(0)
            top_fields: dict[str, Any] = results.fields(0)
            assert top_docnum >= 0
            assert top_score is None or top_score >= 0.0
            assert isinstance(top_fields, dict)

        for docnum, score in results.items():
            assert docnum >= 0
            assert score is None or score >= 0.0

        # whoosh.highlight's public API is annotated (gh#49). Building a
        # Highlighter from a Fragmenter + Formatter and calling highlight_hit
        # flows str results into user code; the helper classes' numeric config
        # attributes and str-returning format methods type-check here too.
        fragmenter: highlight.Fragmenter = highlight.ContextFragmenter(
            maxchars=200, surround=20
        )
        formatter: highlight.Formatter = highlight.HtmlFormatter(tagname="b")
        hl: highlight.Highlighter = highlight.Highlighter(
            fragmenter=fragmenter, formatter=formatter, order=highlight.SCORE
        )
        must_retok: bool = fragmenter.must_retokenize()
        assert isinstance(must_retok, bool)

        for hit in results:
            hit_obj: Hit = hit
            # Hit's dict-like accessors are annotated.
            keys: list[str] = hit_obj.keys()
            fields: dict[str, Any] = hit_obj.fields()
            assert set(keys) <= set(fields)
            titles.append(str(hit_obj["title"]))

            # highlight_hit is annotated to return str.
            excerpt: str = hl.highlight_hit(hit_obj, "title", top=1)
            assert isinstance(excerpt, str)

        # Searcher's document-lookup helpers are annotated, so their return
        # types flow into user code and type-check here.
        total: int = searcher.doc_count()
        total_all: int = searcher.doc_count_all()
        assert total <= total_all

        one: dict[str, Any] | None = searcher.document(id="1")
        assert one is None or isinstance(one, dict)

        found_docnum: int | None = searcher.document_number(id="1")
        assert found_docnum is None or found_docnum >= 0

        for stored in searcher.documents():
            assert isinstance(stored, dict)
        for dn in searcher.document_numbers():
            assert dn >= 0

        # Searcher.find() parses a query string and returns Results, so its
        # return type flows into user code and type-checks here.
        found: Results = searcher.find("title", "search")
        for fhit in found:
            titles.append(str(fhit["title"]))

        # whoosh.query.terms' public API is annotated (gh#51). Constructing the
        # term-level query classes and running them through the searcher flows
        # their annotated types into user code: the constructors accept the
        # documented kwargs, __str__ returns str, Wildcard.normalize() returns a
        # Query, and matcher() returns a Matcher.
        term_q = Term("title", "search", boost=2.0)
        prefix_q = Prefix("title", "sea")
        wildcard_q = Wildcard("title", "sea*ch")
        fuzzy_q = FuzzyTerm("title", "serch", maxdist=2, prefixlength=1)
        variations_q = Variations("title", "searching")
        term_label: str = str(term_q)
        normalized: Query = wildcard_q.normalize()
        assert isinstance(term_label, str)
        assert isinstance(str(normalized), str)
        for term_query in (term_q, prefix_q, wildcard_q, fuzzy_q, variations_q):
            m: Matcher = term_query.matcher(searcher)
            assert m.is_active() in (True, False)

        # Compound query classes (whoosh.query.compound): the boolean
        # combinators most programs build directly. Their annotated
        # constructors accept a sequence of subqueries plus documented kwargs,
        # __len__ returns int, iterating yields Query objects, and
        # normalize()/matcher() keep their Query/Matcher return types.
        and_q = And([term_q, prefix_q], boost=1.5)
        or_q = Or([term_q, wildcard_q], boost=2.0, minmatch=0, scale=0.5)
        dismax_q = DisjunctionMax([term_q, fuzzy_q], tiebreak=0.1)
        andnot_q = AndNot(or_q, term_q)
        clause_count: int = len(and_q)
        assert clause_count == 2
        for sub in or_q:
            sub_label: str = str(sub)
            assert isinstance(sub_label, str)
        for compound_query in (and_q, or_q, dismax_q, andnot_q):
            compound_norm: Query = compound_query.normalize()
            cm: Matcher = compound_query.matcher(searcher)
            assert isinstance(str(compound_norm), str)
            assert cm.is_active() in (True, False)

        # Wrapping query classes (whoosh.query.wrappers): Not excludes a
        # subquery and ConstantScoreQuery wraps one to give matches a flat
        # score. Their annotated constructors accept a Query (plus a float
        # boost/score), children() yields Query objects, and str()/matcher()
        # keep their str/Matcher return types.
        not_q = Not(term_q, boost=1.0)
        const_q = ConstantScoreQuery(prefix_q, score=2.0)
        for wrapping_query in (not_q, const_q):
            for wrapped_child in wrapping_query.children():
                child_label: str = str(wrapped_child)
                assert isinstance(child_label, str)
            wm: Matcher = wrapping_query.matcher(searcher)
            assert wm.is_active() in (True, False)

        # Range query classes (whoosh.query.ranges): TermRange over a text
        # field, and NumericRange/DateRange over the numeric/datetime fields.
        # Their annotated constructors accept the documented start/end bounds
        # (str for TermRange, a number for NumericRange, a datetime for
        # DateRange) plus bool exclusivity flags and a float boost; str()
        # returns str and matcher() keeps its Matcher return type.
        term_range = TermRange("title", "a", "s", startexcl=False, endexcl=True)
        numeric_range = NumericRange("views", 10, 5925, boost=1.5)
        date_range = DateRange(
            "created",
            datetime(2010, 1, 1),
            datetime(2010, 12, 31),
            constantscore=True,
        )
        range_label: str = str(term_range)
        assert isinstance(range_label, str)
        overlaps: bool = term_range.overlaps(numeric_range)
        assert overlaps in (True, False)
        for range_query in (term_range, numeric_range, date_range):
            rm: Matcher = range_query.matcher(searcher)
            assert rm.is_active() in (True, False)

        # Positional query classes (whoosh.query.positional): Phrase matches an
        # ordered run of words, while Sequence/Ordered match sub-queries in
        # adjacent positions. Their annotated constructors accept the documented
        # words/subqueries plus int slop and float boost; str() returns str,
        # terms()/tokens() yield their annotated element types, and matcher()
        # keeps its Matcher return type.
        phrase_q = Phrase("title", ["about", "search"], slop=1, boost=2.0)
        seq_q = Sequence([term_q, prefix_q], slop=2, ordered=True)
        ordered_q = Ordered([term_q, prefix_q], slop=2)
        phrase_label: str = str(phrase_q)
        assert isinstance(phrase_label, str)
        for field_name, word in phrase_q.terms(phrases=True):
            assert isinstance(field_name, str) and isinstance(word, str)
        phrase_tokens: list[Any] = list(phrase_q.tokens())
        assert isinstance(phrase_tokens, list)
        pm: Matcher = phrase_q.matcher(searcher)
        assert pm.is_active() in (True, False)
        for positional_query in (seq_q, ordered_q):
            positional_norm: Query = positional_query.normalize()
            assert isinstance(repr(positional_norm), str)

        # whoosh.classify public API (gh#59): ExpansionModel subclasses and
        # Expander are annotated so downstream query-expansion code type-checks.
        model: classify.ExpansionModel = classify.Bo1Model(doc_count=2, field_length=10.0)
        norm: float = model.normalizer(maxweight=1.0, top_total=4.0)
        expansion_score: float = model.score(1.0, 2.0, 4)
        assert isinstance(norm, float) and isinstance(expansion_score, float)
        expander = classify.Expander(searcher.reader(), "title", model=classify.Bo1Model)
        expander.add([("search", 1.0)])
        expanded: list[tuple[str, float]] = expander.expanded_terms(3)
        assert isinstance(expanded, list)

        # whoosh.spelling public API (gh#61): the "did you mean" surface.
        # ListCorrector builds from a sorted word list and .suggest() is
        # annotated ``-> list[str]``, so its return type flows into user code.
        # A ReaderCorrector pulled from the reader and a MultiCorrector merge
        # keep the same Corrector interface; the searching layer's
        # correct_query returns an annotated Correction whose .format_string()
        # yields str and whose .query stays a Query.
        list_corr: spelling.Corrector = spelling.ListCorrector(
            ["indexing", "search", "searching"]
        )
        suggestions: list[str] = list_corr.suggest("serch", limit=3, maxdist=2, prefix=1)
        assert isinstance(suggestions, list)
        assert all(isinstance(s, str) for s in suggestions)

        reader_corr: spelling.Corrector = searcher.reader().corrector("title")
        multi: spelling.Corrector = spelling.MultiCorrector(
            [list_corr, reader_corr], add
        )
        merged: list[str] = multi.suggest("serch")
        assert isinstance(merged, list)

        spell_parser = QueryParser("title", schema=ix.schema)
        spell_q: Query = spell_parser.parse("serch")
        correction: spelling.Correction = searcher.correct_query(spell_q, "serch")
        corrected_query: Query = correction.query
        corrected_string: str = correction.string
        formatted: str = correction.format_string(highlight.NullFormatter())
        repr_text: str = repr(correction)
        assert isinstance(str(corrected_query), str)
        assert isinstance(corrected_string, str)
        assert isinstance(formatted, str)
        assert repr_text.startswith("Correction(")

        qcorr: spelling.QueryCorrector = spelling.SimpleQueryCorrector(
            {"title": list_corr}, [("title", "serch")]
        )
        assert isinstance(qcorr, spelling.QueryCorrector)
        spell_field: str = spelling.QueryCorrector("title").field()
        assert spell_field == "title"

    return titles


if __name__ == "__main__":
    print(run())
