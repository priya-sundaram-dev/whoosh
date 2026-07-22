# Copyright 2008 Matt Chaput. All rights reserved.
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

"""
This module contains classes for scoring (and sorting) search results.
"""


from __future__ import annotations

from math import log, pi
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

# Base classes


class WeightingModel:
    """Abstract base class for scoring models. A WeightingModel object provides
    a method, ``scorer``, which returns an instance of
    :class:`whoosh.scoring.Scorer`.

    Basically, WeightingModel objects store the configuration information for
    the model (for example, the values of B and K1 in the BM25F model), and
    then creates a scorer instance based on additional run-time information
    (the searcher, the fieldname, and term text) to do the actual scoring.
    """

    use_final: bool = False

    def idf(self, searcher: Any, fieldname: str, text: str) -> float:
        """Returns the inverse document frequency of the given term."""

        parent = searcher.get_parent()
        n = parent.doc_frequency(fieldname, text)
        dc = parent.doc_count_all()
        return log(dc / (n + 1)) + 1

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> BaseScorer:
        """Returns an instance of :class:`whoosh.scoring.Scorer` configured
        for the given searcher, fieldname, and term text.
        """

        raise NotImplementedError(self.__class__.__name__)

    def final(self, searcher: Any, docnum: int, score: float) -> float:
        """Returns a final score for each document. You can use this method
        in subclasses to apply document-level adjustments to the score, for
        example using the value of stored field to influence the score
        (although that would be slow).

        WeightingModel sub-classes that use ``final()`` should have the
        attribute ``use_final`` set to ``True``.

        :param searcher: :class:`whoosh.searching.Searcher` for the index.
        :param docnum: the doc number of the document being scored.
        :param score: the document's accumulated term score.

        :rtype: float
        """

        return score


class BaseScorer:
    """Base class for "scorer" implementations. A scorer provides a method for
    scoring a document, and sometimes methods for rating the "quality" of a
    document and a matcher's current "block", to implement quality-based
    optimizations.

    Scorer objects are created by WeightingModel objects. Basically,
    WeightingModel objects store the configuration information for the model
    (for example, the values of B and K1 in the BM25F model), and then creates
    a scorer instance.
    """

    def supports_block_quality(self) -> bool:
        """Returns True if this class supports quality optimizations."""

        return False

    def score(self, matcher: Any) -> float:
        """Returns a score for the current document of the matcher."""

        raise NotImplementedError(self.__class__.__name__)

    def max_quality(self) -> float:
        """Returns the *maximum limit* on the possible score the matcher can
        give. This can be an estimate and not necessarily the actual maximum
        score possible, but it must never be less than the actual maximum
        score.
        """

        raise NotImplementedError(self.__class__.__name__)

    def block_quality(self, matcher: Any) -> float:
        """Returns the *maximum limit* on the possible score the matcher can
        give **in its current "block"** (whatever concept of "block" the
        backend might use). This can be an estimate and not necessarily the
        actual maximum score possible, but it must never be less than the
        actual maximum score.

        If this score is less than the minimum score
        required to make the "top N" results, then we can tell the matcher to
        skip ahead to another block with better "quality".
        """

        raise NotImplementedError(self.__class__.__name__)


# Scorer that just returns term weight


class WeightScorer(BaseScorer):
    """A scorer that simply returns the weight as the score. This is useful
    for more complex weighting models to return when they are asked for a
    scorer for fields that aren't scorable (don't store field lengths).
    """

    def __init__(self, maxweight: float) -> None:
        self._maxweight = maxweight

    def supports_block_quality(self) -> bool:
        return True

    def score(self, matcher: Any) -> float:
        return matcher.weight()

    def max_quality(self) -> float:
        return self._maxweight

    def block_quality(self, matcher: Any) -> float:
        return matcher.block_max_weight()

    @classmethod
    def for_(cls, searcher: Any, fieldname: str, text: str) -> WeightScorer:
        ti = searcher.term_info(fieldname, text)
        return cls(ti.max_weight())


# Base scorer for models that only use weight and field length


