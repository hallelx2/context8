# Plan 04 — MCP Server Implementation

## Objective

Build the MCP (Model Context Protocol) server that exposes Context8's capabilities as tools that any MCP-compatible coding agent can call. This is the interface layer — agents never talk to the database directly.

## MCP Protocol Overview

MCP is a standard protocol for connecting AI agents to external tools and data sources. It works like this:

```
Agent <──stdin/stdout──> MCP Server <──gRPC──> Actian VectorAI DB
```

The agent sends JSON-RPC messages to the MCP server, which translates them into database operations. The agent doesn't know or care that Actian VectorAI DB is the backend.

## Tools to Expose

### Tool 1: `context8_search`

**Purpose:** Search for past solutions to a problem the agent is facing.

```json
{
  "name": "context8_search",
  "description": "Search Context8 for past solutions to coding problems. Returns semantically similar problems that were previously solved by coding agents, with their solutions. Use this when you encounter an error or problem that might have been solved before. Supports filtering by language, framework, and error type.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The problem description, error message, or question to search for"
      },
      "code_context": {
        "type": "string",
        "description": "Optional code snippet where the error occurs. Improves search accuracy for code-related problems."
      },
      "language": {
        "type": "string",
        "description": "Filter by programming language (e.g., 'python', 'typescript', 'rust')"
      },
      "framework": {
        "type": "string",
        "description": "Filter by framework (e.g., 'react', 'django', 'fastapi')"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of results to return (default: 5, max: 20)",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
```

### Tool 2: `context8_log`

**Purpose:** Log a problem-solution pair after the agent resolves something.

```json
{
  "name": "context8_log",
  "description": "Log a resolved coding problem and its solution to Context8. Call this after you successfully fix an error or solve a non-trivial problem. This builds the collective memory so future agents can find this solution. Only log genuinely useful solutions — not trivial typos or syntax errors.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "problem": {
        "type": "string",
        "description": "The problem description — what went wrong, the error message, symptoms"
      },
      "solution": {
        "type": "string",
        "description": "How you solved it — what you changed and why it works"
      },
      "error_type": {
        "type": "string",
        "description": "The error class (e.g., 'TypeError', 'ImportError', 'BuildError')"
      },
      "code_snippet": {
        "type": "string",
        "description": "The code that was changed (the fix)"
      },
      "code_diff": {
        "type": "string",
        "description": "The diff showing what changed (before/after)"
      },
      "stack_trace": {
        "type": "string",
        "description": "The relevant stack trace, if any"
      },
      "language": {
        "type": "string",
        "description": "Programming language"
      },
      "framework": {
        "type": "string",
        "description": "Framework in use"
      },
      "libraries": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Relevant library versions (e.g., ['react@18.2', 'typescript@5.3'])"
      },
      "tags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Descriptive tags for categorization"
      },
      "confidence": {
        "type": "number",
        "description": "Your confidence that this solution is correct (0.0-1.0)",
        "default": 0.8
      },
      "file_path": {
        "type": "string",
        "description": "File path where the fix was applied"
      }
    },
    "required": ["problem", "solution"]
  }
}
```

### Tool 3: `context8_stats`

**Purpose:** Get stats about the Context8 knowledge base.

```json
{
  "name": "context8_stats",
  "description": "Get statistics about the Context8 knowledge base — total records, breakdown by language/framework, and health status.",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

## Server Implementation

```python
# src/context8/server.py

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .embeddings import EmbeddingService
from .storage import StorageService
from .search import SearchEngine
from .models import ResolutionRecord

logger = logging.getLogger("context8")

# Initialize services
embedding_service = EmbeddingService()
storage_service = StorageService()
search_engine = SearchEngine(storage_service, embedding_service)

