# Benchmarks

Two kinds of benchmark live here.

## `regression.py` — catch performance regressions before a release

A small, honest, **self-contained** benchmark that times the core operations
most users care about (index build, incremental single-document add, and a
handful of representative query types) against a *fixed, deterministic*
synthetic corpus. It uses only the standard library plus Whoosh itself, and
the corpus is seeded, so runs are comparable across machines and versions.

Its only job is to answer **"did this change make Whoosh slower?"** — not to
race other engines (for that see [`../examples/benchmark_vs_sqlite.py`](../examples/benchmark_vs_sqlite.py)).

### Typical maintainer workflow

Record a baseline on a clean checkout of the previous release:

```bash
pip install -e .            # or: pip install whoosh3==<previous>
python benchmark/regression.py --json baseline.json
```

Then, on your working tree, compare against it:

```bash
python benchmark/regression.py --compare baseline.json
```

`--compare` prints a per-metric table of baseline vs. current timings and
**exits non-zero if any metric got slower than the allowed tolerance**
(`--tolerance`, default `0.25` = 25%). Timings are noisy on shared CI runners,
so the default tolerance is intentionally generous — tighten it for local runs
on a quiet machine, and always trust a repeated run over a single one.

### Options

| flag | default | meaning |
|------|---------|---------|
| `--docs N` | `5000` | corpus size |
| `--queries N` | `200` | number of queries per query benchmark |
| `--seed N` | `1234` | RNG seed (keep fixed to compare runs) |
| `--json FILE` | — | write this run's results to `FILE` |
| `--compare FILE` | — | run, then compare against a saved baseline |
| `--tolerance F` | `0.25` | allowed fractional slowdown before flagging |

Example run:

```
Whoosh 3.11.7 on Python 3.12.3 (5000 docs, 200 queries, seed 1234)
----------------------------------------------------
  build_index_ms                3812.44 ms
  incremental_add_ms               7.61 ms
  query_single_term_ms           862.90 ms
  query_two_term_ms             1604.12 ms
  query_prefix_ms               1180.55 ms
  query_sorted_ms                701.33 ms
```

## Corpus benchmarks (`reuters.py`, `enron.py`, `marc21.py`, `dictionary.py`)

The original, heavier benchmarks that index real-world corpora using the
`whoosh.support.bench` harness. They are useful for eyeballing absolute
throughput on realistic data but need their corpora and are not part of the
regression guard.