class WeightLengthScorer(BaseScorer):
    """Base class for scorers where the only per-document variables are term
    weight and field length.

    Subclasses should override the ``_score(weight, length)`` method to return
    the score for a document with the given weight and length, and call the
    ``setup()`` method at the end of the initializer to set up common
    attributes.
    """

    def setup(self, searcher: Any, fieldname: str, text: str) -> WeightScorer | None:
        """Initializes the scorer and then does the busy work of
        adding the ``dfl()`` function and maximum quality attribute.

        This method assumes the initializers of WeightLengthScorer subclasses
        always take ``searcher, offset, fieldname, text`` as the first three
        arguments. Any additional arguments given to this method are passed
        through to the initializer.

        Note: this method calls ``self._score()``, so you should only call it
        in the initializer after setting up whatever attributes ``_score()``
        depends on::

            class MyScorer(WeightLengthScorer):
                def __init__(self, searcher, fieldname, text, parm=1.0):
                    self.parm = parm
                    self.setup(searcher, fieldname, text)

                def _score(self, weight, length):
                    return (weight / (length + 1)) * self.parm
        """

        ti = searcher.term_info(fieldname, text)
        if not searcher.schema[fieldname].scorable:
            return WeightScorer(ti.max_weight())

        self.dfl = lambda docid: searcher.doc_field_length(docid, fieldname, 1)
        self._maxquality = self._score(ti.max_weight(), ti.min_length())
        return None

    def supports_block_quality(self) -> bool:
        return True

    def score(self, matcher: Any) -> float:
        return self._score(matcher.weight(), self.dfl(matcher.id()))

    def max_quality(self) -> float:
        return self._maxquality

    def block_quality(self, matcher: Any) -> float:
        return self._score(matcher.block_max_weight(), matcher.block_min_length())

    def _score(self, weight: float, length: int) -> float:
        # Override this method with the actual scoring function
        raise NotImplementedError(self.__class__.__name__)


# WeightingModel implementations

# Debugging model


class DebugModel(WeightingModel):
    def __init__(self) -> None:
        self.log: list[Any] = []

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> DebugScorer:
        return DebugScorer(searcher, fieldname, text, self.log)


class DebugScorer(BaseScorer):
    def __init__(self, searcher: Any, fieldname: str, text: str, log: list[Any]) -> None:
        ti = searcher.term_info(fieldname, text)
        self._maxweight: float = ti.max_weight()

        self.searcher = searcher
        self.fieldname = fieldname
        self.text = text
        self.log = log

    def supports_block_quality(self) -> bool:
        return True

    def score(self, matcher: Any) -> float:
        fieldname, text = self.fieldname, self.text
        docid = matcher.id()
        w = matcher.weight()
        length = self.searcher.doc_field_length(docid, fieldname)
        self.log.append((fieldname, text, docid, w, length))
        return w

    def max_quality(self) -> float:
        return self._maxweight

    def block_quality(self, matcher: Any) -> float:
        return matcher.block_max_weight()


# BM25F Model


def bm25(idf: float, tf: float, fl: float, avgfl: float, B: float, K1: float) -> float:
    # idf - inverse document frequency
    # tf - term frequency in the current document
    # fl - field length in the current document
    # avgfl - average field length across documents in collection
    # B, K1 - free paramters

    return idf * ((tf * (K1 + 1)) / (tf + K1 * ((1 - B) + B * fl / avgfl)))


class BM25F(WeightingModel):
    """Implements the BM25F scoring algorithm."""

    def __init__(self, B: float = 0.75, K1: float = 1.2, **kwargs: float) -> None:
        """

        >>> from whoosh import scoring
        >>> # Set a custom B value for the "content" field
        >>> w = scoring.BM25F(B=0.75, content_B=1.0, K1=1.5)

        :param B: free parameter, see the BM25 literature. Keyword arguments of
            the form ``fieldname_B`` (for example, ``body_B``) set field-
            specific values for B.
        :param K1: free parameter, see the BM25 literature.
        """

        self.B = B
        self.K1 = K1

        self._field_B: dict[str, float] = {}
        for k, v in kwargs.items():
            if k.endswith("_B"):
                fieldname = k[:-2]
                self._field_B[fieldname] = v

    def supports_block_quality(self) -> bool:
        return True

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> BaseScorer:
        if not searcher.schema[fieldname].scorable:
            return WeightScorer.for_(searcher, fieldname, text)

        if fieldname in self._field_B:
            B = self._field_B[fieldname]
        else:
            B = self.B

        return BM25FScorer(searcher, fieldname, text, B, self.K1, qf=qf)


class BM25FScorer(WeightLengthScorer):
    def __init__(self, searcher: Any, fieldname: str, text: str, B: float, K1: float, qf: int = 1) -> None:
        # IDF and average field length are global statistics, so get them from
        # the top-level searcher
        parent = searcher.get_parent()  # Returns self if no parent
        self.idf = parent.idf(fieldname, text)
        self.avgfl = parent.avg_field_length(fieldname) or 1

        self.B = B
        self.K1 = K1
        self.qf = qf
        self.setup(searcher, fieldname, text)

    def _score(self, weight: float, length: int) -> float:
        s = bm25(self.idf, weight, length, self.avgfl, self.B, self.K1)
        return s


