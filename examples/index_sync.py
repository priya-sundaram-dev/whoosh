"""Keeping a Whoosh index in sync: updates, deletes, and folder sync.

Run me:  python examples/index_sync.py

Demonstrates the three core patterns for keeping search indexes matching source data:
  1. Upsert: writer.update_document(...) on a unique=True field replaces existing docs
     rather than duplicating them.
  2. Delete: writer.delete_by_term(...) removes documents cleanly by primary key.
  3. Folder sync: reconcile an index against a directory of files using stored
     modification times (detecting additions, modifications, and deletions).

Everything runs in memory (RamStorage) and a throwaway temp directory so no files
are left behind.
"""

import os
import tempfile
import time

from whoosh.fields import ID, STORED, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser


def sync_folder(docs_dir, ix):
    """Reconcile the index against docs_dir using stored modification times.

    Compares on-disk files and their mtimes against what is stored in the index,
    issuing adds, updates, or deletes in a single atomic commit.
    """
    indexed = {}
    with ix.searcher() as searcher:
        for fields in searcher.all_stored_fields():
            indexed[fields["path"]] = fields["time"]

    on_disk = {
        name: os.path.getmtime(os.path.join(docs_dir, name))
        for name in os.listdir(docs_dir)
        if os.path.isfile(os.path.join(docs_dir, name))
    }

    deleted = set(indexed) - set(on_disk)
    added = set(on_disk) - set(indexed)
    modified = {
        path
        for path, mtime in on_disk.items()
        if path in indexed and mtime != indexed[path]
    }

    writer = ix.writer()
    for path in deleted:
        writer.delete_by_term("path", path)
    for path in added:
        filepath = os.path.join(docs_dir, path)
        with open(filepath, encoding="utf-8") as f:
            writer.add_document(path=path, time=on_disk[path], content=f.read())
    for path in modified:
        filepath = os.path.join(docs_dir, path)
        with open(filepath, encoding="utf-8") as f:
            writer.update_document(path=path, time=on_disk[path], content=f.read())
    writer.commit()

    return {"added": len(added), "updated": len(modified), "deleted": len(deleted)}


def demo_upsert_and_delete():
    print("=== 1. Upsert with update_document() ===")
    schema = Schema(
        path=ID(unique=True, stored=True),
        content=TEXT(stored=True),
    )
    ix = RamStorage().create_index(schema)

    # Initial indexing pass
    writer = ix.writer()
    writer.add_document(path="doc1.txt", content="the quick brown fox")
    writer.add_document(path="doc2.txt", content="lazy dog sleeps all day")
    writer.commit()

    with ix.searcher() as searcher:
        print(f"Initial index has {searcher.doc_count()} document(s):")
        for hit in searcher.all_stored_fields():
            print(f"  - {hit['path']}: {hit['content']}")

    # Upsert: doc1.txt is updated (replaced in place), doc3.txt is newly added
    writer = ix.writer()
    writer.update_document(path="doc1.txt", content="the quick brown fox jumps")
    writer.update_document(path="doc3.txt", content="pure Python full text search")
    writer.commit()

    with ix.searcher() as searcher:
        print(
            f"\nAfter upsert (update doc1.txt, add doc3.txt), index has {searcher.doc_count()} document(s):"
        )
        for hit in searcher.all_stored_fields():
            print(f"  - {hit['path']}: {hit['content']}")

        qp = QueryParser("content", ix.schema)
        hits = searcher.search(qp.parse("jumps"))
        print(
            f"Query 'jumps' matches: {[h['path'] for h in hits]} (doc1.txt replaced, no duplicates)"
        )

    print("\n=== 2. Delete with delete_by_term() ===")
    writer = ix.writer()
    deleted_count = writer.delete_by_term("path", "doc2.txt")
    writer.commit()
    print(f"Deleted doc2.txt (removed {deleted_count} record)")

    with ix.searcher() as searcher:
        print(f"Remaining document(s) in index ({searcher.doc_count()} total):")
        for hit in searcher.all_stored_fields():
            print(f"  - {hit['path']}")

        qp = QueryParser("content", ix.schema)
        hits = searcher.search(qp.parse("lazy OR sleeps"))
        print(f"Query 'lazy OR sleeps' matches: {len(hits)} hits (doc2.txt is gone)")

    ix.close()


def demo_folder_sync():
    print("\n=== 3. Folder Synchronization (Add / Modify / Delete Detection) ===")
    sync_schema = Schema(
        path=ID(unique=True, stored=True),
        time=STORED,
        content=TEXT(stored=True),
    )
    ix = RamStorage().create_index(sync_schema)

    with tempfile.TemporaryDirectory(prefix="whoosh-sync-demo-") as docs_dir:
        # Pass 1: Initial files
        file1 = os.path.join(docs_dir, "notes.txt")
        file2 = os.path.join(docs_dir, "todo.txt")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("Meeting notes: review search engine architecture.")
        with open(file2, "w", encoding="utf-8") as f:
            f.write("Todo item: write comprehensive integration tests.")

        stats1 = sync_folder(docs_dir, ix)
        print(
            f"Pass 1 (Initial sync) -> Added: {stats1['added']}, Updated: {stats1['updated']}, Deleted: {stats1['deleted']}"
        )
        with ix.searcher() as searcher:
            print(
                f"  Indexed docs ({searcher.doc_count()}): {sorted(d['path'] for d in searcher.all_stored_fields())}"
            )

        # Pass 2: Modifications, additions, and deletions
        time.sleep(0.02)  # Ensure filesystem mtime resolution advances
        with open(file1, "w", encoding="utf-8") as f:
            f.write(
                "Meeting notes: review search engine architecture and BM25 ranking."
            )

        file3 = os.path.join(docs_dir, "faq.txt")
        with open(file3, "w", encoding="utf-8") as f:
            f.write("FAQ: How do I keep my index in sync with files on disk?")

        os.remove(file2)  # delete todo.txt

        stats2 = sync_folder(docs_dir, ix)
        print(
            f"\nPass 2 (Incremental sync) -> Added: {stats2['added']}, Updated: {stats2['updated']}, Deleted: {stats2['deleted']}"
        )
        with ix.searcher() as searcher:
            print(
                f"  Indexed docs ({searcher.doc_count()}): {sorted(d['path'] for d in searcher.all_stored_fields())}"
            )
            qp = QueryParser("content", ix.schema)
            res = searcher.search(qp.parse("BM25"))
            print(f"  Search for 'BM25' in updated file: {[h['path'] for h in res]}")

        # Pass 3: Idempotent no-op pass (no files changed)
        stats3 = sync_folder(docs_dir, ix)
        print(
            f"\nPass 3 (Idempotent check) -> Added: {stats3['added']}, Updated: {stats3['updated']}, Deleted: {stats3['deleted']} (zero work needed)"
        )

    ix.close()


def main():
    demo_upsert_and_delete()
    demo_folder_sync()
    print("\nAll sync demonstrations completed cleanly.")


if __name__ == "__main__":
    main()
