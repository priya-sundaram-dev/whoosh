# Whoosh examples

Runnable, self-contained scripts that show how to use Whoosh for real tasks.
Every file here is standalone: it builds a small index in a temp directory,
runs, prints its output, and cleans up after itself — so you can read one,
run it, and adapt it.

```bash
pip install whoosh3
python examples/quickstart.py
```

Most scripts only need `whoosh3` itself. The few that integrate with a web
framework or an AI library say so below and carry their own `pip install`
line in the module docstring.

## Start here

| Example | What it shows |
| --- | --- |
| [`quickstart.py`](quickstart.py) | Index a few documents and search them — the smallest complete program. |
| [`tutorial.py`](tutorial.py) | The whole "Whoosh in 5 minutes" tutorial as one runnable script. |

## Index management

| Example | What it shows |
| --- | --- |
| [`index_sync.py`](index_sync.py) | Keep an index in sync with changing data: upserts, deletes, and folder reconciliation. |
| [`resource_management.py`](resource_management.py) | Closing indexes, readers, and searchers cleanly (and why it matters). |

## Core search features

| Example | What it shows |
| --- | --- |
| [`scoring_and_sorting.py`](scoring_and_sorting.py) | Custom scoring, sorting by field, and controlling result order. |
| [`highlighting.py`](highlighting.py) | Result highlighting and snippet extraction around matched terms. |
| [`faceted_search.py`](faceted_search.py) | Faceted navigation — sidebar filter counts and drill-down. |
| [`custom_analyzers.py`](custom_analyzers.py) | Compose your own text-processing pipeline from tokenizers and filters. |
| [`did_you_mean.py`](did_you_mean.py) | "Did you mean…?" spell-checking and query correction. |
| [`autocomplete.py`](autocomplete.py) | Search-as-you-type / autocomplete suggestions. |
| [`acronyms.py`](acronyms.py) | Searching for tricky tokens like `R&D`, `C++`, `C#`, and `.NET`. |
| [`signed_numbers.py`](signed_numbers.py) | Indexing signed numbers (and why default text analysis drops the sign). |

## Performance & scaling

| Example | What it shows |
| --- | --- |
| [`parallel_indexing.py`](parallel_indexing.py) | The multi-thread indexing pattern for free-threaded CPython. |
| [`parallel_search.py`](parallel_search.py) | The multi-thread query pattern for free-threaded CPython. |
| [`benchmark_vs_sqlite.py`](benchmark_vs_sqlite.py) | A head-to-head benchmark against SQLite FTS5. |

## Web apps & command line

| Example | What it shows | Extra install |
| --- | --- | --- |
| [`flask_app.py`](flask_app.py) | A small, production-shaped full-text search web app. | `flask` |
| [`fastapi_app.py`](fastapi_app.py) | A production-shaped search API. | `fastapi`, `uvicorn[standard]` |
| [`django_app.py`](django_app.py) | Portable full-text search in Django without Postgres or Elasticsearch. | `django` |
| [`search_cli.py`](search_cli.py) | A tiny command-line search tool built on Whoosh. | — |
| [`static_site_search.py`](static_site_search.py) | Add search to a static site (cookbook recipe). | — |

## AI / LLM integrations

| Example | What it shows | Extra install |
| --- | --- | --- |
| [`rag_retriever.py`](rag_retriever.py) | Whoosh as a BM25 retriever for RAG, plus hybrid (lexical + dense) search. | — |
| [`langchain_retriever.py`](langchain_retriever.py) | Use Whoosh as a LangChain retriever. | `whoosh3[langchain]` |
| [`llamaindex_retriever.py`](llamaindex_retriever.py) | Use Whoosh as a LlamaIndex retriever. | `whoosh3[llamaindex]` |
| [`mcp_server.py`](mcp_server.py) | Expose a Whoosh index to LLM agents as an MCP server. | `whoosh3[mcp]` |

---

Found a rough edge or want an example that isn't here? Open an issue or a pull
request — new example scripts are very welcome, and several of these started as
questions from users.
