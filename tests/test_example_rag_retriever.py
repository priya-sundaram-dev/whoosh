"""Smoke tests for examples/rag_retriever.py.

These keep the RAG / hybrid-search example (referenced from the README and the
"Whoosh for RAG" guide) runnable, so the marketing claim always has working
code behind it.
"""

import importlib.util
import pathlib

import pytest

_EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "rag_retriever.py"


@pytest.fixture(scope="module")
def rag():
    spec = importlib.util.spec_from_file_location("rag_retriever", _EXAMPLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_keyword_search_ranks_exact_terms(rag):
    ix = rag.build_index()
    # A rare literal token (an error code) must be found by BM25.
    assert rag.keyword_search(ix, "ERR_2043 rejected token")[0] == "c5"


def test_dense_bridges_synonyms_but_misses_rare_tokens(rag):
    # The stand-in dense retriever bridges "automobile" -> the "car" chunk...
    assert "c1" in rag.vector_search("automobile servicing")
    # ...but has no concept for a rare literal code.
    assert rag.vector_search("ERR_2043 rejected token") == []


def test_hybrid_recovers_both_failure_modes(rag):
    ix = rag.build_index()
    # BM25 alone misses the synonym query; hybrid recovers it.
    assert rag.keyword_search(ix, "automobile servicing") == []
    assert "c1" in rag.hybrid_search(ix, "automobile servicing")
    # Dense alone misses the rare code; hybrid keeps it.
    assert "c5" in rag.hybrid_search(ix, "ERR_2043 rejected token")


def test_rrf_prefers_ids_found_by_both(rag):
    fused = rag.reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
    # "b" appears in both lists, so it should rank first.
    assert fused[0] == "b"


def test_build_context_joins_chunk_text(rag):
    ix = rag.build_index()
    ids = rag.hybrid_search(ix, "energy in the mitochondria", k=3)
    context = rag.build_context(ix, ids)
    assert "mitochondria" in context
    assert context.count("\n\n") == len(ids) - 1
