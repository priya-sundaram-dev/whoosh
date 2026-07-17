"""Performance-regression benchmark for Whoosh.

A small, honest, reproducible benchmark that times the core operations most
users care about -- building an index, adding a document incrementally, and
running a handful of representative query types -- against a *fixed,
deterministic* synthetic corpus. It is meant to be run on two versions of the
library (for example, the last release and your working tree) so a maintainer
can catch performance regressions *before* cutting a release.

This is deliberately not a "who's fastest" benchmark against other engines
(see ``examples/benchmark_vs_sqlite.py`` for that). Its only job is to answer
"did *this* change make *Whoosh* slower?" with real numbers.

Usage
-----
Record a baseline (e.g. on a clean checkout of the previous release)::

    python benchmark/regression.py --json baseline.json

Then, on your working tree, compare against it::

    python benchmark/regression.py --compare baseline.json

``--compare`` prints a table of each metric's baseline vs. current timing and
exits non-zero if any metric got slower than the allowed tolerance
(``--tolerance``, default 25%). Timings are noisy on shared CI runners, so the
default tolerance is intentionally generous; tighten it for local runs on a
quiet machine.

Everything here uses only the standard library plus Whoosh itself, and the
corpus is seeded, so runs are comparable across machines and versions.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from typing import Callable

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import DATETIME, ID, NUMERIC, TEXT, Schema
from whoosh.qparser import QueryParser

# A small, fixed vocabulary so queries reliably match something and the corpus
# is identical for a given seed across versions and machines.
WORDS = (
    "search engine python library index document token analyzer query parser "
    "ranking relevance scoring highlight facet storage segment posting term "
    "vector field schema writer reader stemming tokenizer filter fast pure "
    "memory disk network cluster shard replica cache latency throughput data "
    "structure algorithm sort merge trie automaton regex fuzzy prefix wildcard"
).split()


def make_corpus(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    docs = []
    for i in range(n):
        length = rng.randint(20, 60)
        body = " ".join(rng.choice(WORDS) for _ in range(length))
        title = " ".join(rng.choice(WORDS) for _ in range(rng.randint(2, 5)))
        docs.append(
            {
                "id": str(i),
                "title": title,
                "body": body,
                "count": rng.randint(0, 10_000),
                "category": "cat%d" % (i % 8),
            }
        )
    return docs


def make_schema() -> Schema:
    return Schema(
        id=ID(stored=True, unique=True),
        title=TEXT(stored=True, analyzer=StemmingAnalyzer()),
        body=TEXT(analyzer=StemmingAnalyzer()),
        count=NUMERIC(stored=True, sortable=True),
        category=ID(stored=True),
    )


def _time(fn: Callable[[], None], repeat: int = 1) -> float:
    """Return the best (minimum) wall-clock time over ``repeat`` runs, in ms."""
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best * 1000.0


def build_index(dirname: str, schema: Schema, docs: list[dict], procs: int = 1):
    ix = index.create_in(dirname, schema)
    writer = ix.writer(procs=procs) if procs > 1 else ix.writer()
    for doc in docs:
        writer.add_document(**doc)
    writer.commit()
    return ix


def run_benchmark(docs_n: int, queries_n: int, seed: int) -> dict:
    docs = make_corpus(docs_n, seed)
    schema = make_schema()
    rng = random.Random(seed + 1)
    query_terms = [rng.choice(WORDS) for _ in range(queries_n)]
    two_term = ["%s %s" % (rng.choice(WORDS), rng.choice(WORDS)) for _ in range(queries_n)]

    results: dict[str, float] = {}
    tmp = tempfile.mkdtemp(prefix="whoosh-bench-")
    try:
        # 1. Index build (single writer) -- the big one.
        d1 = os.path.join(tmp, "build")
        os.mkdir(d1)
        ix = None

        def _build():
            nonlocal ix
            if ix is not None:
                ix.close()
            shutil.rmtree(d1, ignore_errors=True)
            os.mkdir(d1)
            ix = build_index(d1, schema, docs)

        results["build_index_ms"] = _time(_build, repeat=2)

        # 2. Incremental single-document add + commit.
        def _add_one():
            w = ix.writer()
            w.add_document(
                id="extra", title="python search", body="fast pure python search engine"
            )
            w.commit()
            # remove it again so repeated runs stay comparable
            w2 = ix.writer()
            w2.delete_by_term("id", "extra")
            w2.commit()

        results["incremental_add_ms"] = _time(_add_one, repeat=3)

        # 3. Query latency -- single term, parsed and scored (BM25F default).
        with ix.searcher() as s:
            qp = QueryParser("body", schema=ix.schema)

            def _single_term():
                for t in query_terms:
                    q = qp.parse(t)
                    s.search(q, limit=10)

            results["query_single_term_ms"] = _time(_single_term, repeat=3)

            # 4. Two-term (implicit AND) queries.
            def _two_term():
                for t in two_term:
                    q = qp.parse(t)
                    s.search(q, limit=10)

            results["query_two_term_ms"] = _time(_two_term, repeat=3)

            # 5. Prefix query -- exercises the term automaton path.
            def _prefix():
                for t in query_terms:
                    q = qp.parse(t[:2] + "*")
                    s.search(q, limit=10)

            results["query_prefix_ms"] = _time(_prefix, repeat=3)

            # 6. Sorted search (by numeric field) -- exercises sortable columns.
            from whoosh import sorting

            facet = sorting.FieldFacet("count", reverse=True)

            def _sorted():
                for t in query_terms:
                    q = qp.parse(t)
                    s.search(q, limit=10, sortedby=facet)

            results["query_sorted_ms"] = _time(_sorted, repeat=3)

        ix.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return results


def collect(docs_n: int, queries_n: int, seed: int) -> dict:
    import whoosh

    try:
        whoosh_version = whoosh.versionstring()
    except Exception:  # pragma: no cover - defensive
        whoosh_version = ".".join(str(p) for p in whoosh.__version__)

    metrics = run_benchmark(docs_n, queries_n, seed)
    return {
        "whoosh_version": whoosh_version,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "params": {"docs": docs_n, "queries": queries_n, "seed": seed},
        "metrics": metrics,
    }


def print_report(report: dict) -> None:
    print(
        "Whoosh %s on Python %s (%d docs, %d queries, seed %d)"
        % (
            report["whoosh_version"],
            report["python"],
            report["params"]["docs"],
            report["params"]["queries"],
            report["params"]["seed"],
        )
    )
    print("-" * 52)
    for name, value in report["metrics"].items():
        print("  %-26s %10.2f ms" % (name, value))


def compare(baseline: dict, current: dict, tolerance: float) -> int:
    """Print a comparison table; return non-zero if anything regressed."""
    print(
        "Comparing current Whoosh %s vs baseline %s  (tolerance %.0f%%)"
        % (current["whoosh_version"], baseline["whoosh_version"], tolerance * 100)
    )
    print("-" * 72)
    print("  %-26s %12s %12s %10s" % ("metric", "baseline", "current", "delta"))
    print("-" * 72)
    regressed = []
    b_metrics = baseline["metrics"]
    for name, cur in current["metrics"].items():
        base = b_metrics.get(name)
        if base is None:
            print("  %-26s %12s %12.2f %10s" % (name, "(new)", cur, "--"))
            continue
        delta = (cur - base) / base if base else 0.0
        flag = ""
        if delta > tolerance:
            flag = "  <-- REGRESSION"
            regressed.append((name, delta))
        print(
            "  %-26s %12.2f %12.2f %+9.1f%%%s"
            % (name, base, cur, delta * 100, flag)
        )
    print("-" * 72)
    if regressed:
        print("\nFAIL: %d metric(s) regressed beyond %.0f%%:" % (len(regressed), tolerance * 100))
        for name, delta in regressed:
            print("  - %s (+%.1f%%)" % (name, delta * 100))
        return 1
    print("\nOK: no metric regressed beyond %.0f%%." % (tolerance * 100))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docs", type=int, default=5000, help="corpus size (default 5000)")
    ap.add_argument("--queries", type=int, default=200, help="queries per query benchmark")
    ap.add_argument("--seed", type=int, default=1234, help="RNG seed (keep fixed to compare)")
    ap.add_argument("--json", metavar="FILE", help="write the run's results to FILE as JSON")
    ap.add_argument(
        "--compare",
        metavar="BASELINE.json",
        help="run, then compare against a previously saved baseline; exit non-zero on regression",
    )
    ap.add_argument(
        "--tolerance",
        type=float,
        default=0.25,
        help="allowed fractional slowdown before flagging a regression (default 0.25 = 25%%)",
    )
    args = ap.parse_args(argv)

    report = collect(args.docs, args.queries, args.seed)
    print_report(report)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=2)
        print("\nWrote %s" % args.json)

    if args.compare:
        with open(args.compare) as fh:
            baseline = json.load(fh)
        print()
        return compare(baseline, report, args.tolerance)

    return 0


if __name__ == "__main__":
    sys.exit(main())
