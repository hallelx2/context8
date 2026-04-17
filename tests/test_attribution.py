from __future__ import annotations

from dataclasses import dataclass

from context8.search.attribution import AttributionTracker


@dataclass
class _StubPoint:
    id: str
    score: float


class TestAttributionTracker:
    def test_empty_when_no_match(self):
        tracker = AttributionTracker()
        tracker.record("problem", [_StubPoint("a", 0.9), _StubPoint("b", 0.8)])
        attr = tracker.build_for("c")
        assert attr.contributions == []

    def test_records_strategy_score_and_rank(self):
        tracker = AttributionTracker()
        tracker.record("problem", [_StubPoint("a", 0.9), _StubPoint("b", 0.7)])
        tracker.record("keywords", [_StubPoint("b", 0.95), _StubPoint("a", 0.5)])

        attr_b = tracker.build_for("b")
        assert {c.strategy for c in attr_b.contributions} == {"problem", "keywords"}

        problem_c = next(c for c in attr_b.contributions if c.strategy == "problem")
        keyword_c = next(c for c in attr_b.contributions if c.strategy == "keywords")
        assert problem_c.rank == 2
        assert keyword_c.rank == 1
        assert keyword_c.score == 0.95

    def test_fused_when_multiple_strategies(self):
        tracker = AttributionTracker()
        tracker.record("problem", [_StubPoint("a", 0.9)])
        tracker.record("keywords", [_StubPoint("a", 0.8)])
        attr = tracker.build_for("a")
        assert attr.fused is True

    def test_not_fused_when_single_strategy(self):
        tracker = AttributionTracker()
        tracker.record("problem", [_StubPoint("a", 0.9)])
        attr = tracker.build_for("a")
        assert attr.fused is False
