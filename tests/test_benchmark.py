from __future__ import annotations

from dataclasses import dataclass

from context8.benchmark import (
    GROUND_TRUTH,
    Configuration,
    GroundTruthQuery,
    _evaluate_config,
)
from context8.ingest import SEED_DATA, slug_to_id
from context8.models import ResolutionRecord, SearchResult


class TestSlugToId:
    def test_deterministic(self):
        assert slug_to_id("foo") == slug_to_id("foo")

    def test_distinct_slugs_distinct_ids(self):
        assert slug_to_id("foo") != slug_to_id("bar")

    def test_uuid_shape(self):
        sid = slug_to_id("py-cv2-venv")
        assert len(sid) == 36 and sid.count("-") == 4


class TestGroundTruth:
    def test_every_query_points_at_a_real_seed_slug(self):
        seed_slugs = {d["slug"] for d in SEED_DATA if "slug" in d}
        missing = [q for q in GROUND_TRUTH if q.expected_slug not in seed_slugs]
        assert not missing, (
            "Ground-truth references slugs that no seed record has: "
            f"{[q.expected_slug for q in missing]}"
        )

    def test_meaningful_query_count(self):
        # The benchmark needs enough queries that a single hit/miss doesn't
        # swing Recall@3 by more than a few points.
        assert len(GROUND_TRUTH) >= 20


@dataclass
class _StubResultPoint:
    """Minimal fake of the Actian search-result point shape."""

    id: str
    score: float
    payload: dict


class _StubSearchEngine:
    """Stub engine that returns canned results for benchmark math tests."""

    def __init__(self, canned: dict[str, list[str]]):
        # Map query string → list of record IDs to return, in rank order.
        self._canned = canned

    def search(self, query: str, **_kwargs) -> list[SearchResult]:
        ids = self._canned.get(query, [])
        return [
            SearchResult(
                record=ResolutionRecord(id=rid, problem_text=""),
                score=1.0 / (i + 1),
                match_type="dense",
            )
            for i, rid in enumerate(ids)
        ]


class TestEvaluateConfig:
    def _make_queries(self, slugs: list[str]) -> list[GroundTruthQuery]:
        return [GroundTruthQuery(query=s, expected_slug=s) for s in slugs]

    def test_perfect_recall(self):
        slugs = ["py-cv2-venv", "npm-eresolve-peer", "rust-borrow-loop"]
        queries = self._make_queries(slugs)
        canned = {s: [slug_to_id(s)] for s in slugs}
        engine = _StubSearchEngine(canned)

        result = _evaluate_config(Configuration("test"), engine, queries)  # type: ignore[arg-type]

        assert result.recall_at_1 == 1.0
        assert result.recall_at_3 == 1.0
        assert result.recall_at_5 == 1.0
        assert result.mrr == 1.0
        assert result.queries_run == 3
        assert result.queries_with_hit == 3
        assert result.misses == []

    def test_zero_recall(self):
        queries = self._make_queries(["py-cv2-venv", "rust-borrow-loop"])
        engine = _StubSearchEngine({})  # No results for any query

        result = _evaluate_config(Configuration("test"), engine, queries)  # type: ignore[arg-type]

        assert result.recall_at_1 == 0.0
        assert result.recall_at_3 == 0.0
        assert result.mrr == 0.0
        assert len(result.misses) == 2

    def test_partial_recall_with_rank_2(self):
        """Expected record at rank 2: counts for Recall@3 but not Recall@1, MRR=0.5."""
        slug = "py-cv2-venv"
        queries = self._make_queries([slug])
        canned = {slug: ["other-id", slug_to_id(slug), "another-id"]}
        engine = _StubSearchEngine(canned)

        result = _evaluate_config(Configuration("test"), engine, queries)  # type: ignore[arg-type]

        assert result.recall_at_1 == 0.0
        assert result.recall_at_3 == 1.0
        assert result.mrr == 0.5

    def test_recall_at_3_excludes_rank_4(self):
        slug = "py-cv2-venv"
        queries = self._make_queries([slug])
        canned = {
            slug: ["a", "b", "c", slug_to_id(slug), "e"]  # rank 4
        }
        engine = _StubSearchEngine(canned)

        result = _evaluate_config(Configuration("test"), engine, queries)  # type: ignore[arg-type]

        assert result.recall_at_3 == 0.0
        assert result.recall_at_5 == 1.0
        assert result.mrr == 0.25
