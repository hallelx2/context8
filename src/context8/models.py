"""Data models for Context8 resolution records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass
class ResolutionRecord:
    """A problem-solution pair stored in Context8."""

    # ── Problem ───────────────────────────────────────────────────────────
    problem_text: str
    error_type: str = ""
    stack_trace: str = ""

    # ── Solution ──────────────────────────────────────────────────────────
    solution_text: str = ""
    code_snippet: str = ""
    code_diff: str = ""

    # ── Metadata ──────────────────────────────────────────────────────────
    language: str = ""
    framework: str = ""
    libraries: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    agent: str = "unknown"
    os: str = ""
    file_path: str = ""

    # ── Status ────────────────────────────────────────────────────────────
    resolved: bool = True
    confidence: float = 0.5

    # ── Auto-populated ────────────────────────────────────────────────────
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    occurrence_count: int = 1
    resolution_time_secs: int = 0
    last_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "local"

    def to_payload(self) -> dict:
        """Serialize to Actian VectorAI DB payload format."""
        return {
            "problem_text": self.problem_text,
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "solution_text": self.solution_text,
            "code_snippet": self.code_snippet,
            "code_diff": self.code_diff,
            "language": self.language,
            "framework": self.framework,
            "libraries": self.libraries,
            "tags": self.tags,
            "agent": self.agent,
            "os": self.os,
            "file_path": self.file_path,
            "resolved": self.resolved,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "occurrence_count": self.occurrence_count,
            "resolution_time_secs": self.resolution_time_secs,
            "last_seen": self.last_seen,
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, record_id: str, payload: dict) -> ResolutionRecord:
        """Reconstruct from Actian VectorAI DB payload."""
        return cls(
            id=record_id,
            problem_text=payload.get("problem_text", ""),
            error_type=payload.get("error_type", ""),
            stack_trace=payload.get("stack_trace", ""),
            solution_text=payload.get("solution_text", ""),
            code_snippet=payload.get("code_snippet", ""),
            code_diff=payload.get("code_diff", ""),
            language=payload.get("language", ""),
            framework=payload.get("framework", ""),
            libraries=payload.get("libraries", []),
            tags=payload.get("tags", []),
            agent=payload.get("agent", "unknown"),
            os=payload.get("os", ""),
            file_path=payload.get("file_path", ""),
            resolved=payload.get("resolved", True),
            confidence=payload.get("confidence", 0.5),
            timestamp=payload.get("timestamp", ""),
            occurrence_count=payload.get("occurrence_count", 1),
            resolution_time_secs=payload.get("resolution_time_secs", 0),
            last_seen=payload.get("last_seen", ""),
            source=payload.get("source", "local"),
        )


@dataclass
class SearchResult:
    """A search result from Context8."""

    record: ResolutionRecord
    score: float
    match_type: str = "hybrid"  # "dense", "sparse", "hybrid", "dense_code"
