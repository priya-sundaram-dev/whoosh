"""Type-checker smoke fixture for Whoosh3's public API (gh#3).

This module is *not* run as a normal test. Instead, CI type-checks it with
``mypy`` (see the ``types`` job in ``.github/workflows/ci.yml``). It exercises
the annotated public entry points the way a downstream user would, so that if a
future change breaks or removes an annotation, the type checker fails loudly
here rather than silently degrading the editor/mypy experience for users.

Keep this snippet realistic and minimal: index creation, a schema built from
the field-type constructors, adding a document, and running a query through the
searching layer.
"""

from __future__ import annotations

import tempfile

from whoosh import index
from whoosh.fields import DATETIME, ID, NUMERIC, TEXT, Schema
from whoosh.qparser import QueryParser
from whoosh.searching import Hit, Results


def build_schema() -> Schema:
    # Field-type constructors are annotated, so kwargs type-check.
    return Schema(
        id=ID(stored=True, unique=True),
        title=TEXT(stored=True),
        views=NUMERIC(stored=True),
        created=DATETIME(stored=True),
    )


def run() -> list[str]:
    schema = build_schema()
    tmpdir = tempfile.mkdtemp()

    # index.create_in returns an Index; open/exists helpers are annotated too.
    ix = index.create_in(tmpdir, schema)
    assert index.exists_in(tmpdir)

    writer = ix.writer()
    writer.add_document(id="1", title="First document about search")
    writer.commit()

    titles: list[str] = []
    with ix.searcher() as searcher:
        parser = QueryParser("title", schema=ix.schema)
        query = parser.parse("search")
        results: Results = searcher.search(query, limit=10)
        for hit in results:
            hit_obj: Hit = hit
            titles.append(str(hit_obj["title"]))
    return titles


if __name__ == "__main__":
    print(run())
