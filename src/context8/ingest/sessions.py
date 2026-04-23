"""Mine problem-solution pairs from coding agent session transcripts.

Parses Claude Code session JSONL files to find error→fix patterns:
  1. Tool call that produced an error
  2. Subsequent tool calls that resolved it
  3. Extract the problem (error) and solution (what the agent did)

Usage:
    context8 mine ~/.claude/sessions/
    context8 mine ~/.cursor/conversations/
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..models import ResolutionRecord

logger = logging.getLogger("context8.ingest.sessions")

MINE_NAMESPACE = uuid.UUID("c0c8c0c8-0000-0000-0000-00000000009e")

# Patterns that indicate an error occurred
ERROR_INDICATORS = [
    r"(?i)\bError\b[:\s]",
    r"(?i)\bException\b[:\s]",
    r"(?i)\bTraceback\b",
    r"(?i)\bFATAL\b",
    r"(?i)\bfailed\b",
    r"(?i)\bERR_\w+",
    r"(?i)\bexit code [1-9]",
    r"(?i)\bcommand failed\b",
    r"(?i)\bpanic\b",
]

ERROR_RE = re.compile("|".join(ERROR_INDICATORS))

# Patterns that indicate a fix was applied
FIX_INDICATORS = [
    r"(?i)\bfixed\b",
    r"(?i)\bresolved\b",
    r"(?i)\bworkaround\b",
    r"(?i)\bsolution\b",
    r"(?i)\bexit code 0\b",
    r"(?i)\bsuccess",
    r"(?i)\bpassed\b",
    r"(?i)\bcompiled? successfully\b",
]

FIX_RE = re.compile("|".join(FIX_INDICATORS))

# Extract error class names
ERROR_CLASS_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception))\b")


def _session_record_id(session_file: str, index: int) -> str:
    return str(uuid.uuid5(MINE_NAMESPACE, f"{session_file}:{index}"))


@dataclass
class MinedPair:
    """A problem-solution pair extracted from a session."""

    error_text: str
    fix_text: str
    error_type: str
    code_snippet: str
    source_file: str


def _parse_jsonl_session(path: Path) -> list[dict]:
    """Parse a JSONL session file into a list of message dicts."""
    messages = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError as e:
        logger.debug(f"Cannot read {path}: {e}")
    return messages


def _extract_text(msg: dict) -> str:
    """Extract readable text from a session message."""
    # Handle various message formats
    if isinstance(msg.get("content"), str):
        return msg["content"]
    if isinstance(msg.get("content"), list):
        parts = []
        for block in msg["content"]:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", block.get("content", "")))
        return "\n".join(parts)
    if isinstance(msg.get("message"), str):
        return msg["message"]
    if isinstance(msg.get("text"), str):
        return msg["text"]
    return ""


def mine_session_file(path: Path) -> list[MinedPair]:
    """Extract error→fix pairs from a single session file."""
    messages = _parse_jsonl_session(path)
    if not messages:
        return []

    pairs: list[MinedPair] = []
    pending_error: str | None = None
    pending_error_type: str = ""
    pending_code: str = ""

    for msg in messages:
        text = _extract_text(msg)
        if not text or len(text) < 20:
            continue

        if ERROR_RE.search(text) and not FIX_RE.search(text):
            # This looks like an error
            pending_error = text[:2000]  # Cap length
            match = ERROR_CLASS_RE.search(text)
            pending_error_type = match.group(1) if match else ""

            # Try to extract code from the error context
            code_match = re.search(r"```[\w]*\n(.*?)```", text, re.DOTALL)
            pending_code = code_match.group(1).strip()[:1000] if code_match else ""

        elif pending_error and FIX_RE.search(text):
            # This looks like a fix following an error
            pairs.append(
                MinedPair(
                    error_text=pending_error,
                    fix_text=text[:2000],
                    error_type=pending_error_type,
                    code_snippet=pending_code,
                    source_file=str(path),
                )
            )
            pending_error = None
            pending_error_type = ""
            pending_code = ""

    return pairs


def mine_directory(
    directory: Path,
    max_files: int = 100,
) -> list[ResolutionRecord]:
    """Mine all session files in a directory for problem-solution pairs."""
    if not directory.exists():
        logger.warning(f"Directory does not exist: {directory}")
        return []

    # Find JSONL files (Claude Code sessions)
    session_files = sorted(directory.glob("**/*.jsonl"), key=os.path.getmtime, reverse=True)

    # Also check for JSON files (Cursor conversations)
    session_files.extend(sorted(directory.glob("**/*.json"), key=os.path.getmtime, reverse=True))

    # Limit to most recent
    session_files = session_files[:max_files]
    logger.info(f"Mining {len(session_files)} session files from {directory}")

    records: list[ResolutionRecord] = []
    seen_errors: set[str] = set()

    for i, path in enumerate(session_files):
        pairs = mine_session_file(path)

        for j, pair in enumerate(pairs):
            # Simple dedup: skip if we've seen very similar error text
            error_key = pair.error_text[:100].lower().strip()
            if error_key in seen_errors:
                continue
            seen_errors.add(error_key)

            records.append(
                ResolutionRecord(
                    id=_session_record_id(path.name, j),
                    problem_text=pair.error_text[:500],
                    solution_text=pair.fix_text[:500],
                    error_type=pair.error_type,
                    code_snippet=pair.code_snippet,
                    source="session_mine",
                    agent="claude-code" if ".claude" in str(directory) else "unknown",
                    confidence=0.6,  # Lower confidence — auto-extracted
                    tags=["mined", "auto-extracted"],
                )
            )

    logger.info(f"Mined {len(records)} unique problem-solution pairs")
    return records
