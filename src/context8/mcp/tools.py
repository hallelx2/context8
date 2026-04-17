from __future__ import annotations

import platform
from typing import Any

from mcp.types import TextContent, Tool

from ..config import COLLECTION_NAME, DB_URL
from ..embeddings import EmbeddingService
from ..feedback import FeedbackService
from ..models import ResolutionRecord, SearchResult
from ..search import SearchEngine
from ..storage import StorageService

_embedding_service: EmbeddingService | None = None
_storage_service: StorageService | None = None
_search_engine: SearchEngine | None = None
_feedback_service: FeedbackService | None = None


def get_services() -> tuple[EmbeddingService, StorageService, SearchEngine, FeedbackService]:
    global _embedding_service, _storage_service, _search_engine, _feedback_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    if _storage_service is None:
        _storage_service = StorageService()
        _storage_service.initialize()
    if _search_engine is None:
        _search_engine = SearchEngine(_storage_service, _embedding_service)
    if _feedback_service is None:
        _feedback_service = FeedbackService(_storage_service, _embedding_service)

    return _embedding_service, _storage_service, _search_engine, _feedback_service


def list_tools() -> list[Tool]:
    return [
        Tool(
            name="context8_search",
            description=(
                "Search Context8 for past solutions to coding problems. "
                "Returns semantically similar problems that were previously "
                "solved by coding agents, with their solutions, code diffs, "
                "confidence scores, and per-strategy attribution. "
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
            name="context8_rate",
            description=(
                "Report whether a previously-retrieved Context8 solution actually worked. "
                "Call after you applied a solution returned by context8_search and observed "
                "whether it fixed the problem. This feeds the worked-ratio re-ranker so "
                "future agents see the most reliable fixes first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "The id of the Context8 record you applied",
                    },
                    "worked": {
                        "type": "boolean",
                        "description": "Did the solution fix the problem?",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional one-line note about the outcome",
                    },
                },
                "required": ["record_id", "worked"],
            },
        ),
        Tool(
            name="context8_search_solutions",
            description=(
                "Find past Context8 records whose *solution approach* matches a description. "
                "Use this when you have a fix in mind ('add null guard', 'use exponential backoff') "
                "and want to see how other agents have applied that approach in the past."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "approach": {
                        "type": "string",
                        "description": "Description of the solution approach",
                    },
                    "language": {"type": "string", "description": "Optional language filter"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 5)",
                        "default": 5,
                    },
                },
                "required": ["approach"],
            },
        ),
        Tool(
            name="context8_stats",
            description="Get Context8 knowledge base statistics — record count, health status, vector spaces.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "context8_search":
        return _handle_search(arguments)
    if name == "context8_log":
        return _handle_log(arguments)
    if name == "context8_rate":
        return _handle_rate(arguments)
    if name == "context8_search_solutions":
        return _handle_search_solutions(arguments)
    if name == "context8_stats":
        return _handle_stats(arguments)
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _format_attribution(result: SearchResult) -> str:
    if not result.attribution.contributions:
        return result.match_type
    parts = []
    for c in sorted(result.attribution.contributions, key=lambda x: x.rank):
        parts.append(f"{c.strategy}@{c.rank}({c.score:.2f})")
    return " + ".join(parts)


def _format_boosts(result: SearchResult) -> str:
    if not result.boost_factors:
        return ""
    bits = [f"{name}={value:.2f}" for name, value in result.boost_factors.items()]
    return f"  boosts: {', '.join(bits)}"


def _format_feedback(record: ResolutionRecord) -> str:
    fb = record.feedback
    if fb.applied_count == 0:
        return ""
    return f"  feedback: {fb.worked_count}/{fb.applied_count} worked ({fb.worked_ratio:.0%})"


def _handle_search(args: dict) -> list[TextContent]:
    _, _, engine, _ = get_services()

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
        lines.append(
            f"--- Solution {i} (score: {result.score:.3f}, raw: {result.raw_score:.3f}) ---"
        )
        lines.append(f"Record ID: {r.id}")
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
        lines.append(f"Attribution: {_format_attribution(result)}")
        boosts = _format_boosts(result)
        if boosts:
            lines.append(boosts)
        feedback = _format_feedback(r)
        if feedback:
            lines.append(feedback)
        lines.append(
            "If you applied this solution, call context8_rate(record_id, worked) "
            "to improve future ranking."
        )
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


def _handle_log(args: dict) -> list[TextContent]:
    embeddings, storage, engine, _ = get_services()

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


def _handle_rate(args: dict) -> list[TextContent]:
    _, _, _, feedback = get_services()
    outcome = feedback.rate(
        record_id=args["record_id"],
        worked=bool(args["worked"]),
        notes=args.get("notes", ""),
    )

    if not outcome.accepted:
        return [
            TextContent(
                type="text",
                text=f"Feedback not recorded: {outcome.note or 'unknown error'}",
            )
        ]

    return [
        TextContent(
            type="text",
            text=(
                f"Feedback recorded for {outcome.record_id}. "
                f"Worked ratio is now {outcome.worked_count}/{outcome.applied_count} "
                f"({outcome.worked_ratio:.0%}). Future searches will weight this record accordingly."
            ),
        )
    ]


def _handle_search_solutions(args: dict) -> list[TextContent]:
    _, _, engine, _ = get_services()
    results = engine.search_by_solution(
        approach=args["approach"],
        language=args.get("language"),
        limit=min(args.get("limit", 5), 20),
    )

    if not results:
        return [TextContent(type="text", text="No matching solution approaches found in Context8.")]

    lines = [f"Found {len(results)} matching approach(es):\n"]
    for i, result in enumerate(results, 1):
        r = result.record
        lines.append(f"--- Approach {i} (score: {result.score:.3f}) ---")
        lines.append(f"Record ID: {r.id}")
        lines.append(f"Solution: {r.solution_text}")
        lines.append(f"Originally for: {r.problem_text}")
        lines.append("")
    return [TextContent(type="text", text="\n".join(lines))]


def _handle_stats(_args: dict) -> list[TextContent]:
    _, storage, _, _ = get_services()
    total = storage.count()
    info = storage.get_collection_info() or {}
    status = info.get("status", "unknown")

    lines = [
        "Context8 Knowledge Base:",
        f"  Records:       {total}",
        f"  Collection:    {COLLECTION_NAME}",
        f"  Endpoint:      {DB_URL}",
        f"  Named vectors: {info.get('named_vector_count', 0)} ({', '.join(info.get('vectors', []))})",
        f"  Sparse:        {'enabled' if info.get('sparse_supported') else 'disabled'}",
        f"  Hybrid ready:  {'yes' if info.get('hybrid_enabled') else 'no'}",
        f"  Status:        {status}",
    ]
    return [TextContent(type="text", text="\n".join(lines))]
