"""
Whoosh as a BM25 retriever for RAG (+ hybrid search)
====================================================

Retrieval-Augmented Generation lives or dies on retrieval: if the right chunk
isn't in the model's context window, the model can't use it. Dense (vector)
retrieval is great at *meaning* -- "car" matches "automobile" -- but it has a
well-known blind spot: it can quietly fail on the *exact* tokens that matter
most (product SKUs, function names, error codes like ``ERR_2043``, gene symbols,
ticket IDs). Lexical BM25 is the classic complement: it rewards documents that
contain the query's actual terms, weighted by rarity and length.

Combining the two -- *hybrid search* -- reliably beats either one alone, because
they fail on different queries. This example shows the whole pattern end to end,
runnable with nothing but Whoosh and the standard library:

  1. Index your chunks with Whoosh and retrieve with BM25 (`keyword_search`)
  2. A *stand-in* dense retriever (`vector_search`) so the demo actually runs
     with no vector DB, GPU, or embedding API -- swap in FAISS/Chroma/pgvector
  3. Reciprocal Rank Fusion (`reciprocal_rank_fusion`) to merge the rankings
  4. Assemble the fused top-k chunk text into an LLM context window

Whoosh is a *lexical* engine -- it does not compute embeddings. That's the
point: it handles the keyword half in pure Python (no server, no native wheels,
the index is just a folder) so you can pair it with whatever vector store you
already use.

Run it:  python examples/rag_retriever.py

Everything runs in memory (RamStorage) so there are no files to clean up.
"""

from whoosh import scoring
from whoosh.fields import ID, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import MultifieldParser, OrGroup

# --------------------------------------------------------------------------
# A tiny corpus of "chunks". In real RAG you split documents into passages and
# store a stable `id` for each so you can join back to your vector store.
# --------------------------------------------------------------------------
CHUNKS = [
    (
        "c1",
        "Routine car maintenance: check the engine oil, tyre pressure and brakes every few months.",
    ),
    (
        "c2",
        "Python is a popular programming language for data science and machine learning.",
    ),
    (
        "c3",
        "Cellular respiration converts glucose into ATP energy inside the mitochondria.",
    ),
    (
        "c4",
        "Vector databases store embeddings so you can run semantic similarity search.",
    ),
    (
        "c5",
        "Troubleshooting guide: error ERR_2043 means the payment gateway rejected the token.",
    ),
    ("c6", "The mitochondria is often called the powerhouse of the cell."),
]


def build_index():
    """Index the chunks in memory and return the Whoosh index."""
    schema = Schema(
        id=ID(stored=True, unique=True),
        text=TEXT(stored=True),
    )
    ix = RamStorage().create_index(schema)
    writer = ix.writer()
    for chunk_id, text in CHUNKS:
        writer.add_document(id=chunk_id, text=text)
    writer.commit()
    return ix


def keyword_search(ix, query, k=10):
    """Return up to k chunk ids ranked by Whoosh BM25 relevance.

    Using an OrGroup parser keeps recall high: a chunk matches if it contains
    *any* of the query terms, and BM25 still ranks the best-matching chunks
    first (rewarding rarer, more discriminating terms).
    """
    with ix.searcher(weighting=scoring.BM25F()) as s:
        parser = MultifieldParser(["text"], schema=ix.schema, group=OrGroup)
        q = parser.parse(query)
        return [hit["id"] for hit in s.search(q, limit=k)]


