#!/usr/bin/env python3
"""
Cookbook recipe: Add search to a static site

This script indexes a directory of Markdown/RST files and provides a search interface.
It uses only the standard library and Whoosh.

Usage:
  python static_site_search.py index <directory>
  python static_site_search.py search <query>
"""

import os
import re
import sys
from urllib.request import pathname2url

from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.qparser import MultifieldParser
from whoosh.highlight import Formatter


def strip_markup(text):
    """A naive regex-based markup stripper for Markdown/RST."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove Markdown headers/links/images
    text = re.sub(r'#+\s', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove asterisks and underscores used for bold/italic
    text = re.sub(r'[*_]{1,2}', '', text)
    return text


def get_title(text, filename):
    """Extract a simple title from the first heading or fallback to filename."""
    match = re.search(r'^#+\s+(.+)$', text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    match_rst = re.search(r'^([^\n]+)\n[=-]+$', text, re.MULTILINE)
    if match_rst:
        return match_rst.group(1).strip()
    return os.path.basename(filename)


def build_index(directory, indexdir="site_index"):
    """Walks the directory, indexing .md and .rst files."""
    if not os.path.exists(indexdir):
        os.mkdir(indexdir)

    # Schema: title is boosted over body
    schema = Schema(
        path=ID(stored=True, unique=True),
        url=STORED,
        title=TEXT(stored=True, field_boost=2.0),
        body=TEXT(stored=True)
    )

    ix = create_in(indexdir, schema)
    
    with ix.writer() as writer:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.md') or file.endswith('.rst') or file.endswith('.txt'):
                    filepath = os.path.join(root, file)
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    title = get_title(content, file)
                    clean_body = strip_markup(content)
                    
                    # Create a simple relative URL
                    rel_path = os.path.relpath(filepath, directory)
                    url = pathname2url(rel_path)
                    
                    writer.update_document(
                        path=filepath,
                        url=url,
                        title=title,
                        body=clean_body
                    )
    print(f"Indexed {ix.doc_count()} documents in '{indexdir}'.")


def search_index(query_string, indexdir="site_index"):
    """Searches the index and prints highlighted snippets."""
    if not os.path.exists(indexdir):
        print(f"Index directory '{indexdir}' not found. Run 'index' first.")
        return

    ix = open_dir(indexdir)
    
    # Search both title and body
    parser = MultifieldParser(["title", "body"], ix.schema)
    query = parser.parse(query_string)

    with ix.searcher() as searcher:
        results = searcher.search(query, limit=10)
        print(f"Found {len(results)} results for '{query_string}':\n")
        
        # Configure highlighting to output console-friendly text instead of HTML
        results.formatter = ConsoleFormatter()
        
        for hit in results:
            print(f"Title: {hit['title']}")
            print(f"URL:   {hit['url']}")
            
            # Print a highlighted snippet from the body
            snippet = hit.highlights("body")
            if snippet:
                print(f"Snippet: {snippet}")
            print("-" * 40)


class ConsoleFormatter(Formatter):
    """A simple formatter that uses uppercase instead of HTML for highlights."""
    def format_token(self, text, token, chardata):
        # Simply uppercase the matched word
        return text[token.startchar:token.endchar].upper()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
        
    command = sys.argv[1]
    arg = sys.argv[2]
    
    if command == "index":
        build_index(arg)
    elif command == "search":
        search_index(arg)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
