"""Parallel search: the blessed multi-thread query pattern for free-threaded CPython.

The companion to ``examples/parallel_indexing.py``. Where that example fans a
*build* across threads, this one fans a *query workload* across threads.

Searching in Whoosh is CPU-bound pure-Python work -- parsing the query, walking
postings, scoring, and collecting hits. On a normal (GIL-enabled) CPython build,
running many queries across threads does not speed them up: only one thread runs
Python at a time. On a **free-threaded** build (``3.13t``/``3.14t``, PEP 703)
the GIL is gone, so a batch of independent queries can finally scale across real
cores -- no C extension required. This is the classic search-server shape: many
concurrent read-only requests against one shared index.

This example follows the per-object concurrency contract exactly
(https://priya-sundaram-dev.github.io/whoosh/docs/threads.html):

  * A built ``Index`` is read-only after creation and safe to share across
    threads -- every worker opens its searcher *from the one shared index*.
  * A ``Searcher`` is **not** safe to drive from two threads at once, so each
    worker thread gets **its own** searcher (created lazily, once per thread,
    and reused for every query that thread handles). No searcher is shared
    between threads; none is thrown away per query (that would discard the
    field caches that make search fast).

The result is a fan-out pipeline:

    one shared index
        ->  N worker threads, each with its own searcher   (parallel, CPU-bound)
        ->  each thread runs its slice of the query batch
        ->  results collected and checked against a serial run

Run::

    python examples/parallel_search.py                    # auto worker count
    python examples/parallel_search.py --docs 20000 --queries 4000 --workers 4
    python examples/parallel_search.py --check            # correctness only

On a free-threaded build you should see the parallel wall-clock time drop below
the serial baseline as workers increase; on a GIL build the two are about the
same (this is expected, and the script says so). Requires only the standard
library plus Whoosh itself.
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import QueryParser

# A small vocabulary so queries reliably match something. Stemming analysis is
# deliberately included: parsing a query runs the same analyzer as indexing, so
# it is genuine per-query CPU-bound Python work -- the kind free-threaded builds
# let you parallelise.
WORDS = (
    "search engine python library index document token analyzer query parser "
    "ranking relevance scoring highlight facet storage segment posting term "
    "vector field schema writer reader stemming tokenizer filter fast pure "
    "memory disk network cluster shard replica cache latency throughput data "
    "structure algorithm sort merge trie automaton regex fuzzy prefix wildcard"
).split()


def make_schema() -> Schema:
    return Schema(
        id=ID(stored=True, unique=True), body=TEXT(analyzer=StemmingAnalyzer())
    )


def make_corpus(n: int, seed: int = 1234) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    docs = []
    for i in range(n):
        length = rng.randint(40, 120)
        body = " ".join(rng.choice(WORDS) for _ in range(length))
        docs.append((str(i), body))
    return docs


def make_queries(n: int, seed: int = 99) -> list[str]:
    """A deterministic batch of one- and two-term queries drawn from the vocab."""
    rng = random.Random(seed)
    queries = []
    for _ in range(n):
        if rng.random() < 0.5:
            queries.append(rng.choice(WORDS))
        else:
            queries.append(f"{rng.choice(WORDS)} {rng.choice(WORDS)}")
    return queries


def gil_status() -> str:
    """Human-readable description of whether this build is free-threaded."""
    is_gil_enabled = getattr(sys, "_is_gil_enabled", None)
    if is_gil_enabled is None:
        return "GIL build (standard CPython; threads do not run Python in parallel)"
    if is_gil_enabled():
        return (
            "free-threaded build, but GIL is currently ENABLED "
            "(set PYTHON_GIL=0 or run without a GIL-requiring extension to scale)"
        )
    return "free-threaded build, GIL DISABLED (pure-Python work scales across cores)"


def build_index(docs: list[tuple[str, str]], where: str) -> str:
    """Build the one shared, read-only index everyone searches."""
    d = os.path.join(where, "index")
    os.makedirs(d, exist_ok=True)
    ix = index.create_in(d, make_schema())
    w = ix.writer(limitmb=128)
    for doc_id, body in docs:
        w.add_document(id=doc_id, body=body)
    w.commit(optimize=True)
    ix.close()
    return d


def run_one(searcher, parser: QueryParser, text: str) -> tuple[str, ...]:
    """Run one query, return the matched stored ids as a stable, comparable key."""
    q = parser.parse(text)
    hits = searcher.search(q, limit=10)
    return tuple(hit["id"] for hit in hits)


# --------------------------------------------------------------------------- #
# Serial baseline: one searcher, one thread.
# --------------------------------------------------------------------------- #
def search_serial(ix, queries: list[str]) -> tuple[float, list[tuple[str, ...]]]:
    parser = QueryParser("body", ix.schema)
    with ix.searcher() as s:
        t0 = time.perf_counter()
        results = [run_one(s, parser, text) for text in queries]
        elapsed = time.perf_counter() - t0
    return elapsed, results


# --------------------------------------------------------------------------- #
# Parallel: N worker threads, each with its own searcher on the shared index.
# --------------------------------------------------------------------------- #
def search_parallel(
    ix, queries: list[str], workers: int
) -> tuple[float, list[tuple[str, ...]]]:
    parser = QueryParser("body", ix.schema)

    # One searcher per worker thread, created lazily and reused. threading.local
    # guarantees a distinct searcher object per thread, so no searcher is ever
    # driven by two threads at once -- the contract the concurrency guide names.
    local = threading.local()
    created: list = []
    created_lock = threading.Lock()

    def get_searcher():
        s = getattr(local, "searcher", None)
        if s is None:
            s = ix.searcher()
            local.searcher = s
            with created_lock:
                created.append(s)
        return s

    def worker(text: str) -> tuple[str, ...]:
        return run_one(get_searcher(), parser, text)

    try:
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(worker, queries))
        elapsed = time.perf_counter() - t0
    finally:
        for s in created:
            s.close()
    return elapsed, results


def verify_equivalent(
    serial: list[tuple[str, ...]], parallel: list[tuple[str, ...]]
) -> None:
    """Parallel search must return exactly the serial results, in query order."""
    assert len(serial) == len(parallel), (
        f"result count mismatch: {len(serial)} != {len(parallel)}"
    )
    for i, (a, b) in enumerate(zip(serial, parallel)):
        assert a == b, f"query #{i} differs: serial={a!r} parallel={b!r}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", type=int, default=20000, help="number of documents")
    ap.add_argument(
        "--queries", type=int, default=4000, help="number of queries to run"
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=min(8, (os.cpu_count() or 2)),
        help="number of worker threads (default: min(8, CPU count))",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="only verify parallel == serial correctness, skip timing report",
    )
    args = ap.parse_args()

    print(f"Runtime: {gil_status()}")
    print(
        f"CPUs: {os.cpu_count()}  workers: {args.workers}  "
        f"docs: {args.docs}  queries: {args.queries}"
    )
    print("Building corpus + shared index...")
    docs = make_corpus(args.docs)
    queries = make_queries(args.queries)

    where = tempfile.mkdtemp(prefix="whoosh-parallel-search-")
    try:
        index_dir = build_index(docs, where)
        ix = index.open_dir(index_dir)
        try:
            print("\nSerial baseline (1 searcher)...")
            serial_t, serial_results = search_serial(ix, queries)
            print(f"  serial:   {serial_t:6.2f}s  ({args.queries} queries)")

            print(f"Parallel ({args.workers} threads, 1 searcher each)...")
            parallel_t, parallel_results = search_parallel(ix, queries, args.workers)
            print(f"  parallel: {parallel_t:6.2f}s")

            print("\nVerifying parallel results == serial results...")
            verify_equivalent(serial_results, parallel_results)
            print("  OK: parallel search returns identical results.")

            if not args.check:
                speedup = serial_t / parallel_t if parallel_t else float("nan")
                print(f"\nSpeedup: {speedup:.2f}x")
                is_gil_enabled = getattr(sys, "_is_gil_enabled", None)
                if is_gil_enabled is None or is_gil_enabled():
                    print(
                        "  Note: on a GIL build a speedup near 1x is EXPECTED -- "
                        "only one thread\n  runs Python at a time, so thread pool "
                        "overhead can even make it slightly\n  slower. Run this on "
                        "a free-threaded build (3.13t/3.14t, PYTHON_GIL=0) to see\n"
                        "  the query batch pull ahead."
                    )
                else:
                    print(
                        "  Free-threaded build: a speedup above 1x means pure-"
                        "Python search is\n  scaling across cores without any C "
                        "extension -- the search-server shape."
                    )
        finally:
            ix.close()
    finally:
        shutil.rmtree(where, ignore_errors=True)


if __name__ == "__main__":
    main()