# DFree model


def dfree(tf: float, cf: float, qf: float, dl: float, fl: float) -> float:
    # tf - term frequency in current document
    # cf - term frequency in collection
    # qf - term frequency in query
    # dl - field length in current document
    # fl - total field length across all documents in collection
    prior = tf / dl
    post = (tf + 1.0) / (dl + 1.0)
    invpriorcol = fl / cf
    norm = tf * log(post / prior)

    return (
        qf
        * norm
        * (
            tf * (log(prior * invpriorcol))
            + (tf + 1.0) * (log(post * invpriorcol))
            + 0.5 * log(post / prior)
        )
    )


class DFree(WeightingModel):
    """Implements the DFree scoring model from Terrier.

    See http://terrier.org/
    """

    def supports_block_quality(self) -> bool:
        return True

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> BaseScorer:
        if not searcher.schema[fieldname].scorable:
            return WeightScorer.for_(searcher, fieldname, text)

        return DFreeScorer(searcher, fieldname, text, qf=qf)


class DFreeScorer(WeightLengthScorer):
    def __init__(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> None:
        # Total term weight and total field length are global statistics, so
        # get them from the top-level searcher
        parent = searcher.get_parent()  # Returns self if no parent
        self.cf = parent.weight(fieldname, text)
        self.fl = parent.field_length(fieldname)

        self.qf = qf
        self.setup(searcher, fieldname, text)

    def _score(self, weight: float, length: int) -> float:
        return dfree(weight, self.cf, self.qf, length, self.fl)


# PL2 model

rec_log2_of_e = 1.0 / log(2)


def pl2(tf: float, cf: float, qf: float, dc: int, fl: float, avgfl: float, c: float) -> float:
    # tf - term frequency in the current document
    # cf - term frequency in the collection
    # qf - term frequency in the query
    # dc - doc count
    # fl - field length in the current document
    # avgfl - average field length across all documents
    # c -free parameter

    TF = tf * log(1.0 + (c * avgfl) / fl)
    norm = 1.0 / (TF + 1.0)
    f = cf / dc
    return (
        norm
        * qf
        * (
            TF * log(1.0 / f)
            + f * rec_log2_of_e
            + 0.5 * log(2 * pi * TF)
            + TF * (log(TF) - rec_log2_of_e)
        )
    )


class PL2(WeightingModel):
    """Implements the PL2 scoring model from Terrier.

    See http://terrier.org/
    """

    def __init__(self, c: float = 1.0) -> None:
        self.c = c

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> BaseScorer:
        if not searcher.schema[fieldname].scorable:
            return WeightScorer.for_(searcher, fieldname, text)

        return PL2Scorer(searcher, fieldname, text, self.c, qf=qf)


class PL2Scorer(WeightLengthScorer):
    def __init__(self, searcher: Any, fieldname: str, text: str, c: float, qf: int = 1) -> None:
        # Total term weight, document count, and average field length are
        # global statistics, so get them from the top-level searcher
        parent = searcher.get_parent()  # Returns self if no parent
        self.cf = parent.frequency(fieldname, text)
        self.dc = parent.doc_count_all()
        self.avgfl = parent.avg_field_length(fieldname) or 1

        self.c = c
        self.qf = qf
        self.setup(searcher, fieldname, text)

    def _score(self, weight: float, length: int) -> float:
        return pl2(weight, self.cf, self.qf, self.dc, length, self.avgfl, self.c)


# Simple models


class Frequency(WeightingModel):
    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> WeightScorer:
        maxweight = searcher.term_info(fieldname, text).max_weight()
        return WeightScorer(maxweight)


class TF_IDF(WeightingModel):
    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> TF_IDFScorer:
        # IDF is a global statistic, so get it from the top-level searcher
        parent = searcher.get_parent()  # Returns self if no parent
        idf = parent.idf(fieldname, text)

        maxweight = searcher.term_info(fieldname, text).max_weight()
        return TF_IDFScorer(maxweight, idf)


class TF_IDFScorer(BaseScorer):
    def __init__(self, maxweight: float, idf: float) -> None:
        self._maxquality = maxweight * idf
        self.idf = idf

    def supports_block_quality(self) -> bool:
        return True

    def score(self, matcher: Any) -> float:
        return matcher.weight() * self.idf

    def max_quality(self) -> float:
        return self._maxquality

    def block_quality(self, matcher: Any) -> float:
        return matcher.block_max_weight() * self.idf


# Utility models


class Weighting(WeightingModel):
    """This class provides backwards-compatibility with the old weighting
    class architecture, so any existing custom scorers don't need to be
    rewritten.
    """

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> Weighting.CompatibilityScorer:
        return self.CompatibilityScorer(searcher, fieldname, text, self.score)

    def score(self, searcher: Any, fieldname: str, text: str, docnum: int, weight: float) -> float:
        raise NotImplementedError

    class CompatibilityScorer(BaseScorer):
        def __init__(self, searcher: Any, fieldname: str, text: str, scoremethod: Callable[..., float]) -> None:
            self.searcher = searcher
            self.fieldname = fieldname
            self.text = text
            self.scoremethod = scoremethod

        def score(self, matcher: Any) -> float:
            return self.scoremethod(
                self.searcher, self.fieldname, self.text, matcher.id(), matcher.weight()
            )


class FunctionWeighting(WeightingModel):
    """Uses a supplied function to do the scoring. For simple scoring functions
    and experiments this may be simpler to use than writing a full weighting
    model class and scorer class.

    The function should accept the arguments
    ``searcher, fieldname, text, matcher``.

    For example, the following function will score documents based on the
    earliest position of the query term in the document::

        def pos_score_fn(searcher, fieldname, text, matcher):
            poses = matcher.value_as("positions")
            return 1.0 / (poses[0] + 1)

        pos_weighting = scoring.FunctionWeighting(pos_score_fn)
        with myindex.searcher(weighting=pos_weighting) as s:
            results = s.search(q)

    Note that the searcher passed to the function may be a per-segment searcher
    for performance reasons. If you want to get global statistics inside the
    function, you should use ``searcher.get_parent()`` to get the top-level
    searcher. (However, if you are using global statistics, you should probably
    write a real model/scorer combo so you can cache them on the object.)
    """

    def __init__(self, fn: Callable[..., float]) -> None:
        self.fn = fn

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> FunctionWeighting.FunctionScorer:
        return self.FunctionScorer(self.fn, searcher, fieldname, text, qf=qf)

    class FunctionScorer(BaseScorer):
        def __init__(self, fn: Callable[..., float], searcher: Any, fieldname: str, text: str, qf: int = 1) -> None:
            self.fn = fn
            self.searcher = searcher
            self.fieldname = fieldname
            self.text = text
            self.qf = qf

        def score(self, matcher: Any) -> float:
            return self.fn(self.searcher, self.fieldname, self.text, matcher)


class MultiWeighting(WeightingModel):
    """Chooses from multiple scoring algorithms based on the field."""

    def __init__(self, default: WeightingModel, **weightings: WeightingModel) -> None:
        """The only non-keyword argument specifies the default
        :class:`Weighting` instance to use. Keyword arguments specify
        Weighting instances for specific fields.

        For example, to use ``BM25`` for most fields, but ``Frequency`` for
        the ``id`` field and ``TF_IDF`` for the ``keys`` field::

            mw = MultiWeighting(BM25(), id=Frequency(), keys=TF_IDF())

        :param default: the Weighting instance to use for fields not
            specified in the keyword arguments.
        """

        self.default = default
        # Store weighting functions by field name
        self.weightings = weightings

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> BaseScorer:
        w = self.weightings.get(fieldname, self.default)
        return w.scorer(searcher, fieldname, text, qf=qf)


class ReverseWeighting(WeightingModel):
    """Wraps a weighting object and subtracts the wrapped model's scores from
    0, essentially reversing the weighting model.
    """

    def __init__(self, weighting: WeightingModel) -> None:
        self.weighting = weighting

    def scorer(self, searcher: Any, fieldname: str, text: str, qf: int = 1) -> ReverseWeighting.ReverseScorer:
        subscorer = self.weighting.scorer(searcher, fieldname, text, qf=qf)
        return ReverseWeighting.ReverseScorer(subscorer)

    class ReverseScorer(BaseScorer):
        def __init__(self, subscorer: BaseScorer) -> None:
            self.subscorer = subscorer

        def supports_block_quality(self) -> bool:
            return self.subscorer.supports_block_quality()

        def score(self, matcher: Any) -> float:
            return 0 - self.subscorer.score(matcher)

        def max_quality(self) -> float:
            return 0 - self.subscorer.max_quality()

        def block_quality(self, matcher: Any) -> float:
            return 0 - self.subscorer.block_quality(matcher)


# class PositionWeighting(WeightingModel):
#    def __init__(self, reversed=False):
#        self.reversed = reversed
#
#    def scorer(self, searcher, fieldname, text, qf=1):
#        return PositionWeighting.PositionScorer()
#
#    class PositionScorer(BaseScorer):
#        def score(self, matcher):
#            p = min(span.pos for span in matcher.spans())
#            if self.reversed:
#                return p
#            else:
#                return 0 - p
