from __future__ import annotations

from context8.models import (
    Attribution,
    FeedbackStats,
    ResolutionRecord,
    SearchResult,
    StrategyContribution,
)


class TestFeedbackStats:
    def test_default_zero(self):
        fb = FeedbackStats()
        assert fb.applied_count == 0
        assert fb.worked_count == 0
        assert fb.worked_ratio == 0.0

    def test_ratio_calculation(self):
        fb = FeedbackStats(applied_count=4, worked_count=3)
        assert fb.worked_ratio == 0.75

    def test_roundtrip(self):
        fb = FeedbackStats(applied_count=10, worked_count=7)
        restored = FeedbackStats.from_dict(fb.to_dict())
        assert restored.applied_count == 10
        assert restored.worked_count == 7

    def test_from_none(self):
        fb = FeedbackStats.from_dict(None)
        assert fb.applied_count == 0


class TestResolutionRecordWithFeedback:
    def test_payload_includes_feedback(self):
        r = ResolutionRecord(
            problem_text="x",
            feedback=FeedbackStats(applied_count=2, worked_count=1),
        )
        payload = r.to_payload()
        assert payload["feedback"] == {"applied_count": 2, "worked_count": 1}

    def test_roundtrip_preserves_feedback(self):
        original = ResolutionRecord(
            problem_text="x",
            feedback=FeedbackStats(applied_count=5, worked_count=4),
        )
        restored = ResolutionRecord.from_payload(original.id, original.to_payload())
        assert restored.feedback.applied_count == 5
        assert restored.feedback.worked_count == 4


class TestAttribution:
    def test_empty_default(self):
        attr = Attribution()
        assert attr.contributions == []
        assert attr.fused is False
        assert attr.best() is None

    def test_best_picks_lowest_rank(self):
        attr = Attribution(
            contributions=[
                StrategyContribution(strategy="problem", score=0.8, rank=2),
                StrategyContribution(strategy="keywords", score=0.9, rank=1),
            ],
            fused=True,
        )
        assert attr.best().strategy == "keywords"

    def test_strategies(self):
        attr = Attribution(
            contributions=[
                StrategyContribution(strategy="problem", score=0.8, rank=2),
                StrategyContribution(strategy="keywords", score=0.9, rank=1),
            ]
        )
        assert attr.strategies == ["problem", "keywords"]


class TestSearchResultDefaults:
    def test_attribution_default_present(self):
        r = ResolutionRecord(problem_text="x")
        result = SearchResult(record=r, score=0.5)
        assert result.attribution.contributions == []
        assert result.boost_factors == {}
        assert result.raw_score == 0.0
