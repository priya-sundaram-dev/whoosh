"""
Resource management: closing indexes, readers, and searchers cleanly.

Whoosh keeps the index's on-disk files open while a reader or searcher is
alive so it can serve queries quickly. If you leave those objects to be
cleaned up by the garbage collector, the underlying files stay open until
the object is collected. On POSIX that is usually harmless, but on Windows
an open file handle prevents the file from being deleted or replaced, which
shows up as ``PermissionError: [WinError 32]`` when you try to remove or
rebuild an index.

The fix is simple and deterministic: close what you open. Every reader and
searcher is a context manager, so a ``with`` block is the idiomatic way to
guarantee the handles are released as soon as you are done -- no
``gc.collect()`` workaround required.

Run this file:

    python examples/resource_management.py
"""

import os
import shutil
import tempfile

from whoosh import fields, index
from whoosh.qparser import QueryParser


def build_index(dirname):
    schema = fields.Schema(
        title=fields.TEXT(stored=True),
        body=fields.TEXT,
    )
    ix = index.create_in(dirname, schema)
    writer = ix.writer()
    for i in range(100):
        writer.add_document(
            title=f"Document {i}",
            body="pure python full text search library " * 5,
        )
    # commit() finalizes the segment and releases the writer's files.
    writer.commit()
    return ix


def search_the_right_way(ix):
    """Use a ``with`` block: the searcher closes automatically on exit,
    even if an exception is raised inside the block."""
    qp = QueryParser("body", ix.schema)
    q = qp.parse("pure AND search")
    with ix.searcher() as searcher:
        results = searcher.search(q, limit=5)
        hits = [hit["title"] for hit in results]
    # <- searcher is now closed; its index files are released here.
    return hits


def read_the_right_way(ix):
    """Readers are context managers too."""
    with ix.reader() as reader:
        return reader.doc_count()


def main():
    tmp = tempfile.mkdtemp(prefix="whoosh-resmgmt-")
    try:
        ix = build_index(tmp)

        hits = search_the_right_way(ix)
        print(f"Searcher (with-block) found {len(hits)} hits, e.g. {hits[:2]}")

        count = read_the_right_way(ix)
        print(f"Reader (with-block) reports {count} documents")

        # When you are completely done with the index, close it. This releases
        # any cached readers the index is holding on your behalf.
        ix.close()
        print("index.close() called -- all handles released deterministically.")

        # Because everything was closed explicitly, the index directory can be
        # removed immediately, even on Windows. No gc.collect() needed.
        shutil.rmtree(tmp)
        print(f"Removed {tmp!r} cleanly right after closing.")
        tmp = None
    finally:
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
