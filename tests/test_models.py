"""Unit tests for data models — no DB or embedding models needed."""

from __future__ import annotations

from context8.models import ResolutionRecord, SearchResult


class TestResolutionRecord:
    def test_create_minimal(self):
        record = ResolutionRecord(problem_text="test error")
        assert record.problem_text == "test error"
        assert record.id  # UUID generated
        assert record.timestamp  # Auto-populated
        assert record.occurrence_count == 1
        assert record.resolved is True

    def test_defaults(self):
        record = ResolutionRecord(problem_text="test")
        assert record.confidence == 0.5
        assert record.source == "local"
        assert record.agent == "unknown"
        assert record.language == ""
        assert record.tags == []
        assert record.libraries == []

    def test_to_payload_roundtrip(self):
        original = ResolutionRecord(
            problem_text="TypeError in component",
            solution_text="Added null check",
            language="typescript",
            framework="react",
            tags=["null-check", "typescript"],
            confidence=0.92,
        )
        payload = original.to_payload()
        restored = ResolutionRecord.from_payload(original.id, payload)

        assert restored.problem_text == original.problem_text
        assert restored.solution_text == original.solution_text
        assert restored.language == original.language
        assert restored.tags == original.tags
        assert restored.confidence == original.confidence
        assert restored.id == original.id

    def test_payload_contains_all_fields(self):
        record = ResolutionRecord(problem_text="test")
        payload = record.to_payload()

        required_fields = [
            "problem_text",
            "solution_text",
            "error_type",
            "language",
            "framework",
            "tags",
            "libraries",
            "resolved",
            "confidence",
            "timestamp",
            "occurrence_count",
            "source",
        ]
        for field in required_fields:
            assert field in payload, f"Missing field: {field}"

    def test_unique_ids(self):
        a = ResolutionRecord(problem_text="a")
        b = ResolutionRecord(problem_text="b")
        assert a.id != b.id


class TestSearchResult:
    def test_create(self):
        record = ResolutionRecord(problem_text="test")
        result = SearchResult(record=record, score=0.85)
        assert result.score == 0.85
        assert result.match_type == "hybrid"

    def test_custom_match_type(self):
        record = ResolutionRecord(problem_text="test")
        result = SearchResult(record=record, score=0.5, match_type="dense")
        assert result.match_type == "dense"
