from __future__ import annotations

import math
from datetime import datetime, timezone

from ..config import (
    CONFIDENCE_BOOST_FLOOR,
    RECENCY_HALF_LIFE_DAYS,
    WORKED_RATIO_BOOST_FLOOR,
    WORKED_RATIO_MIN_SAMPLES,
)
from ..models import ResolutionRecord, SearchResult


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def confidence_factor(record: ResolutionRecord) -> float:
    floor = CONFIDENCE_BOOST_FLOOR
    return floor + (1.0 - floor) * max(0.0, min(1.0, record.confidence))


def recency_factor(record: ResolutionRecord, now: datetime | None = None) -> float:
    ts = _parse_iso(record.timestamp)
    if ts is None:
        return 1.0
    now = now or datetime.now(timezone.utc)
    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
    return math.exp(-math.log(2.0) * age_days / RECENCY_HALF_LIFE_DAYS)


def worked_ratio_factor(record: ResolutionRecord) -> float:
    fb = record.feedback
    if fb.applied_count < WORKED_RATIO_MIN_SAMPLES:
        return 1.0
    floor = WORKED_RATIO_BOOST_FLOOR
    return floor + (1.0 - floor) * fb.worked_ratio


class QualityRanker:
    def __init__(
        self,
        use_confidence: bool = True,
        use_recency: bool = True,
        use_feedback: bool = True,
    ):
        self.use_confidence = use_confidence
        self.use_recency = use_recency
        self.use_feedback = use_feedback

    def boost(self, results: list[SearchResult]) -> list[SearchResult]:
        now = datetime.now(timezone.utc)
        for r in results:
            factors = {}
            multiplier = 1.0
            if self.use_confidence:
                cf = confidence_factor(r.record)
                factors["confidence"] = cf
                multiplier *= cf
            if self.use_recency:
                rf = recency_factor(r.record, now=now)
                factors["recency"] = rf
                multiplier *= rf
            if self.use_feedback:
                wf = worked_ratio_factor(r.record)
                factors["worked_ratio"] = wf
                multiplier *= wf
            r.raw_score = r.score
            r.score = r.score * multiplier
            r.boost_factors = factors

        results.sort(key=lambda r: r.score, reverse=True)
        return results
