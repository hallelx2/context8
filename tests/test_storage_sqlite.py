"""Unit tests for the SQLite storage backend.

These run on every platform without a daemon — they create a fresh
temp DB per test, exercise schema migration, vec0 round-trips, FTS5
ranking, JSON1 tag filters, the dim guard, and scroll pagination.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from context8.models import ResolutionRecord
from context8.storage.backend import SearchFilter
from context8.storage.sqlite_backend import SQLiteBackend
from context8.storage.sqlite_schema import (
    DimMismatchError,
    apply_migrations,
    apply_pragmas,
)


def _vec(seed: int, dim: int) -> list[float]:
    """Deterministic toy vector — good enough for ranking tests."""
    import random

    rng = random.Random(seed)
    return [rng.random() for _ in range(dim)]


@pytest.fixture
def backend(tmp_path: Path) -> SQLiteBackend:
    db = tmp_path / "ctx.db"
    b = SQLiteBackend(db, text_dim=384, code_dim=384, use_code_model=False)
    b.initialize()
    yield b
    b.close()


def _make(record_id: str = "", **overrides) -> ResolutionRecord:
    kwargs = dict(
        problem_text="default problem",
        solution_text="default solution",
        language="python",
    )
    kwargs.update(overrides)
    rec = ResolutionRecord(**kwargs)
    if record_id:
        rec.id = record_id
    return rec


def _vectors(seed: int = 0, dim: int = 384) -> dict:
    return {
        "problem": _vec(seed, dim),
        "solution": _vec(seed + 1, dim),
        "code_context": _vec(seed + 2, dim),
    }


class TestSchema:
    def test_initialize_is_idempotent(self, tmp_path: Path):
        db = tmp_path / "ctx.db"
        b = SQLiteBackend(db, text_dim=384, code_dim=384, use_code_model=False)
        first = b.initialize()
        second = b.initialize()
        assert first is True
        assert second is False
        assert b.collection_exists() is True
        b.close()

    def test_wal_pragma_active(self, tmp_path: Path):
        db = tmp_path / "ctx.db"
        b = SQLiteBackend(db, text_dim=384, code_dim=384, use_code_model=False)
        b.initialize()
        mode = b.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        b.close()

    def test_dim_mismatch_raises_clear_error(self, tmp_path: Path):
        db = tmp_path / "ctx.db"
        b1 = SQLiteBackend(db, text_dim=384, code_dim=384, use_code_model=False)
        b1.initialize()
        b1.close()

        # Same DB, but now request the 768d code-context vec0 — should fail.
        b2 = SQLiteBackend(db, text_dim=384, code_dim=768, use_code_model=True)
        with pytest.raises(DimMismatchError) as exc:
            b2.initialize()
        msg = str(exc.value)
        assert "code_dim=384" in msg
        assert "code_dim=768" in msg
        assert "init --force" in msg

    def test_drop_collection_cleans_everything(self, backend: SQLiteBackend):
        backend.store_record(_make(), _vectors())
        assert backend.count() == 1
        backend.drop_collection()
        # After drop, the records table is gone.
        with pytest.raises(sqlite3.OperationalError):
            backend.conn.execute("SELECT 1 FROM records").fetchone()


class TestRoundtrip:
    def test_store_and_get_preserves_payload(self, backend: SQLiteBackend):
        rec = _make(
            problem_text="ImportError: numpy",
            solution_text="pip install numpy",
            error_type="ImportError",
            language="python",
            framework="pytest",
            tags=["import", "venv"],
            libraries=["numpy>=1.20"],
            confidence=0.91,
        )
        rec.feedback.applied_count = 3
        rec.feedback.worked_count = 2
        rid = backend.store_record(rec, _vectors())
        got = backend.get_record(rid)
        assert got is not None
        assert got.problem_text == rec.problem_text
        assert got.solution_text == rec.solution_text
        assert got.error_type == "ImportError"
        assert got.language == "python"
        assert got.framework == "pytest"
        assert got.tags == ["import", "venv"]
        assert got.libraries == ["numpy>=1.20"]
        assert abs(got.confidence - 0.91) < 1e-6
        assert got.feedback.applied_count == 3
        assert got.feedback.worked_count == 2

    def test_update_payload_only_does_not_touch_vectors(self, backend: SQLiteBackend):
        rec = _make()
        backend.store_record(rec, _vectors(seed=0))
        # Snapshot the dense vector via search.
        before = backend.search_dense("problem", _vec(0, 384), None, 1)
        assert before and before[0].record_id == rec.id

        rec.feedback.applied_count = 5
        rec.feedback.worked_count = 4
        backend.update_payload_only(rec)

        # Vector still searchable with the original embedding (i.e. not rewritten).
        after = backend.search_dense("problem", _vec(0, 384), None, 1)
        assert after and after[0].record_id == rec.id
        # Counters persisted.
        got = backend.get_record(rec.id)
        assert got.feedback.applied_count == 5
        assert got.feedback.worked_count == 4

    def test_delete_record_removes_from_all_tables(self, backend: SQLiteBackend):
        rec = _make()
        backend.store_record(rec, _vectors())
        assert backend.count() == 1
        backend.delete_record(rec.id)
        assert backend.count() == 0
        assert backend.get_record(rec.id) is None
        # vec0 + FTS5 cleanup.
        assert backend.search_dense("problem", _vec(0, 384), None, 5) == []
        assert backend.search_sparse(rec.problem_text, None, 5) == []


class TestDenseSearch:
    def test_exact_match_scores_one(self, backend: SQLiteBackend):
        rec = _make()
        vecs = _vectors(seed=42)
        backend.store_record(rec, vecs)
        hits = backend.search_dense("problem", vecs["problem"], None, 5)
        assert len(hits) == 1
        # Identical normalized vectors → cosine_distance ≈ 0 → score ≈ 1.
        assert hits[0].score == pytest.approx(1.0, abs=1e-3)

    def test_unknown_space_raises(self, backend: SQLiteBackend):
        with pytest.raises(ValueError):
            backend.search_dense("not-a-space", _vec(0, 384), None, 5)

    def test_filter_narrows_results(self, backend: SQLiteBackend):
        backend.store_record(_make(language="python"), _vectors(seed=1))
        backend.store_record(_make(language="rust"), _vectors(seed=2))
        sf = SearchFilter(language="python")
        hits = backend.search_dense("problem", _vec(1, 384), sf, 5)
        assert len(hits) == 1
        assert hits[0].record.language == "python"


class TestSparseSearch:
    def test_fts_finds_rare_token(self, backend: SQLiteBackend):
        backend.store_record(
            _make(problem_text="ERESOLVE unable to resolve dependency tree"),
            _vectors(seed=1),
        )
        backend.store_record(
            _make(problem_text="Hydration mismatch in Next.js"),
            _vectors(seed=2),
        )
        hits = backend.search_sparse("ERESOLVE", None, 5)
        assert len(hits) == 1
        assert "ERESOLVE" in hits[0].record.problem_text

    def test_fts_safe_to_special_chars(self, backend: SQLiteBackend):
        # FTS5 punctuation should be defanged — this used to be a syntax
        # error if naively passed as MATCH input.
        backend.store_record(_make(problem_text="hello world"), _vectors())
        # Should not raise.
        hits = backend.search_sparse('AND OR ! () "" * hello', None, 5)
        assert len(hits) >= 1


class TestTagsAnyOfFilter:
    def test_tags_filter_via_json1(self, backend: SQLiteBackend):
        backend.store_record(_make(tags=["docker", "wsl2"]), _vectors(seed=1))
        backend.store_record(_make(tags=["react", "next.js"]), _vectors(seed=2))
        backend.store_record(_make(tags=[]), _vectors(seed=3))

        sf = SearchFilter(tags_any_of=["docker"])
        recs, _ = backend.scroll(sf, limit=10)
        assert len(recs) == 1
        assert "docker" in recs[0].tags

        sf = SearchFilter(tags_any_of=["docker", "react"])
        recs, _ = backend.scroll(sf, limit=10)
        assert len(recs) == 2


class TestScrollPagination:
    def test_paginates_with_cursor(self, backend: SQLiteBackend):
        for i in range(5):
            backend.store_record(_make(record_id=f"id-{i:02d}"), _vectors(seed=i))

        page1, off1 = backend.scroll(None, limit=2)
        assert len(page1) == 2
        assert off1 is not None

        page2, off2 = backend.scroll(None, limit=2, offset=off1)
        assert len(page2) == 2
        assert off2 is not None

        page3, off3 = backend.scroll(None, limit=2, offset=off2)
        assert len(page3) == 1  # only one left
        assert off3 is None

        # No overlap — concatenate and dedupe.
        all_ids = {r.id for r in page1 + page2 + page3}
        assert len(all_ids) == 5


class TestCollectionInfo:
    def test_info_shape_matches_protocol(self, backend: SQLiteBackend):
        info = backend.get_collection_info()
        assert info is not None
        assert info["status"] == "ready"
        assert info["named_vector_count"] == 3
        assert sorted(info["vectors"]) == ["code_context", "problem", "solution"]
        assert info["sparse_supported"] is True
        assert info["hybrid_enabled"] is True
        assert info["backend"] == "sqlite"

    def test_sparse_supported_property(self, backend: SQLiteBackend):
        assert backend.sparse_supported is True


class TestPragmas:
    def test_apply_pragmas_independently(self, tmp_path: Path):
        # apply_pragmas must be safe on a bare connection.
        conn = sqlite3.connect(str(tmp_path / "scratch.db"))
        apply_pragmas(conn)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_apply_migrations_requires_loaded_extension(self, tmp_path: Path):
        """apply_migrations creates vec0 tables — caller must load sqlite-vec first.

        This documents the contract: SQLiteBackend.conn loads the extension
        before calling apply_migrations. A bare connection isn't enough.
        """
        import sqlite_vec

        conn = sqlite3.connect(str(tmp_path / "scratch.db"))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        apply_pragmas(conn)
        created = apply_migrations(conn, text_dim=384, code_dim=384, use_code_model=False)
        assert created is True
        # Idempotent.
        again = apply_migrations(conn, text_dim=384, code_dim=384, use_code_model=False)
        assert again is False
        conn.close()
