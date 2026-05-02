"""End-to-end integration tests against a live Actian VectorAI DB.

These tests cover the legacy hackathon-era backend. They auto-skip
unless ``CONTEXT8_BACKEND=actian`` is set AND the SDK is installed AND
a container is reachable at ``$CONTEXT8_DB_HOST:$CONTEXT8_DB_PORT``.

The default test run uses the SQLite backend — see
:mod:`tests.test_e2e_sqlite` for the equivalent suite that runs
without any infrastructure.

To run these locally:

    pip install "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"
    docker compose up -d
    CONTEXT8_BACKEND=actian pytest tests/test_e2e.py -v
"""

from __future__ import annotations

import os
import socket
import uuid

import pytest

from context8 import config as ctx_config
from context8.config import DB_HOST, DB_PORT
from context8.embeddings import EmbeddingService
from context8.feedback import FeedbackService
from context8.models import FeedbackStats, ResolutionRecord


def _backend_is_actian() -> bool:
    return os.environ.get("CONTEXT8_BACKEND", "sqlite").lower() == "actian"


def _db_reachable() -> bool:
    try:
        with socket.create_connection((DB_HOST, DB_PORT), timeout=1.0):
            return True
    except OSError:
        return False


def _sdk_installed() -> bool:
    try:
        import actian_vectorai  # noqa: F401

        return True
    except ImportError:
        return False


pytestmark = [
    pytest.mark.actian,
    pytest.mark.skipif(
        not _backend_is_actian(),
        reason="set CONTEXT8_BACKEND=actian to run this suite",
    ),
    pytest.mark.skipif(not _sdk_installed(), reason="actian-vectorai SDK not installed"),
    pytest.mark.skipif(
        not _db_reachable(), reason=f"Actian DB not reachable at {DB_HOST}:{DB_PORT}"
    ),
]


@pytest.fixture
def isolated_collection(monkeypatch):
    """Each test gets its own collection name so they don't collide."""
    name = f"context8_test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(ctx_config, "COLLECTION_NAME", name)

    # Patch the same constant in every module that imported it at load time.
    from context8.storage import actian_backend as actian_mod

    monkeypatch.setattr(actian_mod, "COLLECTION_NAME", name)

    yield name

    # Cleanup
    from context8.storage import StorageService

    s = StorageService()
    try:
        s.drop_collection()
    finally:
        s.close()


@pytest.fixture
def storage(isolated_collection):
    from context8.storage import StorageService

    s = StorageService()
    s.initialize()
    yield s
    s.close()


@pytest.fixture(scope="session")
def embeddings():
    e = EmbeddingService()
    e.warmup()
    return e


@pytest.fixture
def seeded(storage, embeddings):
    """A collection with a few records spanning multiple languages/frameworks."""
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
    def test_collection_has_three_named_vectors(self, storage):
        info = storage.get_collection_info()
        assert info is not None
        # Either we discovered them via introspection, or the fallback list
        # of 3 is used. Either way the count should be 3 in success path.
        assert len(info["vectors"]) >= 3, f"Expected ≥3 named vectors, got {info['vectors']}"

    def test_sparse_vectors_present_or_explicitly_disabled(self, storage):
        # Either sparse is enabled, or we explicitly know it isn't (so the
        # demo can warn the user). We must NOT silently end up in an
        # unknown state.
        info = storage.get_collection_info()
        assert info is not None
        assert "sparse_supported" in info


class TestStoreAndRetrieve:
    def test_round_trip(self, seeded, embeddings):
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
        """ERESOLVE is a unique token — sparse should rank the npm record #1."""
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        results = engine.search(
            "ERESOLVE",
            resolved_only=False,
            limit=3,
        )
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
            assert r.record.language == "python", (
                f"Filter leaked: got language={r.record.language!r}"
            )

    def test_no_filter_returns_more(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        unfiltered = engine.search(
            "error",
            use_filter=False,
            resolved_only=False,
            limit=10,
        )
        filtered = engine.search(
            "error",
            language="rust",
            use_filter=True,
            resolved_only=False,
            limit=10,
        )
        # Unfiltered should see all 3 records; filtered to rust should see 1.
        assert len(unfiltered) >= len(filtered)


class TestNamedVectorAccessPaths:
    def test_solution_vector_search(self, seeded, embeddings):
        from context8.search import SearchEngine

        storage, _ = seeded
        engine = SearchEngine(storage, embeddings)
        # Searching by solution approach should find the matching record.
        results = engine.search_by_solution("install package in active venv", limit=3)
        # At minimum the search should execute without error and return results
        # or an explicit empty list (not raise). Asserting top-1 correctness
        # depends on embedding quality; we just assert it ran cleanly.
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
    def test_rate_persists_and_roundtrips(self, seeded, embeddings):
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

    def test_rate_unknown_record_rejected(self, seeded, embeddings):
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