# Create MCP server
app = Server("context8")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Register Context8 tools with the MCP protocol."""
    return [
        Tool(
            name="context8_search",
            description=(
                "Search Context8 for past solutions to coding problems. "
                "Returns semantically similar problems that were previously solved "
                "by coding agents. Use when you encounter an error that might have "
                "been solved before."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Problem description or error message to search for",
                    },
                    "code_context": {
                        "type": "string",
                        "description": "Code snippet where the error occurs",
                    },
                    "language": {
                        "type": "string",
                        "description": "Filter by programming language",
                    },
                    "framework": {
                        "type": "string",
                        "description": "Filter by framework",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="context8_log",
            description=(
                "Log a resolved coding problem and its solution to Context8. "
                "Call this after fixing a non-trivial error. Builds collective "
                "memory for future agents."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "problem": {"type": "string", "description": "What went wrong"},
                    "solution": {"type": "string", "description": "How you fixed it"},
                    "error_type": {"type": "string"},
                    "code_snippet": {"type": "string"},
                    "code_diff": {"type": "string"},
                    "stack_trace": {"type": "string"},
                    "language": {"type": "string"},
                    "framework": {"type": "string"},
                    "libraries": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "default": 0.8},
                    "file_path": {"type": "string"},
                },
                "required": ["problem", "solution"],
            },
        ),
        Tool(
            name="context8_stats",
            description="Get Context8 knowledge base statistics.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls from agents."""
    
    try:
        if name == "context8_search":
            return await _handle_search(arguments)
        elif name == "context8_log":
            return await _handle_log(arguments)
        elif name == "context8_stats":
            return await _handle_stats(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _handle_search(args: dict) -> list[TextContent]:
    """Execute hybrid search and format results."""
    results = search_engine.search(
        query=args["query"],
        code_context=args.get("code_context", ""),
        language=args.get("language"),
        framework=args.get("framework"),
        limit=min(args.get("limit", 5), 20),
    )

    if not results:
        return [TextContent(
            type="text",
            text="No matching solutions found in Context8. This might be a new problem — consider logging the solution after you resolve it with context8_log.",
        )]

    # Format results for the agent
    output_lines = [f"Found {len(results)} relevant solution(s) in Context8:\n"]
    
    for i, result in enumerate(results, 1):
        r = result.record
        output_lines.append(f"--- Solution {i} (score: {result.score:.3f}) ---")
        output_lines.append(f"Problem: {r.problem_text}")
        output_lines.append(f"Solution: {r.solution_text}")
        if r.code_diff:
            output_lines.append(f"Code change:\n{r.code_diff}")
        if r.language or r.framework:
            output_lines.append(f"Context: {r.language} / {r.framework}")
        if r.tags:
            output_lines.append(f"Tags: {', '.join(r.tags)}")
        output_lines.append(f"Confidence: {r.confidence:.0%}")
        output_lines.append("")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def _handle_log(args: dict) -> list[TextContent]:
    """Log a new resolution record."""
    import platform

    record = ResolutionRecord(
        problem_text=args["problem"],
        solution_text=args["solution"],
        error_type=args.get("error_type", ""),
        code_snippet=args.get("code_snippet", ""),
        code_diff=args.get("code_diff", ""),
        stack_trace=args.get("stack_trace", ""),
        language=args.get("language", ""),
        framework=args.get("framework", ""),
        libraries=args.get("libraries", []),
        tags=args.get("tags", []),
        confidence=args.get("confidence", 0.8),
        file_path=args.get("file_path", ""),
        os=platform.system().lower(),
        agent="mcp-agent",  # Could be passed by the agent
    )

    # Check for duplicates first
    existing = search_engine.find_duplicate(record.problem_text)
    if existing:
        return [TextContent(
            type="text",
            text=f"Similar solution already exists (score: {existing.score:.3f}). Record ID: {existing.record.id}. Not creating duplicate.",
        )]

    # Generate embeddings and store
    vectors = embedding_service.embed_record(
        problem_text=record.problem_text,
        solution_text=record.solution_text,
        code_snippet=record.code_snippet,
    )
    record_id = storage_service.store_record(record, vectors)

    return [TextContent(
        type="text",
        text=f"Solution logged to Context8. Record ID: {record_id}. This will help future agents encountering similar problems.",
    )]


async def _handle_stats(args: dict) -> list[TextContent]:
    """Return knowledge base statistics."""
    total = storage_service.count()
    
    output = [
        "Context8 Knowledge Base Stats:",
        f"  Total records: {total}",
        f"  Database: Actian VectorAI DB",
        f"  Collection: context8_store",
        f"  Vector spaces: problem (384d), solution (384d), code_context (768d)",
        f"  Sparse vectors: keywords (BM25)",
        f"  Status: HEALTHY",
    ]
    
    return [TextContent(type="text", text="\n".join(output))]


async def main():
    """Run the Context8 MCP server."""
    # Initialize database
    storage_service.initialize()
    logger.info("Context8 MCP server starting...")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

## Agent Configuration

### Claude Code (`.claude/settings.json`)

```json
{
  "mcpServers": {
    "context8": {
      "command": "python",
      "args": ["-m", "context8.server"],
      "env": {
        "CONTEXT8_DB_HOST": "localhost",
        "CONTEXT8_DB_PORT": "50051"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "context8": {
      "command": "python",
      "args": ["-m", "context8.server"]
    }
  }
}
```

### Any MCP-compatible Agent

The MCP protocol is standardized — any agent that speaks MCP can use Context8 by configuring the server command.

## CLI Entry Point

For convenience, Context8 can also be started via CLI:

```python
# src/context8/__main__.py

"""Context8 — Collective Problem-Solving Memory for Coding Agents.

Usage:
    python -m context8                   # Start MCP server (stdio)
    python -m context8 --init            # Initialize database only
    python -m context8 --stats           # Show knowledge base stats
    python -m context8 --seed            # Seed with starter data
"""

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(description="Context8 MCP Server")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    parser.add_argument("--seed", action="store_true", help="Seed with starter data")
    parser.add_argument("--host", default="localhost", help="DB host")
    parser.add_argument("--port", type=int, default=50051, help="DB port")
    
    args = parser.parse_args()

    if args.init:
        from .storage import StorageService
        svc = StorageService(host=args.host, port=args.port)
        svc.initialize()
        print("Context8 database initialized.")
        return

    if args.stats:
        from .storage import StorageService
        svc = StorageService(host=args.host, port=args.port)
        print(f"Total records: {svc.count()}")
        return

    if args.seed:
        from .seed import seed_database
        seed_database(host=args.host, port=args.port)
        print("Database seeded with starter data.")
        return

    # Default: run MCP server
    from .server import main as server_main
    asyncio.run(server_main())


if __name__ == "__main__":
    main()
```

## Testing Criteria

- [ ] MCP server starts without errors via `python -m context8`
- [ ] `list_tools()` returns all 3 tools with correct schemas
- [ ] `context8_search` returns results for known queries
- [ ] `context8_search` returns "no results" message for unknown queries
- [ ] `context8_search` respects language/framework filters
- [ ] `context8_log` stores a record and returns a valid ID
- [ ] `context8_log` detects duplicates and refuses to create them
- [ ] `context8_stats` returns correct count and status
- [ ] Server handles malformed input gracefully (no crashes)
- [ ] Server reconnects to DB after transient connection failure

## Files Created

```
src/context8/
├── __init__.py
├── __main__.py     # CLI entry point
├── server.py       # MCP server with tool handlers
├── models.py       # Data models (from Plan 03)
├── storage.py      # DB operations (from Plan 03)
├── embeddings.py   # Embedding pipeline (from Plan 02)
├── search.py       # Search engine (Plan 05)
└── seed.py         # Starter data seeder (Plan 07)
```

## Estimated Time: 1.5 hours

## Dependencies: Plan 01, Plan 02, Plan 03

## Next: Plan 05 (Search Engine — hybrid/filtered/named vector search)
