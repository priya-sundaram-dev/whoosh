"""Integration tests for WhooshRetriever (requires langchain-core + whoosh3)."""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from langchain_whoosh import WhooshRetriever

TEXTS = [
    "Whoosh is a fast pure-Python full-text search library.",
    "BM25 ranks documents by term rarity and frequency.",
    "Elasticsearch is a distributed search engine written in Java.",
]
IDS = ["a", "b", "c"]
METADATAS = [{"src": "readme"}, {"src": "docs"}, {"src": "wiki"}]


def _retriever(k: int = 4) -> WhooshRetriever:
    return WhooshRetriever.from_texts(
        texts=TEXTS, ids=IDS, metadatas=METADATAS, k=k
    )


def test_is_base_retriever():
    assert isinstance(_retriever(), BaseRetriever)


def test_invoke_returns_documents():
    docs = _retriever().invoke("pure python search")
    assert docs, "expected at least one hit"
    assert all(isinstance(d, Document) for d in docs)
    # The exact-token query should float the Whoosh readme doc to the top.
    assert docs[0].metadata["id"] == "a"


def test_metadata_is_preserved_and_scored():
    docs = _retriever().invoke("term rarity")
    top = docs[0]
    assert top.metadata["id"] == "b"
    assert top.metadata["src"] == "docs"
    assert isinstance(top.metadata["score"], float)
    assert top.metadata["score"] > 0


def test_k_limits_results():
    docs = _retriever(k=1).invoke("search")
    assert len(docs) == 1


def test_empty_query_returns_nothing():
    assert _retriever().invoke("   ") == []


def test_from_index_roundtrip(tmp_path):
    WhooshRetriever.from_texts(
        texts=TEXTS, ids=IDS, metadatas=METADATAS, path=str(tmp_path), k=4
    )
    reopened = WhooshRetriever.from_index(str(tmp_path), k=4)
    docs = reopened.invoke("distributed java engine")
    assert docs[0].metadata["id"] == "c"
