"""End-to-end integration tests against the SQLite backend.

Mirrors :mod:`tests.test_e2e` (which targets Actian) but runs without
any infrastructure — a fresh ``tmp_path`` DB per test, no Docker, no
gRPC. These run on every CI matrix combination.

The fixtures monkeypatch ``CONTEXT8_DB_PATH`` so the on-disk file lands
in the test's ``tmp_path`` and is cleaned up automatically. The
embedding model is session-scoped (warming it once is expensive) and
shared across tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from context8.embeddings import EmbeddingService
from context8.feedback import FeedbackService
from context8.models import FeedbackStats, ResolutionRecord
from context8.storage import StorageService
from context8.storage.sqlite_backend import SQLiteBackend


@pytest.fixture(scope="session")
def embeddings() -> EmbeddingService:
    e = EmbeddingService()
    e.warmup()
    return e


@pytest.fixture
def storage(tmp_path: Path) -> StorageService:
    backend = SQLiteBackend(
        tmp_path / "ctx.db",
        text_dim=384,
        code_dim=384,
        use_code_model=False,
    )
    s = StorageService(backend=backend, name="sqlite")
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def seeded(storage: StorageService, embeddings: EmbeddingService):
    records = [
        ResolutionRecord(
            problem_text=(
                "ModuleNotFoundError: No module named 'cv2' even though "
                "opencv-python is installed via pip"
            ),
            solution_text="Install in active venv: pip install opencv-python-headless",
            error_type="ModuleNotFoundError",
            language="python",
        ),
        ResolutionRecord(
            problem_text=(
                "ERESOLVE unable to resolve dependency tree - npm peer dependency "
                "conflict after upgrading react"
            ),
            solution_text="Use --legacy-peer-deps or add overrides in package.json",
            error_type="ERESOLVE",
            language="javascript",
        ),
        ResolutionRecord(
            problem_text="borrow checker rejects mutating a vec while iterating",
            solution_text="Collect indices first, then mutate by index",
            language="rust",
        ),
    ]
    for r in records:
        v = embeddings.embed_record(r.problem_text, r.solution_text, "")
        storage.store_record(r, v)
    return storage, records


# ── Tests ─────────────────────────────────────────────────────────────────


class TestCollectionShape:
    def test_collection_has_three_named_vectors(self, storage: StorageService):
        info = storage.get_collection_info()
        assert info is not None
        assert len(info["vectors"]) == 3
        assert sorted(info["vectors"]) == ["code_context", "problem", "solution"]

    def test_sparse_vectors_present(self, storage: StorageService):
        info = storage.get_collection_info()
        assert info is not None
        assert info["sparse_supported"] is True
        assert info["hybrid_enabled"] is True

    def test_backend_self_identifies(self, storage: StorageService):
        info = storage.get_collection_info()
        assert info["backend"] == "sqlite"


class TestStoreAndRetrieve:
    def test_round_trip(self, seeded):
        storage, records = seeded
        assert storage.count() == len(records)
        first = records[0]
        fetched = storage.get_record(first.id)
        assert fetched is not None
        assert fetched.problem_text == first.problem_text


class TestHybridSearch:
    def test_dense_search_finds_paraphrased_query(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search(
            "opencv import broken inside virtualenv",
            resolved_only=False,
            limit=3,
        )
        assert results, "Dense search should find the cv2 record"
        assert any("cv2" in r.record.problem_text for r in results)

    def test_sparse_catches_exact_error_token(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search("ERESOLVE", resolved_only=False, limit=3)
        assert results
        assert "ERESOLVE" in results[0].record.problem_text


class TestFilteredSearch:
    def test_language_filter_excludes_other_languages(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)

        py_results = engine.search(
            "module import error",
            language="python",
            use_filter=True,
            resolved_only=False,
            limit=5,
        )
        for r in py_results:
            assert r.record.language == "python"

    def test_no_filter_returns_more(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        unfiltered = engine.search("error", use_filter=False, resolved_only=False, limit=10)
        filtered = engine.search(
            "error",
            language="rust",
            use_filter=True,
            resolved_only=False,
            limit=10,
        )
        assert len(unfiltered) >= len(filtered)


class TestNamedVectorAccessPaths:
    def test_solution_vector_search(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search_by_solution("install package in active venv", limit=3)
        assert isinstance(results, list)


class TestAblation:
    def test_dense_only_still_works(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search(
            "opencv import broken",
            use_problem_vector=True,
            use_code_vector=False,
            use_sparse=False,
            use_filter=False,
            resolved_only=False,
        )
        assert results

    def test_no_strategies_returns_empty(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search(
            "anything",
            use_problem_vector=False,
            use_code_vector=False,
            use_sparse=False,
            resolved_only=False,
        )
        assert results == []


class TestFeedbackLoop:
    def test_rate_persists_and_roundtrips(self, seeded):
        storage, records = seeded
        feedback = FeedbackService(storage)
        target = records[0]

        outcome = feedback.rate(target.id, worked=True)
        assert outcome.accepted
        assert outcome.applied_count == 1
        assert outcome.worked_count == 1

        outcome = feedback.rate(target.id, worked=False)
        assert outcome.applied_count == 2
        assert outcome.worked_count == 1

        refreshed = storage.get_record(target.id)
        assert refreshed is not None
        assert refreshed.feedback.applied_count == 2
        assert refreshed.feedback.worked_count == 1

    def test_rate_unknown_record_rejected(self, seeded):
        storage, _ = seeded
        feedback = FeedbackService(storage)
        outcome = feedback.rate("00000000-0000-0000-0000-000000000000", worked=True)
        assert not outcome.accepted


class TestAttribution:
    def test_attribution_populated_on_hybrid_search(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search("ERESOLVE peer dep mismatch", resolved_only=False, limit=3)
        assert results
        assert results[0].attribution.contributions
        strategies = {c.strategy for c in results[0].attribution.contributions}
        assert strategies & {"problem", "code_context", "keywords"}


class TestQualityBoost:
    def test_recent_high_confidence_outranks_stale(self, storage, embeddings):
        from context8.search import SearchEngine

        recent = ResolutionRecord(
            problem_text="hydration mismatch in next.js after react upgrade",
            solution_text="add suppressHydrationWarning",
            language="typescript",
            confidence=0.95,
        )
        stale = ResolutionRecord(
            problem_text="hydration mismatch in next.js after react upgrade older",
            solution_text="something old",
            language="typescript",
            confidence=0.5,
            timestamp="2019-01-01T00:00:00+00:00",
        )
        for rec in (recent, stale):
            v = embeddings.embed_record(rec.problem_text, rec.solution_text, "")
            storage.store_record(rec, v)

        engine = SearchEngine(storage, embeddings)
        boosted = engine.search(
            "hydration mismatch in next.js",
            apply_quality_boost=True,
            resolved_only=False,
            limit=2,
        )
        assert boosted
        assert boosted[0].record.id == recent.id

    def test_feedback_boosts_proven_record(self, storage, embeddings):
        from context8.search import SearchEngine

        winner = ResolutionRecord(
            problem_text="duplicate problem A — bug fix candidate",
            solution_text="fix one",
            language="python",
            feedback=FeedbackStats(applied_count=10, worked_count=10),
        )
        loser = ResolutionRecord(
            problem_text="duplicate problem A — bug fix candidate alt",
            solution_text="fix two",
            language="python",
            feedback=FeedbackStats(applied_count=10, worked_count=0),
        )
        for rec in (winner, loser):
            v = embeddings.embed_record(rec.problem_text, rec.solution_text, "")
            storage.store_record(rec, v)

        engine = SearchEngine(storage, embeddings)
        boosted = engine.search(
            "duplicate problem A bug fix candidate",
            apply_quality_boost=True,
            resolved_only=False,
            limit=2,
        )
        assert boosted
        assert boosted[0].record.id == winner.id


class TestDuplicateDetection:
    def test_find_duplicate_finds_close_match(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, records = seeded
        engine = SearchEngine(storage, embeddings)
        # Near-paraphrase of the cv2 record's problem.
        dup = engine.find_duplicate(records[0].problem_text, threshold=0.85)
        assert dup is not None
        assert dup.record.id == records[0].id

    def test_find_duplicate_or_variant_categorises(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, records = seeded
        engine = SearchEngine(storage, embeddings)
        # Same problem, similar solution → "duplicate"
        status, _ = engine.find_duplicate_or_variant(
            records[0].problem_text,
            records[0].solution_text,
        )
        assert status in ("duplicate", "variant")

        # Brand new problem → "new"
        status, _ = engine.find_duplicate_or_variant(
            "completely unrelated problem about quantum cryptography in haskell",
            "use Maybe monad",
        )
        assert status == "new"


class TestBrowseAndExportImport:
    def test_browse_by_language(self, seeded):
        from context8.browse import browse

        storage, _ = seeded
        py_records = browse(storage, language="python")
        assert all(r.language == "python" for r in py_records)
        assert len(py_records) >= 1

    def test_export_then_import_roundtrips(self, storage, embeddings, tmp_path: Path):
        from context8.export import export_json, import_json

        # Seed manually so we don't depend on the seeded fixture.
        recs = (
            ResolutionRecord(
                problem_text="problem one", solution_text="sol one", language="python"
            ),
            ResolutionRecord(problem_text="problem two", solution_text="sol two", language="rust"),
        )
        for rec in recs:
            v = embeddings.embed_record(rec.problem_text, rec.solution_text, "")
            storage.store_record(rec, v)
        assert storage.count() == 2

        out = tmp_path / "backup.json"
        n = export_json(storage, out)
        assert n == 2

        # Drop and re-import.
        storage.drop_collection()
        storage.initialize()
        assert storage.count() == 0

        imported = import_json(storage, embeddings, out)
        assert imported == 2
        assert storage.count() == 2
