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
from whoosh.analysis.acore import Token
from whoosh.analysis.analyzers import StandardAnalyzer
from whoosh.analysis.filters import (
    CharsetFilter,
    DelimitedAttributeFilter,
    LowercaseFilter,
    PassFilter,
    ReverseTextFilter,
    StopFilter,
    StripFilter,
    SubstitutionFilter,
    TeeFilter,
)
from whoosh.analysis.ngrams import (
    NgramAnalyzer,
    NgramFilter,
    NgramTokenizer,
    NgramWordAnalyzer,
)
from whoosh.analysis.tokenizers import (
    CharsetTokenizer,
    CommaSeparatedTokenizer,
    IDTokenizer,
    NormalizingRegexTokenizer,
    PathTokenizer,
    RegexTokenizer,
    SpaceSeparatedTokenizer,
)
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
    from collections.abc import Iterator

    from whoosh.analysis.analyzers import CompositeAnalyzer
    from whoosh.matching import Matcher
    from whoosh.query import Query
    from whoosh.reading import IndexReader, TermInfo
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

    # whoosh.writing's IndexWriter public API is annotated (gh#62). Exercise
    # the schema-mutation, deletion and grouping helpers on a throwaway index
    # so their side effects don't perturb the search fixture below. The precise
    # types flow into user code: add_field/remove_field return ``None``, the
    # delete_by_* helpers return the deleted-document ``int`` count, and
    # group() yields an AbstractContextManager usable in a ``with`` statement.
    wtmp = tempfile.mkdtemp()
    wix = index.create_in(wtmp, build_schema())
    w2: IndexWriter = wix.writer()
    w2.add_field("body", TEXT(stored=True))
    with w2.group():
        w2.add_document(id="10", title="Grouped parent", body="child text")
        w2.add_document(id="11", title="Grouped child", body="more text")
    deleted_by_term: int = w2.delete_by_term("id", "10")
    deleted_by_query: int = w2.delete_by_query(Term("id", "11"))
    assert deleted_by_term >= 0 and deleted_by_query >= 0
    w2.commit()

    # remove_field is applied on a fresh writer (schema edits must precede any
    # buffered documents); its ``-> None`` annotation flows here too.
    w3: IndexWriter = wix.writer()
    w3.remove_field("body")
    w3.commit()

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
        titles.extend(str(fhit["title"]) for fhit in found)

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

        # whoosh.reading public API (gh#64): the IndexReader read side that
        # every search touches. The annotated signatures flow the concrete
        # return types (counts as ``int``, ``lexicon`` as bytestrings, a
        # ``TermInfo`` with ``int`` statistics, a ``Matcher`` for postings)
        # into downstream index-introspection code.
        reader: IndexReader = searcher.reader()
        field_names: list[str] = list(reader.indexed_field_names())
        assert "title" in field_names

        doc_total: int = reader.doc_count()
        doc_total_all: int = reader.doc_count_all()
        assert doc_total <= doc_total_all
        assert reader.has_deletions() is False
        assert reader.is_deleted(0) is False

        lex: list[bytes] = list(reader.lexicon("title"))
        assert all(isinstance(bs, bytes) for bs in lex)
        prefixed: list[bytes] = list(reader.expand_prefix("title", "sea"))
        assert all(isinstance(bs, bytes) for bs in prefixed)

        all_terms: list[tuple[str, bytes]] = list(reader.all_terms())
        assert all_terms

        if lex:
            first_text: bytes = lex[0]
            info: TermInfo = reader.term_info("title", first_text)
            term_df: int = info.doc_frequency()
            term_weight: float = info.weight()
            term_maxid: int = info.max_id()
            assert term_df >= 1
            assert term_weight >= 0.0
            assert term_maxid >= 0

            freq: int = reader.frequency("title", first_text)
            docfreq: int = reader.doc_frequency("title", first_text)
            assert freq >= docfreq >= 1

            postings: Matcher = reader.postings("title", first_text)
            assert postings.is_active() in (True, False)

            for text, terminfo in reader.iter_field("title"):
                assert isinstance(text, bytes)
                assert isinstance(terminfo.doc_frequency(), int)
                break

        reader_stored: dict[str, Any] = reader.stored_fields(0)
        assert isinstance(reader_stored, dict)
        for stored_doc in reader.all_stored_fields():
            assert isinstance(stored_doc, dict)
            break
        assert reader.has_vector(0, "title") in (True, False)

        near: list[str] = list(reader.terms_within("title", "search", 1))
        assert all(isinstance(word, str) for word in near)

        # whoosh.query base-class public API (gh#69): the generic Query surface
        # every query type inherits and that tree-transformation / introspection
        # code calls polymorphically. The annotations flow the concrete return
        # types into user code: the boolean predicates return ``bool``, the
        # tree-walkers (children/leaves) yield ``Query``, term introspection
        # yields ``(str, str)`` pairs, transforms (with_boost/apply/accept/
        # normalize/simplify) return a ``Query``, estimate_* return ``int``,
        # docs() yields ``int`` docnums, and tokens/all_tokens yield ``Token``.
        base_q: Query = And([term_q, prefix_q]).normalize()
        is_leaf: bool = base_q.is_leaf()
        is_range: bool = base_q.is_range()
        has_terms: bool = base_q.has_terms()
        needs_spans: bool = base_q.needs_spans()
        assert is_leaf in (True, False)
        assert (is_range, has_terms, needs_spans) != (None, None, None)

        for child_q in base_q.children():
            assert isinstance(str(child_q), str)
        for leaf_q in base_q.leaves():
            assert isinstance(str(leaf_q), str)

        for base_field, base_text in base_q.iter_all_terms():
            assert isinstance(base_field, str) and isinstance(base_text, str)
        all_pairs: set[tuple[str, str]] = base_q.all_terms()
        assert all(isinstance(f, str) and isinstance(t, str) for f, t in all_pairs)
        for pair_field, pair_text in base_q.terms(phrases=True):
            assert isinstance(pair_field, str) and isinstance(pair_text, str)

        existing: set[tuple[str, bytes]] = base_q.existing_terms(reader, expand=True)
        assert all(isinstance(t, bytes) for _, t in existing)

        boosted: Query = base_q.with_boost(2.0)
        applied: Query = base_q.apply(lambda q: q)
        accepted: Query = base_q.accept(lambda q: q)
        simplified: Query = base_q.simplify(reader)
        required: set[Query] = base_q.requires()
        assert isinstance(str(boosted), str)
        assert isinstance(str(applied), str) and isinstance(str(accepted), str)
        assert isinstance(str(simplified), str)
        assert all(isinstance(str(r), str) for r in required)

        matched_field: str | None = term_q.field()
        assert matched_field is None or isinstance(matched_field, str)

        size_est: int = term_q.estimate_size(reader)
        min_est: int = term_q.estimate_min_size(reader)
        assert size_est >= 0 and min_est >= 0

        base_docnums: list[int] = list(term_q.docs(searcher))
        assert all(dn >= 0 for dn in base_docnums)

        base_tokens: list[Any] = list(term_q.all_tokens())
        more_tokens: list[Any] = list(term_q.tokens())
        assert isinstance(base_tokens, list) and isinstance(more_tokens, list)

        term_leaves, phrase_leaves = phrase_q.phrases()
        assert isinstance(term_leaves, list) and isinstance(phrase_leaves, list)

    # whoosh.analysis.ngrams public API (gh#71): the N-gram tokenizer/filter
    # pair behind autocomplete and prefix search. The annotations flow the
    # concrete types into user code: the constructors take ``int`` sizes and an
    # optional ``at`` string, calling the tokenizer or the filter yields
    # ``Token`` objects, and the analyzer factories return a composed analyzer.
    ngram_tokenizer = NgramTokenizer(2, 3)
    ngram_tokens: list[Token] = list(ngram_tokenizer("hi there", positions=True))
    assert all(isinstance(tok, Token) for tok in ngram_tokens)

    ngram_filter = NgramFilter(2, 4, at="start")
    filtered: Iterator[Token] = ngram_filter(RegexTokenizer()("hello there"))
    assert all(isinstance(tok, Token) for tok in filtered)

    ngram_analyzer: CompositeAnalyzer = NgramAnalyzer(3)
    word_analyzer: CompositeAnalyzer = NgramWordAnalyzer(2, 4, at="end")
    gram_texts: list[str] = [str(tok.text) for tok in ngram_analyzer("hi there")]
    word_texts: list[str] = [str(tok.text) for tok in word_analyzer("hello there")]
    assert gram_texts and word_texts

    # whoosh.analysis.tokenizers public API (gh#72)
    tok_id = IDTokenizer()
    tok_norm = NormalizingRegexTokenizer()
    tok_path = PathTokenizer()
    assert list(tok_id("test")) and list(tok_norm("test")) and list(tok_path("a/b"))
    assert list(SpaceSeparatedTokenizer()("a b")) and list(CommaSeparatedTokenizer()("a,b"))

    # whoosh.analysis.filters public API (gh#76)
    tokenizer = RegexTokenizer()
    lc_filter = LowercaseFilter()
    lc_tokens: Iterator[Token] = lc_filter(tokenizer("Hello World"))
    assert all(tok.text == tok.text.lower() for tok in lc_tokens)
    strip_filter = StripFilter()
    strip_tokens: Iterator[Token] = strip_filter(tokenizer("  hello  "))
    assert all(isinstance(tok, Token) for tok in strip_tokens)
    rev_filter = ReverseTextFilter()
    rev_tokens: Iterator[Token] = rev_filter(tokenizer("hello there"))
    assert all(isinstance(tok, Token) for tok in rev_tokens)
    # StopFilter: annotated params (stoplist, minsize, maxsize, renumber, lang)
    stop_filter = StopFilter(minsize=2, maxsize=15, renumber=True)
    stop_tokens: Iterator[Token] = stop_filter(tokenizer("this is a test"))
    assert all(isinstance(tok, Token) for tok in stop_tokens)
    # SubstitutionFilter: pattern + replacement
    sub_filter = SubstitutionFilter("-", "")
    sub_tokens: Iterator[Token] = sub_filter(tokenizer("self-aware pre-built"))
    assert all(isinstance(tok, Token) for tok in sub_tokens)
    # DelimitedAttributeFilter: delimiter, attribute, default, type
    daf = DelimitedAttributeFilter(delimiter="^", attribute="boost", default=1.0, type=float)
    daf_tokens: Iterator[Token] = daf(tokenizer("image render^2 file^0.5"))
    assert all(isinstance(tok, Token) for tok in daf_tokens)
    # PassFilter: passes tokens through unchanged
    pass_filter = PassFilter()
    pass_tokens: Iterator[Token] = pass_filter(tokenizer("hello"))
    assert all(isinstance(tok, Token) for tok in pass_tokens)
    # TeeFilter: interleaves two filter branches
    tee_filter = TeeFilter(LowercaseFilter(), ReverseTextFilter())
    tee_tokens: Iterator[Token] = tee_filter(tokenizer("Hello World"))
    assert all(isinstance(tok, Token) for tok in tee_tokens)

    # whoosh.analysis.morph public API (gh#77): the stemming / phonetic filters
    # behind StemmingAnalyzer and "sounds-like" matching. Their annotated
    # __call__ takes an Iterator[Token] and returns an Iterator[Token], so the
    # filter chain type-checks for downstream analyzer authors.
    from whoosh.analysis.morph import DoubleMetaphoneFilter, StemFilter

    stem_filter = StemFilter()
    stem_tokens: Iterator[Token] = stem_filter(tokenizer("searching indexes"))
    assert all(isinstance(tok, Token) for tok in stem_tokens)
    dmeta_filter = DoubleMetaphoneFilter()
    dmeta_tokens: Iterator[Token] = dmeta_filter(tokenizer("Smith Smyth"))
    assert all(isinstance(tok, Token) for tok in dmeta_tokens)

    # whoosh.analysis.intraword public API (gh#82): the sub-word splitting and
    # phrase-shingling filters used for CamelCase/Wi-Fi/SD500 handling and
    # pseudo-phrase fields. Their annotated __call__ takes an Iterable[Token]
    # and returns an Iterator[Token], so the filter chain type-checks.
    from whoosh.analysis.intraword import (
        BiWordFilter,
        CompoundWordFilter,
        IntraWordFilter,
        ShingleFilter,
    )

    iwf = IntraWordFilter(mergewords=True, mergenums=True)
    iwf_tokens: Iterator[Token] = iwf(tokenizer("PowerShot SD500 Wi-Fi"))
    assert all(isinstance(tok, Token) for tok in iwf_tokens)
    biword = BiWordFilter(sep="-")
    biword_tokens: Iterator[Token] = biword(tokenizer("the sign of four"))
    assert all(isinstance(tok, Token) for tok in biword_tokens)
    shingle = ShingleFilter(size=2, sep=" ")
    shingle_tokens: Iterator[Token] = shingle(tokenizer("a witty fool"))
    assert all(isinstance(tok, Token) for tok in shingle_tokens)
    cwf = CompoundWordFilter({"green", "eggs"}, keep_compound=True)
    cwf_tokens: Iterator[Token] = cwf(tokenizer("greeneggs"))
    assert all(isinstance(tok, Token) for tok in cwf_tokens)

    # whoosh.analysis.analyzers public API (gh#85): analyzer factories return
    # an Analyzer, and calling one with text yields an Iterator[Token].
    standard_analyzer = StandardAnalyzer()
    standard_tokens: Iterator[Token] = standard_analyzer(
        "Testing is testing and searchable"
    )
    assert all(isinstance(tok, Token) for tok in standard_tokens)

    return titles


if __name__ == "__main__":
    print(run())
