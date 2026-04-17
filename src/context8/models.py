from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FeedbackStats:
    applied_count: int = 0
    worked_count: int = 0

    @property
    def worked_ratio(self) -> float:
        if self.applied_count == 0:
            return 0.0
        return self.worked_count / self.applied_count

    def to_dict(self) -> dict:
        return {
            "applied_count": self.applied_count,
            "worked_count": self.worked_count,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> FeedbackStats:
        data = data or {}
        return cls(
            applied_count=int(data.get("applied_count", 0)),
            worked_count=int(data.get("worked_count", 0)),
        )


@dataclass
class ResolutionRecord:
    problem_text: str
    error_type: str = ""
    stack_trace: str = ""

    solution_text: str = ""
    code_snippet: str = ""
    code_diff: str = ""

    language: str = ""
    framework: str = ""
    libraries: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    agent: str = "unknown"
    os: str = ""
    file_path: str = ""

    resolved: bool = True
    confidence: float = 0.5

    feedback: FeedbackStats = field(default_factory=FeedbackStats)

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=_utc_now_iso)
    occurrence_count: int = 1
    resolution_time_secs: int = 0
    last_seen: str = field(default_factory=_utc_now_iso)
    source: str = "local"

    def to_payload(self) -> dict:
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
            "feedback": self.feedback.to_dict(),
        }

    @classmethod
    def from_payload(cls, record_id: str, payload: dict) -> ResolutionRecord:
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
            feedback=FeedbackStats.from_dict(payload.get("feedback")),
        )


@dataclass
class StrategyContribution:
    strategy: str
    score: float
    rank: int


@dataclass
class Attribution:
    contributions: list[StrategyContribution] = field(default_factory=list)
    fused: bool = False

    @property
    def strategies(self) -> list[str]:
        return [c.strategy for c in self.contributions]

    def best(self) -> StrategyContribution | None:
        if not self.contributions:
            return None
        return min(self.contributions, key=lambda c: c.rank)


@dataclass
class SearchResult:
    record: ResolutionRecord
    score: float
    raw_score: float = 0.0
    match_type: str = "hybrid"
    attribution: Attribution = field(default_factory=Attribution)
    boost_factors: dict[str, float] = field(default_factory=dict)
