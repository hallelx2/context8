"""Context8 MCP Server — exposes tools to coding agents.

Started automatically by agents via MCP config, or manually with:
    context8 serve
    python -m context8.server
"""

from __future__ import annotations

import logging
import platform
import threading
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import COLLECTION_NAME, DB_URL
from .embeddings import EmbeddingService
from .models import ResolutionRecord
from .search import SearchEngine
from .storage import StorageService

logger = logging.getLogger("context8")

# ── Service Singletons ────────────────────────────────────────────────────────

_embedding_service: EmbeddingService | None = None
_storage_service: StorageService | None = None
_search_engine: SearchEngine | None = None


def _get_services() -> tuple[EmbeddingService, StorageService, SearchEngine]:
    """Lazy-init and return service singletons."""
    global _embedding_service, _storage_service, _search_engine

    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    if _storage_service is None:
        _storage_service = StorageService()
        _storage_service.initialize()
    if _search_engine is None:
        _search_engine = SearchEngine(_storage_service, _embedding_service)

    return _embedding_service, _storage_service, _search_engine


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("context8")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Register Context8 tools."""
    return [
        Tool(
            name="context8_search",
            description=(
                "Search Context8 for past solutions to coding problems. "
                "Returns semantically similar problems that were previously "
                "solved by coding agents, with their solutions and code diffs. "
                "Use when you encounter an error that might have been solved before, "
                "especially after your first fix attempt fails."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Problem description, error message, or question",
                    },
                    "code_context": {
                        "type": "string",
                        "description": "Code snippet where the error occurs (improves accuracy)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Filter by programming language (python, typescript, rust, etc.)",
                    },
                    "framework": {
                        "type": "string",
                        "description": "Filter by framework (react, django, fastapi, etc.)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 5, max 20)",
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
                "Call this after you successfully fix a non-trivial error. "
                "This builds the collective memory so future agents can find "
                "this solution. Only log genuinely useful solutions — not "
                "trivial typos or simple syntax errors."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "What went wrong — the error, symptoms, context",
                    },
                    "solution": {
                        "type": "string",
                        "description": "How you fixed it — what you changed and why",
                    },
                    "error_type": {
                        "type": "string",
                        "description": "Error class (TypeError, ImportError, etc.)",
                    },
                    "code_snippet": {"type": "string", "description": "The fix code"},
                    "code_diff": {"type": "string", "description": "Before/after diff"},
                    "stack_trace": {"type": "string", "description": "Relevant stack trace"},
                    "language": {"type": "string", "description": "Programming language"},
                    "framework": {"type": "string", "description": "Framework in use"},
                    "libraries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Library versions",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Descriptive tags",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 (default 0.8)",
                        "default": 0.8,
                    },
                    "file_path": {"type": "string", "description": "File path of the fix"},
                },
                "required": ["problem", "solution"],
            },
        ),
        Tool(
            name="context8_stats",
            description="Get Context8 knowledge base statistics — record count, health status, vector spaces.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to handlers."""
    try:
        if name == "context8_search":
            return _handle_search(arguments)
        elif name == "context8_log":
            return _handle_log(arguments)
        elif name == "context8_stats":
            return _handle_stats(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Context8 error: {str(e)}")]


# ── Tool Handlers ─────────────────────────────────────────────────────────────


def _handle_search(args: dict) -> list[TextContent]:
    """Execute hybrid search and return formatted results."""
    embeddings, storage, engine = _get_services()

    results = engine.search(
        query=args["query"],
        code_context=args.get("code_context", ""),
        language=args.get("language"),
        framework=args.get("framework"),
        limit=min(args.get("limit", 5), 20),
    )

    if not results:
        return [
            TextContent(
                type="text",
                text=(
                    "No matching solutions found in Context8. "
                    "This might be a new problem. After you resolve it, "
                    "consider logging the solution with context8_log."
                ),
            )
        ]

    lines = [f"Found {len(results)} solution(s) in Context8:\n"]

    for i, result in enumerate(results, 1):
        r = result.record
        lines.append(f"--- Solution {i} (score: {result.score:.3f}) ---")
        lines.append(f"Problem: {r.problem_text}")
        lines.append(f"Solution: {r.solution_text}")
        if r.code_diff:
            lines.append(f"Code change:\n{r.code_diff}")
        if r.code_snippet:
            lines.append(f"Code:\n{r.code_snippet}")

        meta = []
        if r.language:
            meta.append(r.language)
        if r.framework:
            meta.append(r.framework)
        if r.error_type:
            meta.append(r.error_type)
        if meta:
            lines.append(f"Context: {' / '.join(meta)}")
        if r.tags:
            lines.append(f"Tags: {', '.join(r.tags)}")
        lines.append(f"Confidence: {r.confidence:.0%}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


def _handle_log(args: dict) -> list[TextContent]:
    """Log a new resolution record."""
    embeddings, storage, engine = _get_services()

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
        agent="mcp-agent",
    )

    # Check for duplicates
    existing = engine.find_duplicate(record.problem_text)
    if existing:
        return [
            TextContent(
                type="text",
                text=(
                    f"Similar solution already exists (score: {existing.score:.3f}). "
                    f"Record ID: {existing.record.id}. Skipping duplicate."
                ),
            )
        ]

    # Embed and store
    vectors = embeddings.embed_record(
        problem_text=record.problem_text,
        solution_text=record.solution_text,
        code_snippet=record.code_snippet,
    )
    record_id = storage.store_record(record, vectors)

    return [
        TextContent(
            type="text",
            text=(
                f"Solution logged to Context8. Record ID: {record_id}. "
                f"Future agents encountering similar problems will find this."
            ),
        )
    ]


def _handle_stats(args: dict) -> list[TextContent]:
    """Return knowledge base statistics."""
    _, storage, _ = _get_services()

    total = storage.count()
    collection_info = storage.get_collection_info()
    status = collection_info.get("status", "unknown") if collection_info else "unknown"

    lines = [
        "Context8 Knowledge Base:",
        f"  Records:       {total}",
        f"  Collection:    {COLLECTION_NAME}",
        f"  Endpoint:      {DB_URL}",
        "  Vector spaces: problem (384d), solution (384d), code_context (768d)",
        f"  Sparse:        {'enabled' if storage.sparse_supported else 'disabled (fallback mode)'}",
        f"  Status:        {status}",
    ]

    return [TextContent(type="text", text="\n".join(lines))]


# ── Server Entrypoint ─────────────────────────────────────────────────────────


async def run_server():
    """Run the Context8 MCP server on stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Context8 MCP server starting...")

    # Warm up models in background
    embeddings, _, _ = _get_services()
    threading.Thread(target=embeddings.warmup, daemon=True).start()

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_server())
