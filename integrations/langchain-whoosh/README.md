# langchain-whoosh

A pure-Python **BM25 (lexical) retriever for [LangChain](https://github.com/langchain-ai/langchain)**, powered by [Whoosh](https://github.com/priya-sundaram-dev/whoosh).

LangChain pipelines usually reach for a *vector* store, but dense retrieval has a
well-known blind spot: it can quietly miss the *exact* tokens that matter most —
product SKUs, function names, error codes like `ERR_2043`, gene symbols, ticket
IDs. A lexical BM25 retriever is the classic complement, and Whoosh gives you one
in **pure Python**: no server, no native wheels, and an index that is just a
folder on disk.

## Install

```bash
pip install langchain-whoosh
```

This pulls in `langchain-core` and `whoosh3` (the maintained Whoosh fork).

## Quick start

```python
from langchain_whoosh import WhooshRetriever

retriever = WhooshRetriever.from_texts(
    texts=[
        "Whoosh is a pure-Python full-text search library.",
        "BM25 ranks documents by term rarity and frequency.",
    ],
    ids=["a", "b"],
    metadatas=[{"src": "readme"}, {"src": "docs"}],
    k=4,
)

docs = retriever.invoke("pure python search")
for d in docs:
    print(d.metadata["score"], d.page_content)
```

Each result is a standard `langchain_core.documents.Document`; the original
`id`, the BM25 `score`, and any metadata you supplied are attached under
`Document.metadata`.

## Persist an index to disk

```python
# Build once …
WhooshRetriever.from_texts(texts=texts, ids=ids, path="./my_index")

# … reopen later without re-indexing.
retriever = WhooshRetriever.from_index("./my_index", k=8)
```

## Hybrid search (lexical + vector)

Drop this retriever and your vector retriever into LangChain's
[`EnsembleRetriever`](https://python.langchain.com/docs/how_to/ensemble_retriever/);
it does Reciprocal Rank Fusion for you:

```python
from langchain.retrievers import EnsembleRetriever

hybrid = EnsembleRetriever(
    retrievers=[whoosh_retriever, vector_retriever],
    weights=[0.5, 0.5],
)
```

## License

BSD-2-Clause, matching Whoosh. See the [Whoosh repository](https://github.com/priya-sundaram-dev/whoosh) for the full project, docs, and issue tracker.
