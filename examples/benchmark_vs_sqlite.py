"""Benchmark: Whoosh vs SQLite FTS5.

An honest, reproducible micro-benchmark comparing this library against
SQLite's built-in FTS5 full-text extension on the same synthetic corpus.
It measures index build time, index size, and average query latency.

The point is NOT to "win" -- SQLite FTS5 is a heavily optimised C extension
and will usually be faster and smaller. The point is to show, with real
numbers, *where Whoosh sits* and what you get in return: a pure-Python,
zero-dependency, embeddable search engine with pluggable analysis, scoring,
faceting and highlighting -- no C toolchain, no separate service, and full
control from Python.

Run:
    python examples/benchmark_vs_sqlite.py            # default 20k docs
    python examples/benchmark_vs_sqlite.py --docs 50000 --queries 500

Requires only the standard library plus Whoosh itself.
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sqlite3
import tempfile
import time

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import QueryParser

# A small vocabulary so that queries reliably match something.
WORDS = (
    "search engine python library index document token analyzer query parser "
    "ranking relevance scoring highlight facet storage segment posting term "
    "vector field schema writer reader stemming tokenizer filter fast pure "
    "memory disk network cluster shard replica cache latency throughput data "
    "structure algorithm sort merge trie automaton regex fuzzy prefix wildcard"
).split()


def make_corpus(n: int, seed: int = 1234) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    docs = []
    for i in range(n):
        length = rng.randint(20, 60)
        body = " ".join(rng.choice(WORDS) for _ in range(length))
        docs.append((str(i), body))
    return docs


def make_queries(n: int, seed: int = 99) -> list[str]:
    rng = random.Random(seed)
    qs = []
    for _ in range(n):
        if rng.random() < 0.5:
            qs.append(rng.choice(WORDS))
        else:
            qs.append(f"{rng.choice(WORDS)} {rng.choice(WORDS)}")
    return qs


def dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def bench_whoosh(docs, queries, workdir):
    schema = Schema(id=ID(stored=True), body=TEXT(analyzer=StemmingAnalyzer()))
    ix = index.create_in(workdir, schema)

    t0 = time.perf_counter()
    writer = ix.writer(limitmb=128)
    for doc_id, body in docs:
        writer.add_document(id=doc_id, body=body)
    writer.commit()
    build = time.perf_counter() - t0

    size = dir_size(workdir)

    parser = QueryParser("body", schema=ix.schema)
    parsed = [parser.parse(q) for q in queries]

    t0 = time.perf_counter()
    returned = 0
    with ix.searcher() as s:
        for q in parsed:
            results = s.search(q, limit=10)
            # Count rows actually returned (<= limit), matching the SQLite
            # side, so the "returned rows" column is directly comparable.
            returned += sum(1 for _ in results)
    query_total = time.perf_counter() - t0

    ix.close()
    return build, size, query_total, returned


def bench_sqlite(docs, queries, dbpath):
    con = sqlite3.connect(dbpath)
    con.execute("CREATE VIRTUAL TABLE docs USING fts5(id, body)")

    t0 = time.perf_counter()
    con.executemany("INSERT INTO docs(id, body) VALUES (?, ?)", docs)
    con.commit()
    build = time.perf_counter() - t0

    con.close()
    size = os.path.getsize(dbpath)

    con = sqlite3.connect(dbpath)
    cur = con.cursor()
    t0 = time.perf_counter()
    returned = 0
    for q in queries:
        # FTS5 MATCH; join tokens with OR to mimic Whoosh's default OR grouping.
        match = " OR ".join(q.split())
        rows = cur.execute(
            "SELECT id FROM docs WHERE docs MATCH ? LIMIT 10", (match,)
        ).fetchall()
        returned += len(rows)
    query_total = time.perf_counter() - t0
    con.close()
    return build, size, query_total, returned


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", type=int, default=20000)
    ap.add_argument("--queries", type=int, default=300)
    args = ap.parse_args()

    print(f"Building corpus: {args.docs} docs, {args.queries} queries...\n")
    docs = make_corpus(args.docs)
    queries = make_queries(args.queries)

    tmp = tempfile.mkdtemp(prefix="whoosh_bench_")
    try:
        whoosh_dir = os.path.join(tmp, "whoosh_index")
        os.makedirs(whoosh_dir)
        sqlite_path = os.path.join(tmp, "fts5.db")

        wb, wsz, wq, wh = bench_whoosh(docs, queries, whoosh_dir)
        sb, ssz, sq, sh = bench_sqlite(docs, queries, sqlite_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    def row(label, whoosh_val, sqlite_val):
        print(f"  {label:<22} {whoosh_val:>16}   {sqlite_val:>16}")

    print("=" * 60)
    print(f"  {'metric':<22} {'Whoosh':>16}   {'SQLite FTS5':>16}")
    print("=" * 60)
    row("index build (s)", f"{wb:.3f}", f"{sb:.3f}")
    row("index size", human_bytes(wsz), human_bytes(ssz))
    row(f"{args.queries} queries (s)", f"{wq:.3f}", f"{sq:.3f}")
    row("avg query (ms)", f"{wq / args.queries * 1000:.3f}",
        f"{sq / args.queries * 1000:.3f}")
    row("rows returned (top10)", str(wh), str(sh))
    print("=" * 60)
    print(
        "\nNotes:\n"
        "  * SQLite FTS5 is a mature C extension; expect it to be faster and\n"
        "    smaller. Whoosh trades some raw speed for being pure-Python,\n"
        "    dependency-free, and fully programmable from Python.\n"
        "  * Whoosh uses a stemming analyzer here (search/searching/searched\n"
        "    all match); FTS5 uses its default unicode tokenizer. Results are\n"
        "    indicative, not a controlled apples-to-apples relevance test.\n"
        "  * Numbers vary by machine, corpus, and query mix. Reproduce with\n"
        "    your own data before drawing conclusions."
    )


if __name__ == "__main__":
    main()
