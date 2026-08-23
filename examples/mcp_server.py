"""Expose a Whoosh full-text index to LLM agents as an MCP server.

This example is a thin wrapper around :mod:`whoosh.mcp`, which ships as part of
the ``whoosh3`` package. The Model Context Protocol (MCP) lets AI agents
(Claude Desktop, IDE assistants, custom agent loops) call tools over a standard
protocol. Because Whoosh is pure Python and embeds a real BM25F index as a plain
directory of files, it makes an excellent *local, no-server, no-native-deps*
search backend for an agent's "search" and "fetch" tools.

The packaged version installs a ``whoosh-mcp`` console script, so the usual way
to run it is simply::

    pip install "whoosh3[mcp]"
    whoosh-mcp ~/notes            # stdio transport, ready for an agent

This file keeps a runnable copy you can read and adapt. It builds a tiny index
and serves two tools that follow the common connector convention::

    search(query, limit) -> list of {id, title, score, snippet}
    fetch(id)            -> full document text for a given id

Run it directly::

    pip install whoosh3 mcp
    python examples/mcp_server.py            # built-in sample documents

Serve your *own* files instead by pointing it at a directory of ``.md`` /
``.txt`` / ``.rst`` documents::

    WHOOSH_MCP_CORPUS=~/notes python examples/mcp_server.py

Point an MCP client at it (e.g. in Claude Desktop's config)::

    {
      "mcpServers": {
        "whoosh": { "command": "whoosh-mcp", "args": ["/path/to/your/docs"] }
      }
    }

The search core (SearchCore) has no MCP dependency, so you can import and
unit-test it directly, or reuse it behind any agent framework (LangChain /
LlamaIndex tools, OpenAI function calling, or a plain function).
"""

from __future__ import annotations

# The implementation now lives in the installable package; re-export it here so
# this example stays a single source of truth and never drifts.
from whoosh.mcp import (  # noqa: F401
    DEFAULT_EXTS,
    SAMPLE_DOCS,
    SearchCore,
    build_mcp_server,
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
