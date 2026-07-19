import pytest

# from jieba.analyse import ChineseAnalyzer
from whoosh import analysis, fields, highlight, qparser, query
from whoosh.filedb.filestore import RamStorage
from whoosh.util.testing import TempIndex

_doc = "alfa bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"


def u(s):
    return s.decode("ascii") if isinstance(s, bytes) else s


def test_null_fragment():
    terms = frozenset(("bravo", "india"))
    sa = analysis.StandardAnalyzer()
    nf = highlight.WholeFragmenter()
    uc = highlight.UppercaseFormatter()
    htext = highlight.highlight(_doc, terms, sa, nf, uc)
    assert (
        htext
        == "alfa BRAVO charlie delta echo foxtrot golf hotel INDIA juliet kilo lima"
    )


def test_phrase_strict():
    def search(searcher, query_string):
        parser = qparser.QueryParser("title", schema=ix.schema)
        q = parser.parse(u(query_string))
        result = searcher.search(q, terms=True)
        result.fragmenter = highlight.ContextFragmenter()
        result.formatter = highlight.UppercaseFormatter()
        return result

    schema = fields.Schema(id=fields.ID(stored=True), title=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(
        id="1",
        title="strict phrase highlights phrase terms but not individual terms",
    )
    w.commit()

    with ix.searcher() as s:
        # Phrase
        r = search(s, '"phrase terms"')

        # Non-strict
        outputs = [hit.highlights("title", strict_phrase=False) for hit in r]
        assert outputs == [
            "strict PHRASE highlights PHRASE TERMS but not individual...TERMS"
        ]

        # Strict
        outputs = [hit.highlights("title", strict_phrase=True) for hit in r]
        assert outputs == ["phrase highlights PHRASE TERMS but not individual"]

        # Phrase with slop
        r = search(s, '"strict highlights terms"~2')

        # Non-strict
        outputs = [hit.highlights("title", strict_phrase=False) for hit in r]
        assert outputs == [
            "STRICT phrase HIGHLIGHTS phrase TERMS but not individual...TERMS"
        ]

        # Strict
        outputs = [hit.highlights("title", strict_phrase=True) for hit in r]
        assert outputs == ["STRICT phrase HIGHLIGHTS phrase TERMS but not individual"]

        # Phrase with individual terms
        r = search(s, 'individual AND "phrase terms"')

        # Non-strict
        outputs = [hit.highlights("title", strict_phrase=False) for hit in r]
        assert outputs == [
            "strict PHRASE highlights PHRASE TERMS but not INDIVIDUAL TERMS"
        ]

        # Strict
        outputs = [hit.highlights("title", strict_phrase=True) for hit in r]
        assert outputs == ["phrase highlights PHRASE TERMS but not INDIVIDUAL terms"]


def test_phrase_strict_ignores_stray_terms():
    # Regression for whoosh-community#486: a document containing the phrase
    # AND stray occurrences of the individual words should, under
    # strict_phrase=True, highlight only the words that form the phrase match.
    schema = fields.Schema(body=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(body="a python here " + "x " * 30 + "the python library there")
    w.commit()

    q = query.Phrase("body", ["python", "library"])
    with ix.searcher() as s:
        hit = s.search(q, terms=True)[0]

        # Non-strict highlights every occurrence of the individual words.
        loose = hit.highlights("body")
        assert loose.count('class="match') > 2

        # Strict highlights only the two words that form the phrase match.
        strict = hit.highlights("body", strict_phrase=True)
        assert strict.count('class="match') == 2
        assert "python</b> <b" in strict or "python</b>\u00a0<b" in strict


def test_phrase_strict_mixed_case_gh29():
    # Regression for mchaput/whoosh#29: with mixed-case source text, strict
    # phrase highlighting used to return an empty string. The scanner compared
    # the analyzer-normalized (lower-cased) phrase words against the *raw*
    # source words re-split on whitespace, so "java" never equalled "Java" and
    # no match was ever recorded. It must now highlight only the words that
    # form a real adjacent phrase match, regardless of source casing.
    schema = fields.Schema(body=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(
        body="we are looking for a Java Developer in CA area. "
        "Java developer should have a strong knowledge in java programming. "
        "He/she must be able to work as GUI developer"
    )
    w.commit()

    q = qparser.QueryParser("body", ix.schema).parse('"java developer"')
    with ix.searcher() as s:
        hit = s.search(q, terms=True)[0]
        hl = highlight.Highlighter(fragmenter=highlight.WholeFragmenter())

        strict = hl.highlight_hit(hit, "body", strict_phrase=True)
        # The two real "Java Developer" / "Java developer" occurrences are the
        # only phrase matches; each contributes two highlighted words.
        assert strict.count('class="match') == 4
        # The stray "java" in "java programming" and "developer" in
        # "GUI developer" must NOT be highlighted under strict phrase mode.
        assert "java</b> programming" not in strict
        assert "GUI <b" not in strict

        # Sanity: non-strict still highlights every individual term occurrence.
        loose = hl.highlight_hit(hit, "body", strict_phrase=False)
        assert loose.count('class="match') > 4


def test_phrase_strict_slop_mixed_case_gh29():
    # Same root cause as gh#29, exercised through the slop branch: intervening
    # words are allowed but casing must still be normalized before comparison.
    schema = fields.Schema(body=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(body="One Two Three four One six Three")
    w.commit()

    q = query.Phrase("body", ["one", "three"], slop=2)
    with ix.searcher() as s:
        hit = s.search(q, terms=True)[0]
        hl = highlight.Highlighter(fragmenter=highlight.WholeFragmenter())
        strict = hl.highlight_hit(hit, "body", strict_phrase=True)
        # Both slop windows ("One Two Three" and "One six Three") match.
        assert strict.count('class="match') == 4


def test_sentence_fragment():
    text = (
        "This is the first sentence. This one doesn't have the word. "
        + "This sentence is the second. Third sentence here."
    )
    terms = ("sentence",)
    sa = analysis.StandardAnalyzer(stoplist=None)
    sf = highlight.SentenceFragmenter()
    uc = highlight.UppercaseFormatter()
    htext = highlight.highlight(text, terms, sa, sf, uc)
    assert (
        htext
        == "This is the first SENTENCE...This SENTENCE is the second...Third SENTENCE here"
    )


def test_context_fragment():
    terms = frozenset(("bravo", "india"))
    sa = analysis.StandardAnalyzer()
    cf = highlight.ContextFragmenter(surround=6)
    uc = highlight.UppercaseFormatter()
    htext = highlight.highlight(_doc, terms, sa, cf, uc)
    assert htext == "alfa BRAVO charlie...hotel INDIA juliet"


def test_context_at_start():
    terms = frozenset(["alfa"])
    sa = analysis.StandardAnalyzer()
    cf = highlight.ContextFragmenter(surround=15)
    uc = highlight.UppercaseFormatter()
    htext = highlight.highlight(_doc, terms, sa, cf, uc)
    assert htext == "ALFA bravo charlie delta echo foxtrot"


def test_html_format():
    terms = frozenset(("bravo", "india"))
    sa = analysis.StandardAnalyzer()
    cf = highlight.ContextFragmenter(surround=6)
    hf = highlight.HtmlFormatter()
    htext = highlight.highlight(_doc, terms, sa, cf, hf)
    assert (
        htext
        == 'alfa <strong class="match term0">bravo</strong> charlie...hotel <strong class="match term1">india</strong> juliet'
    )


def test_html_escape():
    terms = frozenset(["bravo"])
    sa = analysis.StandardAnalyzer()
    wf = highlight.WholeFragmenter()
    hf = highlight.HtmlFormatter()
    htext = highlight.highlight('alfa <bravo "charlie"> delta', terms, sa, wf, hf)
    assert (
        htext
        == 'alfa &lt;<strong class="match term0">bravo</strong> "charlie"&gt; delta'
    )


def test_maxclasses():
    terms = frozenset(("alfa", "bravo", "charlie", "delta", "echo"))
    sa = analysis.StandardAnalyzer()
    cf = highlight.ContextFragmenter(surround=6)
    hf = highlight.HtmlFormatter(tagname="b", termclass="t", maxclasses=2)
    htext = highlight.highlight(_doc, terms, sa, cf, hf)
    assert (
        htext
        == '<b class="match t0">alfa</b> <b class="match t1">bravo</b> <b class="match t0">charlie</b>...<b class="match t1">delta</b> <b class="match t0">echo</b> foxtrot'
    )


def test_workflow_easy():
    schema = fields.Schema(id=fields.ID(stored=True), title=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)

    w = ix.writer()
    w.add_document(id="1", title="The man who wasn't there")
    w.add_document(id="2", title="The dog who barked at midnight")
    w.add_document(id="3", title="The invisible man")
    w.add_document(id="4", title="The girl with the dragon tattoo")
    w.add_document(id="5", title="The woman who disappeared")
    w.commit()

    with ix.searcher() as s:
        # Parse the user query
        parser = qparser.QueryParser("title", schema=ix.schema)
        q = parser.parse("man")
        r = s.search(q, terms=True)
        assert len(r) == 2

        r.fragmenter = highlight.WholeFragmenter()
        r.formatter = highlight.UppercaseFormatter()
        outputs = [hit.highlights("title") for hit in r]
        assert outputs == ["The invisible MAN", "The MAN who wasn't there"]


def test_workflow_manual():
    schema = fields.Schema(id=fields.ID(stored=True), title=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)

    w = ix.writer()
    w.add_document(id="1", title="The man who wasn't there")
    w.add_document(id="2", title="The dog who barked at midnight")
    w.add_document(id="3", title="The invisible man")
    w.add_document(id="4", title="The girl with the dragon tattoo")
    w.add_document(id="5", title="The woman who disappeared")
    w.commit()

    with ix.searcher() as s:
        # Parse the user query
        parser = qparser.QueryParser("title", schema=ix.schema)
        q = parser.parse("man")

        # Extract the terms the user used in the field we're interested in
        terms = [text for fieldname, text in q.all_terms() if fieldname == "title"]

        # Perform the search
        r = s.search(q)
        assert len(r) == 2

        # Use the same analyzer as the field uses. To be sure, you can
        # do schema[fieldname].analyzer. Be careful not to do this
        # on non-text field types such as DATETIME.
        analyzer = schema["title"].analyzer

        # Since we want to highlight the full title, not extract fragments,
        # we'll use WholeFragmenter.
        nf = highlight.WholeFragmenter()

        # In this example we'll simply uppercase the matched terms
        fmt = highlight.UppercaseFormatter()

        outputs = []
        for d in r:
            text = d["title"]
            outputs.append(highlight.highlight(text, terms, analyzer, nf, fmt))

        assert outputs == ["The invisible MAN", "The MAN who wasn't there"]


def test_unstored():
    schema = fields.Schema(text=fields.TEXT, tags=fields.KEYWORD)
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(text="alfa bravo charlie", tags="delta echo")
    w.commit()

    hit = ix.searcher().search(query.Term("text", "bravo"))[0]
    with pytest.raises(KeyError):
        hit.highlights("tags")


def test_multifilter():
    iwf_for_index = analysis.IntraWordFilter(mergewords=True, mergenums=False)
    iwf_for_query = analysis.IntraWordFilter(mergewords=False, mergenums=False)
    mf = analysis.MultiFilter(index=iwf_for_index, query=iwf_for_query)
    ana = analysis.RegexTokenizer() | mf | analysis.LowercaseFilter()

    schema = fields.Schema(text=fields.TEXT(analyzer=ana, stored=True))
    with TempIndex(schema) as ix:
        w = ix.writer()
        w.add_document(text="Our BabbleTron5000 is great")
        w.commit()

        with ix.searcher() as s:
            assert ("text", "5000") in s.reader()
            hit = s.search(query.Term("text", "5000"))[0]
            assert (
                hit.highlights("text")
                == 'Our BabbleTron<b class="match term0">5000</b> is great'
            )


def test_pinpoint():
    domain = (
        "alfa bravo charlie delta echo foxtrot golf hotel india juliet "
        "kilo lima mike november oskar papa quebec romeo sierra tango"
    )
    schema = fields.Schema(text=fields.TEXT(stored=True, chars=True))
    ix = RamStorage().create_index(schema)
    w = ix.writer()
    w.add_document(text=domain)
    w.commit()

    assert ix.schema["text"].supports("characters")
    with ix.searcher() as s:
        r = s.search(query.Term("text", "juliet"), terms=True)
        hit = r[0]
        hi = highlight.Highlighter()
        hi.formatter = highlight.UppercaseFormatter()

        assert not hi.can_load_chars(r, "text")
        assert (
            hi.highlight_hit(hit, "text")
            == "golf hotel india JULIET kilo lima mike november"
        )

        hi.fragmenter = highlight.PinpointFragmenter()
        assert hi.can_load_chars(r, "text")
        assert (
            hi.highlight_hit(hit, "text")
            == "ot golf hotel india JULIET kilo lima mike nove"
        )

        hi.fragmenter.autotrim = True
        assert hi.highlight_hit(hit, "text") == "golf hotel india JULIET kilo lima mike"


def test_pinpoint_multiterm_retokenize():
    # Regression: when PinpointFragmenter falls back to the retokenizing path
    # (the field does not store characters, so can_load_chars() is False) and a
    # query matches *more than one* term, the fragmenter used to read the
    # analyzer's single, reused Token object at list-comprehension time. That
    # made every matched entry point at the *last* token in the stream, so the
    # wrong word (or nothing) got highlighted. It must snapshot each matched
    # token instead. See highlight.PinpointFragmenter.fragment_tokens.
    schema = fields.Schema(text=fields.TEXT(stored=True))  # note: no chars=True
    ix = RamStorage().create_index(schema)
    with ix.writer() as w:
        w.add_document(text="The quick brown fox jumps over the lazy dog")

    with ix.searcher() as s:
        qp = qparser.QueryParser("text", ix.schema)
        r = s.search(qp.parse('"quick brown"'), terms=True)
        hit = r[0]

        hi = highlight.Highlighter(
            fragmenter=highlight.PinpointFragmenter(),
            formatter=highlight.UppercaseFormatter(),
        )
        # This field can't load chars, so we exercise the retokenize fallback.
        assert not hi.can_load_chars(r, "text")

        out = hi.highlight_hit(hit, "text", top=1)
        # Both matched terms must be highlighted, and the unmatched trailing
        # word "dog" must NOT be.
        assert "QUICK" in out and "BROWN" in out
        assert "DOG" not in out

        # A two-term (non-phrase) query hits the same code path.
        r2 = s.search(qp.parse("brown fox"), terms=True)
        out2 = hi.highlight_hit(r2[0], "text", top=1)
        assert "BROWN" in out2 and "FOX" in out2
        assert "DOG" not in out2


def test_highlight_wildcards():
    schema = fields.Schema(text=fields.TEXT(stored=True))
    ix = RamStorage().create_index(schema)
    with ix.writer() as w:
        w.add_document(text="alfa bravo charlie delta cookie echo")

    with ix.searcher() as s:
        qp = qparser.QueryParser("text", ix.schema)
        q = qp.parse("c*")
        r = s.search(q)
        assert r.scored_length() == 1
        r.formatter = highlight.UppercaseFormatter()
        hit = r[0]
        assert hit.highlights("text") == "alfa bravo CHARLIE delta COOKIE echo"


def test_highlight_ngrams():
    schema = fields.Schema(text=fields.NGRAMWORDS(stored=True))
    ix = RamStorage().create_index(schema)
    with ix.writer() as w:
        w.add_document(text="Multiplication and subtraction are good")

    with ix.searcher() as s:
        qp = qparser.QueryParser("text", ix.schema)
        q = qp.parse("multiplication")
        r = s.search(q)
        assert r.scored_length() == 1

        r.fragmenter = highlight.SentenceFragmenter()
        r.formatter = highlight.UppercaseFormatter()
        snippet = r[0].highlights("text")
        assert snippet == "MULTIPLICATIon and subtracTION are good"


def test_issue324():
    sa = analysis.StemmingAnalyzer()
    result = highlight.highlight(
        "Indexed!\n1",
        ["index"],
        sa,
        fragmenter=highlight.ContextFragmenter(),
        formatter=highlight.UppercaseFormatter(),
    )
    assert result == "INDEXED!\n1"


def test_whole_noterms():
    schema = fields.Schema(text=fields.TEXT(stored=True), tag=fields.KEYWORD)
    ix = RamStorage().create_index(schema)
    with ix.writer() as w:
        w.add_document(text="alfa bravo charlie delta echo foxtrot golf", tag="foo")

    with ix.searcher() as s:
        r = s.search(query.Term("text", "delta"))
        assert len(r) == 1

        r.fragmenter = highlight.WholeFragmenter()
        r.formatter = highlight.UppercaseFormatter()
        hi = r[0].highlights("text")
        assert hi == "alfa bravo charlie DELTA echo foxtrot golf"

        r = s.search(query.Term("tag", "foo"))
        assert len(r) == 1
        r.fragmenter = highlight.WholeFragmenter()
        r.formatter = highlight.UppercaseFormatter()
        hi = r[0].highlights("text")
        assert hi == ""

        hi = r[0].highlights("text", minscore=0)
        assert hi == "alfa bravo charlie delta echo foxtrot golf"
