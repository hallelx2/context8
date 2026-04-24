"""Additional MCP tools: browse, ecosystem scan, difficulty tagging.

These supplement the core tools (search, log, rate, stats) with
discovery and preparation capabilities that agents use to build
skills and prevent known problems proactively.
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent, Tool


def extra_tools() -> list[Tool]:
    """Return additional MCP tools for discovery and skill prep."""
    return [
        Tool(
            name="context8_browse",
            description=(
                "Browse Context8 records by metadata without a search query. "
                "Use to discover what problems exist for a language, framework, "
                "or tag. Returns a list of records matching the filters."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Filter by language (python, typescript, etc.)",
                    },
                    "framework": {
                        "type": "string",
                        "description": "Filter by framework (react, django, etc.)",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter by tag (docker, prisma, etc.)",
                    },
                    "error_type": {
                        "type": "string",
                        "description": "Filter by error class (TypeError, etc.)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="context8_ecosystem",
            description=(
                "Get all known problems for a tech stack / ecosystem. "
                "Use this BEFORE starting a new project to learn what "
                "problems other agents have hit with this combination. "
                "The output is formatted so you can use it to write a "
                "CLAUDE.md section or a skill file with known pitfalls."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Languages to scan (e.g. ['typescript', 'python'])",
                    },
                    "frameworks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Frameworks to scan (e.g. ['nextjs', 'prisma'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results per category (default 10)",
                        "default": 10,
                    },
                },
                "required": ["languages"],
            },
        ),
    ]


def call_extra_tool(name: str, arguments: dict[str, Any]) -> list[TextContent] | None:
    """Handle extra tool calls. Returns None if tool not recognized."""
    if name == "context8_browse":
        return _handle_browse(arguments)
    if name == "context8_ecosystem":
        return _handle_ecosystem(arguments)
    return None


def _handle_browse(args: dict) -> list[TextContent]:
    from ..browse import browse
    from ..storage import StorageService

    storage = StorageService()

    records = browse(
        storage,
        tag=args.get("tag"),
        language=args.get("language"),
        framework=args.get("framework"),
        error_type=args.get("error_type"),
        limit=args.get("limit", 20),
    )

    if not records:
        return [TextContent(type="text", text="No records match those filters.")]

    lines = [f"Found {len(records)} record(s):\n"]
    for i, r in enumerate(records, 1):
        meta = []
        if r.language:
            meta.append(r.language)
        if r.framework:
            meta.append(r.framework)
        if r.error_type:
            meta.append(r.error_type)
        meta_str = f" ({', '.join(meta)})" if meta else ""

        lines.append(f"[{i}] {r.problem_text[:120]}{meta_str}")
        lines.append(f"    Fix: {r.solution_text[:150]}")
        if r.tags:
            lines.append(f"    Tags: {', '.join(r.tags[:5])}")
        lines.append(f"    ID: {r.id}  Confidence: {r.confidence:.0%}")
        lines.append("")

    storage.close()
    return [TextContent(type="text", text="\n".join(lines))]


def _handle_ecosystem(args: dict) -> list[TextContent]:
    from ..browse import browse
    from ..storage import StorageService

    storage = StorageService()

    languages = args.get("languages", [])
    frameworks = args.get("frameworks", [])
    limit = args.get("limit", 10)

    all_records = []
    seen_ids: set[str] = set()

    # Collect records across all specified languages and frameworks
    for lang in languages:
        records = browse(storage, language=lang, limit=limit)
        for r in records:
            if r.id not in seen_ids:
                all_records.append(r)
                seen_ids.add(r.id)

    for fw in frameworks:
        records = browse(storage, framework=fw, limit=limit)
        for r in records:
            if r.id not in seen_ids:
                all_records.append(r)
                seen_ids.add(r.id)

    storage.close()

    if not all_records:
        stack = ", ".join(languages + frameworks)
        return [
            TextContent(
                type="text",
                text=f"No known problems found for [{stack}] in Context8.",
            )
        ]

    # Format as skill-ready content the agent can use directly
    stack = " + ".join(languages + frameworks)
    lines = [
        f"# Known Problems for {stack}",
        "",
        f"Context8 has {len(all_records)} known problem(s) for this ecosystem.",
        "Use these to write a CLAUDE.md section or skill file.",
        "",
    ]

    # Group by error type
    by_type: dict[str, list] = {}
    for r in all_records:
        key = r.error_type or "General"
        by_type.setdefault(key, []).append(r)

    for error_type, records in sorted(by_type.items()):
        lines.append(f"## {error_type}")
        lines.append("")
        for r in records:
            lines.append(f"**Problem:** {r.problem_text}")
            lines.append(f"**Fix:** {r.solution_text}")
            if r.tags:
                lines.append(f"**Tags:** {', '.join(r.tags)}")
            lines.append(f"**Confidence:** {r.confidence:.0%}")
            lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
