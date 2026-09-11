"""A LangChain retriever backed by Whoosh BM25 (pure-Python lexical search).

LangChain pipelines usually reach for a *vector* store, but dense retrieval has
a well-known blind spot: it can quietly miss the *exact* tokens that matter most
(product SKUs, function names, error codes like ``ERR_2043``, gene symbols,
ticket IDs). A lexical BM25 retriever is the classic complement -- and Whoosh
gives you one in pure Python, with no server, no native wheels, and an index
that is just a folder on disk.

``WhooshRetriever`` is a drop-in ``langchain_core.retrievers.BaseRetriever`` you
can wire into any chain, ``EnsembleRetriever`` (for hybrid search), or LangGraph
agent exactly like any other retriever::

    from langchain_whoosh import WhooshRetriever

    retriever = WhooshRetriever.from_texts(
        texts=["Whoosh is a pure-Python search library.",
               "BM25 ranks by term rarity."],
        ids=["a", "b"],
        metadatas=[{"src": "readme"}, {"src": "docs"}],
        k=4,
    )
    docs = retriever.invoke("pure python search")   # -> list[Document]

For true *hybrid* search, drop this retriever and your vector retriever into
LangChain's ``EnsembleRetriever``; it does Reciprocal Rank Fusion for you.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from whoosh.retrieval import WhooshSearch

__all__ = ["WhooshRetriever"]


class WhooshRetriever(BaseRetriever):
    """A LangChain retriever that ranks documents with Whoosh BM25.

    Parameters
    ----------
    core:
        A :class:`whoosh.retrieval.WhooshSearch` instance. Build one directly
        (``WhooshSearch.from_texts(...)`` / ``WhooshSearch.open_dir(path)``) for
        full control, or use :meth:`from_texts` / :meth:`from_index` below.
    k:
        The maximum number of documents to return per query (default ``4``).
    """

    # ``Any`` keeps both pydantic v1 and v2 happy with an arbitrary type.
    core: Any
    k: int = 4

    def _get_relevant_documents(  # noqa: D401 - langchain-core hook
        self, query: str, *, run_manager: Any = None
    ) -> list[Document]:
        return [
            Document(
                page_content=hit.text,
                metadata={"id": hit.id, "score": hit.score, **hit.metadata},
            )
            for hit in self.core.search(query, self.k)
        ]

    # ------------------------------------------------------------------ #
    # Convenience constructors
    # ------------------------------------------------------------------ #
    @classmethod
    def from_texts(
        cls,
        texts: Sequence[str],
        *,
        ids: Sequence[str] | None = None,
        metadatas: Sequence[dict] | None = None,
        path: str | None = None,
        k: int = 4,
    ) -> WhooshRetriever:
        """Build an in-memory (or on-disk) index from parallel lists.

        Pass ``path`` to persist the index to a directory; omit it to keep the
        whole thing in memory (handy for tests and notebooks).
        """
        core = WhooshSearch.from_texts(
            texts=texts, ids=ids, metadatas=metadatas, path=path
        )
        return cls(core=core, k=k)

    @classmethod
    def from_index(cls, path: str, *, k: int = 4) -> WhooshRetriever:
        """Open an index previously built with ``from_texts(..., path=...)``."""
        return cls(core=WhooshSearch.open_dir(path), k=k)
