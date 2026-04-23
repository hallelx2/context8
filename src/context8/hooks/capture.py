"""Auto-capture hook — logs errors and their resolutions to Context8.

Designed as a Claude Code notification hook that watches for error
patterns. When it detects an error followed by a successful operation,
it auto-logs the problem-solution pair without the agent needing to
call context8_log explicitly.

This runs as a lightweight check — if no DB or no actian SDK, it
exits silently. Never blocks the agent workflow.

Hook config (.claude/settings.json):
  "hooks": {
    "afterToolUse": [{
      "command": "python -m context8.hooks.capture"
    }]
  }

Reads tool output from stdin (piped by the hook system).
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile

# State file to track pending errors across hook invocations
STATE_FILE = os.path.join(tempfile.gettempdir(), "context8_capture_state.json")

ERROR_RE = re.compile(
    r"(?i)\bError\b[:\s]|(?i)\bException\b|(?i)\bTraceback\b"
    r"|(?i)\bfailed\b|(?i)\bERR_\w+|(?i)\bexit code [1-9]"
)
SUCCESS_RE = re.compile(r"(?i)\bexit code 0|(?i)\bsuccess|(?i)\bpassed\b|(?i)\bcompiled")
ERROR_CLASS_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception))\b")


def _read_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def _clear_state() -> None:
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
    except Exception:
        return

    if not raw.strip():
        return

    # Parse hook input
    output_text = raw.strip()
    try:
        data = json.loads(raw)
        output_text = str(data.get("output", data.get("result", data.get("content", raw))))
    except (json.JSONDecodeError, TypeError):
        pass

    if len(output_text) < 15:
        return

    state = _read_state()

    # Phase 1: detect error → store as pending
    if ERROR_RE.search(output_text) and not SUCCESS_RE.search(output_text):
        match = ERROR_CLASS_RE.search(output_text)
        state["pending_error"] = output_text[:1000]
        state["error_type"] = match.group(1) if match else ""
        _write_state(state)
        return

    # Phase 2: detect success after a pending error → auto-log
    if "pending_error" in state and SUCCESS_RE.search(output_text):
        error_text = state["pending_error"]
        error_type = state.get("error_type", "")
        fix_text = output_text[:1000]
        _clear_state()

        try:
            from context8.embeddings import EmbeddingService
            from context8.models import ResolutionRecord
            from context8.search import SearchEngine
            from context8.storage import StorageService

            storage = StorageService()
            embeddings = EmbeddingService()
            engine = SearchEngine(storage, embeddings)

            # Check for duplicates
            existing = engine.find_duplicate(error_text)
            if existing:
                storage.close()
                return  # Already logged

            record = ResolutionRecord(
                problem_text=error_text[:500],
                solution_text=fix_text[:500],
                error_type=error_type,
                source="auto_capture",
                agent="claude-code",
                confidence=0.5,  # Lower — auto-captured
                tags=["auto-captured"],
            )
            vectors = embeddings.embed_record(
                problem_text=record.problem_text,
                solution_text=record.solution_text,
            )
            storage.store_record(record, vectors)
            storage.close()

        except ImportError:
            pass
        except Exception:
            pass

    elif "pending_error" in state:
        # Not a success — keep waiting (error might be multi-step)
        pass


if __name__ == "__main__":
    main()
