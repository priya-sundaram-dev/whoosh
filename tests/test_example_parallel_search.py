"""Smoke tests for examples/parallel_search.py.

The parallel-search recipe is the query-side companion to the parallel-indexing
pattern the concurrency guide points free-threaded (no-GIL) users at: one shared
read-only index, one searcher per worker thread, a batch of queries fanned out
across the pool. The whole promise is that fanning the workload across threads
returns *exactly* the same results as a serial run -- the search-server shape,
correct by construction. These tests pin that equivalence (and the per-thread
searcher discipline) so a refactor can't silently break it; timing is not
asserted, since a speedup only shows up on an actual free-threaded build.
"""

import importlib.util
import pathlib
import tempfile

import pytest

_EXAMPLE = (
    pathlib.Path(__file__).resolve().parent.parent / "examples" / "parallel_search.py"
)


@pytest.fixture(scope="module")
def ex():
    spec = importlib.util.spec_from_file_location("parallel_search", _EXAMPLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(ex):
    """A shared index + open handle reused across the query tests."""
    docs = ex.make_corpus(600)
    with tempfile.TemporaryDirectory() as where:
        index_dir = ex.build_index(docs, where)
        from whoosh import index

        ix = index.open_dir(index_dir)
        try:
            yield ex, ix
        finally:
            ix.close()


def test_parallel_matches_serial(built):
    ex, ix = built
    queries = ex.make_queries(400)
    _, serial = ex.search_serial(ix, queries)
    _, parallel = ex.search_parallel(ix, queries, workers=4)
    ex.verify_equivalent(serial, parallel)


def test_single_worker_is_still_correct(built):
    # Degenerate fan-out (1 worker) must behave like the serial path.
    ex, ix = built
    queries = ex.make_queries(120)
    _, serial = ex.search_serial(ix, queries)
    _, parallel = ex.search_parallel(ix, queries, workers=1)
    ex.verify_equivalent(serial, parallel)


def test_more_workers_than_queries(built):
    # Uneven fan-out where some workers get no work must not drop or reorder
    # results -- pool.map preserves input order regardless of worker count.
    ex, ix = built
    queries = ex.make_queries(3)
    _, serial = ex.search_serial(ix, queries)
    _, parallel = ex.search_parallel(ix, queries, workers=8)
    ex.verify_equivalent(serial, parallel)


def test_results_are_deterministic_and_ordered(built):
    # make_queries is seeded, so the workload -- and therefore the result
    # list -- is reproducible run to run.
    ex, ix = built
    q1 = ex.make_queries(50)
    q2 = ex.make_queries(50)
    assert q1 == q2
    _, r1 = ex.search_serial(ix, q1)
    _, r2 = ex.search_serial(ix, q2)
    assert r1 == r2


def test_verify_equivalent_catches_a_mismatch(ex):
    # The correctness check must actually fail when results differ, otherwise
    # the other tests prove nothing.
    with pytest.raises(AssertionError):
        ex.verify_equivalent([("a",)], [("b",)])
    with pytest.raises(AssertionError):
        ex.verify_equivalent([("a",)], [("a",), ("b",)])


def test_gil_status_is_descriptive(ex):
    status = ex.gil_status()
    assert isinstance(status, str) and status