# --------------------------------------------------------------------------
# A STAND-IN dense retriever.
#
# Real dense retrieval would embed the query and search FAISS/Chroma/pgvector.
# To keep this file dependency-free *and* to honestly demonstrate why hybrid
# search wins, we fake "semantic" matching with a tiny concept lexicon: a query
# concept matches a chunk if they share a concept, even when the surface words
# differ ("automobile" -> the "car" chunk). Like a real embedding model, it is
# good at meaning but blind to rare literal tokens it never learned (ERR_2043).
# Swap this whole function for your production retriever; the interface is just
# (query, k) -> list of chunk ids.
# --------------------------------------------------------------------------
_CONCEPTS = {
    "c1": {"vehicle", "maintenance"},
    "c2": {"programming", "ml"},
    "c3": {"biology", "energy"},
    "c4": {"vectors", "search"},
    "c5": {"payments", "errors"},
    "c6": {"biology"},
}
_QUERY_CONCEPTS = {
    "automobile": {"vehicle"},
    "car": {"vehicle"},
    "vehicle": {"vehicle"},
    "servicing": {"maintenance"},
    "maintenance": {"maintenance"},
    "coding": {"programming"},
    "energy": {"energy"},
    "powerhouse": {"energy", "biology"},
    "cell": {"biology"},
    "payment": {"payments"},
    "embeddings": {"vectors"},
}


def vector_search(query, k=10):
    """Stand-in for a real embedding retriever: concept-overlap similarity."""
    q_concepts = set()
    for word in query.lower().split():
        q_concepts |= _QUERY_CONCEPTS.get(word.strip(".,?!"), set())
    scored = []
    for chunk_id, concepts in _CONCEPTS.items():
        overlap = len(q_concepts & concepts)
        if overlap:
            scored.append((overlap, chunk_id))
    scored.sort(reverse=True)
    return [chunk_id for _, chunk_id in scored[:k]]


def reciprocal_rank_fusion(rankings, k=60):
    """Fuse several ranked id-lists into one.

    RRF scores each id by ``1 / (k + rank)`` summed across every ranking it
    appears in, so an id ranked highly by *either* retriever floats to the top
    and ids found by *both* win outright. ``k=60`` is the standard constant;
    it damps the influence of any single list's exact positions.
    """
    scores = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda k: scores[k], reverse=True)


def hybrid_search(ix, query, k=10):
    """Combine Whoosh BM25 with the (stand-in) dense retriever via RRF."""
    lexical = keyword_search(ix, query, k=k)
    dense = vector_search(query, k=k)
    return reciprocal_rank_fusion([lexical, dense])[:k]


def build_context(ix, chunk_ids):
    """Fetch chunk text back for the LLM context window, in ranked order."""
    with ix.searcher() as s:
        texts = []
        for cid in chunk_ids:
            doc = s.document(id=cid)
            if doc:
                texts.append(doc["text"])
        return "\n\n".join(texts)


def _demo():
    ix = build_index()

    print("=" * 70)
    print("Why hybrid beats either retriever alone")
    print("=" * 70)

    # 1) A synonym query: the user says "automobile", the chunk says "car".
    #    BM25 has no literal term to match; the dense stand-in bridges meaning.
    q1 = "automobile servicing"
    print(f"\nQuery: {q1!r}")
    print(
        f"  BM25 (lexical): {keyword_search(ix, q1)}   <- misses c1 (no word 'automobile')"
    )
    print(
        f"  Dense (stand-in): {vector_search(q1)}   <- bridges 'automobile' -> car chunk"
    )
    print(f"  Hybrid (RRF):   {hybrid_search(ix, q1)}   <- recovers c1")

    # 2) A rare literal token: an error code the embedding model never learned.
    #    Dense misses it; BM25 nails it because the exact token is rare.
    q2 = "ERR_2043 rejected token"
    print(f"\nQuery: {q2!r}")
    print(f"  BM25 (lexical): {keyword_search(ix, q2)}   <- nails c5 on the exact code")
    print(
        f"  Dense (stand-in): {vector_search(q2)}   <- misses: no concept for a rare code"
    )
    print(f"  Hybrid (RRF):   {hybrid_search(ix, q2)}   <- keeps c5 on top")

    # 3) Assemble a context window for the LLM from the fused top-k.
    print("\n" + "=" * 70)
    print("Assembling an LLM context window from the fused top-k")
    print("=" * 70)
    q3 = "energy in the mitochondria"
    ids = hybrid_search(ix, q3, k=3)
    print(f"\nQuery: {q3!r}  ->  fused ids: {ids}")
    context = build_context(ix, ids)
    print("\n--- context passed to the model ---")
    print(context)
    print("--- end context ---")


if __name__ == "__main__":
    _demo()
