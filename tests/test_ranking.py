from __future__ import annotations

from datetime import datetime, timedelta, timezone

from context8.models import FeedbackStats, ResolutionRecord, SearchResult
from context8.search.ranking import (
    QualityRanker,
    confidence_factor,
    recency_factor,
    worked_ratio_factor,
)


def _record(**kwargs) -> ResolutionRecord:
    defaults = dict(
        problem_text="x",
        solution_text="y",
        confidence=0.9,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(kwargs)
    return ResolutionRecord(**defaults)


def _result(record: ResolutionRecord, score: float = 0.5) -> SearchResult:
    return SearchResult(record=record, score=score, raw_score=score)


class TestConfidenceFactor:
    def test_high_confidence_no_penalty(self):
        r = _record(confidence=1.0)
        assert confidence_factor(r) == 1.0

    def test_low_confidence_penalized(self):
        r = _record(confidence=0.0)
        assert confidence_factor(r) < 1.0

    def test_floor_respected(self):
        r = _record(confidence=0.0)
        assert confidence_factor(r) >= 0.7


class TestRecencyFactor:
    def test_now_full_score(self):
        r = _record(timestamp=datetime.now(timezone.utc).isoformat())
        assert 0.99 < recency_factor(r) <= 1.0

    def test_old_record_decayed(self):
        old = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        r = _record(timestamp=old)
        assert recency_factor(r) < 0.5

    def test_invalid_timestamp_neutral(self):
        r = _record(timestamp="")
        assert recency_factor(r) == 1.0


class TestWorkedRatioFactor:
    def test_no_samples_neutral(self):
        r = _record()
        assert worked_ratio_factor(r) == 1.0

    def test_few_samples_neutral(self):
        r = _record(feedback=FeedbackStats(applied_count=2, worked_count=2))
        assert worked_ratio_factor(r) == 1.0

    def test_high_ratio_full_credit(self):
        r = _record(feedback=FeedbackStats(applied_count=10, worked_count=10))
        assert worked_ratio_factor(r) == 1.0

    def test_low_ratio_penalized(self):
        r = _record(feedback=FeedbackStats(applied_count=10, worked_count=0))
        assert worked_ratio_factor(r) < 1.0
        assert worked_ratio_factor(r) >= 0.6


class TestQualityRanker:
    def test_boost_changes_score_and_orders(self):
        fresh = _record(confidence=1.0, timestamp=datetime.now(timezone.utc).isoformat())
        stale = _record(
            confidence=0.5,
            timestamp=(datetime.now(timezone.utc) - timedelta(days=1000)).isoformat(),
        )
        results = [_result(stale, 0.9), _result(fresh, 0.85)]
        ranker = QualityRanker()
        boosted = ranker.boost(results)
        assert boosted[0].record is fresh

    def test_raw_score_preserved(self):
        r = _record(confidence=0.5)
        result = _result(r, 0.8)
        QualityRanker().boost([result])
        assert result.raw_score == 0.8
        assert result.score < 0.8

    def test_disabling_all_factors_is_identity(self):
        results = [_result(_record(), 0.5), _result(_record(), 0.4)]
        ranker = QualityRanker(use_confidence=False, use_recency=False, use_feedback=False)
        boosted = ranker.boost(results)
        assert boosted[0].score == 0.5
        assert boosted[1].score == 0.4
