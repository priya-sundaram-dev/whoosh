# Copyright 2012 Matt Chaput. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY MATT CHAPUT ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL MATT CHAPUT OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of Matt Chaput.

"""This package contains objects that represent the tree of a search query.

A :class:`~whoosh.query.Query` object can be created directly and combined
(for example, ``Term("content", "foo") & Term("content", "bar")``), or produced
by a :class:`whoosh.qparser.QueryParser` from a query string. Every query can
be matched against an index by passing it to
:meth:`whoosh.searching.Searcher.search`.

The most commonly used queries are re-exported here so they can be imported
directly from ``whoosh.query`` (for example ``from whoosh.query import Term,
And, Or``). This includes term queries (:class:`Term`, :class:`Prefix`,
:class:`Wildcard`, :class:`FuzzyTerm`), compound queries (:class:`And`,
:class:`Or`, :class:`Not`, :class:`AndMaybe`, :class:`AndNot`), range queries
(:class:`TermRange`, :class:`NumericRange`, :class:`DateRange`), and span
queries for positional matching.
"""

from whoosh.query.compound import (
    And,
    AndMaybe,
    AndNot,
    BinaryQuery,
    BooleanQuery,
    CompoundQuery,
    DefaultOr,
    DisjunctionMax,
    Or,
    Otherwise,
    PreloadedOr,
    Require,
    SplitOr,
)
from whoosh.query.nested import NestedChildren, NestedParent
from whoosh.query.positional import Ordered, Phrase, Sequence
from whoosh.query.qcolumns import ColumnMatcher, ColumnQuery
from whoosh.query.qcore import (
    Every,
    Highest,
    Lowest,
    NullQuery,
    Query,
    QueryError,
    _NullQuery,
    error_query,
    token_lists,
)
from whoosh.query.ranges import DateRange, NumericRange, RangeMixin, TermRange
from whoosh.query.spans import (
    Span,
    SpanBefore,
    SpanBiMatcher,
    SpanBiQuery,
    SpanCondition,
    SpanContains,
    SpanFirst,
    SpanNear,
    SpanNear2,
    SpanNot,
    SpanOr,
    SpanQuery,
    SpanWrappingMatcher,
    WrappingSpan,
)
from whoosh.query.terms import (
    ExpandingTerm,
    FuzzyTerm,
    MultiTerm,
    PatternQuery,
    Prefix,
    Regex,
    Term,
    Variations,
    Wildcard,
)
from whoosh.query.wrappers import ConstantScoreQuery, Not, WeightingQuery, WrappingQuery
