"""Smoke tests: the copy-paste ``examples/`` scripts still run end to end.

Several ``examples/*.py`` files are the first thing a new user runs -- most
importantly ``quickstart.py`` and ``tutorial.py``, the exact snippets the docs
tell people to try. They print output rather than exposing tidy functions, so
the deeper per-example tests (``test_example_acronyms.py`` etc.) don't cover
them. Nothing else guarantees they keep working, so a routine API refactor
could silently break the project's own front-door examples.

This module runs each dependency-free, no-argument example as a subprocess in a
throwaway working directory and asserts it exits cleanly. It is deliberately a
shallow "does it still run?" guard; examples with richer, assertable behaviour
get their own dedicated test module.

Examples that need optional third-party packages (Flask/FastAPI/Django,
LangChain, LlamaIndex, MCP) or command-line arguments (``static_site_search``,
``search_cli``, ``django_app``), or that are intentionally slow benchmarks
(``benchmark_vs_sqlite``), are excluded on purpose.
"""

import os
import pathlib
import subprocess
import sys

import pytest

import whoosh

_EXAMPLES_DIR = pathlib.Path(__file__).resolve().parent.parent / "examples"

# Dependency-free, no-argument scripts that finish quickly. Keeping this an
# explicit allowlist (rather than globbing the directory) means adding a new
# example is a deliberate, reviewed choice and never makes CI flaky by
# accident.
_RUNNABLE = [
    "quickstart.py",
    "tutorial.py",
    "autocomplete.py",
    "did_you_mean.py",
    "highlighting.py",
    "faceted_search.py",
    "scoring_and_sorting.py",
    "custom_analyzers.py",
    "resource_management.py",
]


def _env_with_whoosh_importable():
    """Return an env where ``import whoosh`` works in the child process.

    Works whether whoosh is pip-installed or being tested straight from
    ``src/`` (the package's parent directory is prepended to PYTHONPATH).
    """
    env = dict(os.environ)
    pkg_parent = str(pathlib.Path(whoosh.__file__).resolve().parent.parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pkg_parent + (os.pathsep + existing if existing else "")
    return env


@pytest.mark.parametrize("script", _RUNNABLE)
def test_example_script_runs(script, tmp_path):
    path = _EXAMPLES_DIR / script
    assert path.is_file(), f"missing example: {script}"
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(tmp_path),  # examples that build an on-disk index stay contained
        env=_env_with_whoosh_importable(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"examples/{script} exited {result.returncode}:\n"
        + result.stdout.decode("utf-8", "replace")[-2000:]
    )
