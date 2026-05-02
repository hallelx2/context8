"""SQLite + sqlite-vec + FTS5 storage backend (default).

All Context8 data lives in a single file at :data:`config.DB_PATH`
(default ``~/.context8/context8.db``). Three vec0 virtual tables hold the
named dense vectors; one FTS5 table provides BM25 lexical scoring;
metadata sits in a regular ``records`` table joined back via
``record_id``. JSON1 (``json_each``) handles the ``tags_any_of`` filter.

Cosine *distance* (lower = closer) comes back from vec0; we convert to a
similarity *score* (higher = better) via ``score = 1.0 - distance`` so
the engine sees the same direction Actian returned.

Concurrency: WAL mode + a 5s busy timeout. There is at most one writer
in this app (CLI ingest *or* MCP ``_handle_log``), so writer
serialisation by sqlite-vec is fine. Multiple readers (e.g. the MCP
search loop) run in parallel.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from pathlib import Path

from ..models import FeedbackStats, ResolutionRecord
from .backend import ScoredHit, SearchFilter
from .sqlite_schema import apply_migrations, apply_pragmas, drop_all

logger = logging.getLogger("context8.storage.sqlite")

_VEC_TABLE_FOR_SPACE = {
    "problem": ("vec_problem", "problem_vec"),
    "solution": ("vec_solution", "solution_vec"),
    "code_context": ("vec_code_context", "code_vec"),
}


def _serialize_f32(vec: list[float]) -> bytes:
    """Pack a Python float list into the sqlite-vec wire format."""
    return struct.pack(f"{len(vec)}f", *vec)


def _row_to_record(row: sqlite3.Row) -> ResolutionRecord:
    return ResolutionRecord(
        id=row["id"],
        problem_text=row["problem_text"] or "",
        error_type=row["error_type"] or "",
        stack_trace=row["stack_trace"] or "",
        solution_text=row["solution_text"] or "",
        code_snippet=row["code_snippet"] or "",
        code_diff=row["code_diff"] or "",
        language=row["language"] or "",
        framework=row["framework"] or "",
        libraries=json.loads(row["libraries"] or "[]"),
        tags=json.loads(row["tags"] or "[]"),
        agent=row["agent"] or "unknown",
        os=row["os"] or "",
        file_path=row["file_path"] or "",
        resolved=bool(row["resolved"]),
        confidence=float(row["confidence"] or 0.0),
        timestamp=row["timestamp"] or "",
        occurrence_count=int(row["occurrence_count"] or 1),
        resolution_time_secs=int(row["resolution_time_secs"] or 0),
        last_seen=row["last_seen"] or "",
        source=row["source"] or "local",
        feedback=FeedbackStats(
            applied_count=int(row["feedback_applied"] or 0),
            worked_count=int(row["feedback_worked"] or 0),
        ),
    )


class SQLiteBackend:
    """Default storage backend. See module docstring for design notes."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        text_dim: int,
        code_dim: int,
        use_code_model: bool,
    ):
        self._db_path = Path(db_path)
        self._text_dim = int(text_dim)
        self._code_dim = int(code_dim)
        self._use_code_model = bool(use_code_model)
        self._conn: sqlite3.Connection | None = None
        # FTS5 always supported — it ships with the stdlib sqlite3.
        self._sparse_supported = True

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import sqlite_vec
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    "sqlite-vec is required for the SQLite backend.\n  pip install sqlite-vec"
                ) from exc

            conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                isolation_level=None,  # we manage transactions explicitly
            )
            conn.row_factory = sqlite3.Row
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            apply_pragmas(conn)
            self._conn = conn
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        return apply_migrations(
            self.conn,
            text_dim=self._text_dim,
            code_dim=self._code_dim,
            use_code_model=self._use_code_model,
        )

    def collection_exists(self) -> bool:
        try:
            row = self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='records'"
            ).fetchone()
            return bool(row)
        except sqlite3.DatabaseError:
            return False

    def drop_collection(self) -> None:
        drop_all(self.conn)

    # ------------------------------------------------------------------
    # Record CRUD
    # ------------------------------------------------------------------
    def store_record(self, record: ResolutionRecord, vectors: dict) -> str:
        c = self.conn
        try:
            c.execute("BEGIN")
            self._upsert_record_row(record)
            self._upsert_vec("vec_problem", "problem_vec", record.id, vectors["problem"])
            self._upsert_vec("vec_solution", "solution_vec", record.id, vectors["solution"])
            self._upsert_vec("vec_code_context", "code_vec", record.id, vectors["code_context"])
            self._upsert_fts(record)
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return record.id

    def update_payload_only(self, record: ResolutionRecord) -> str:
        """Update metadata + FTS but leave vec0 rows untouched."""
        c = self.conn
        try:
            c.execute("BEGIN")
            self._upsert_record_row(record)
            self._upsert_fts(record)
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return record.id

    def update_record(self, record: ResolutionRecord, vectors: dict) -> str:
        return self.store_record(record, vectors)

    def get_record(self, record_id: str) -> ResolutionRecord | None:
        row = self.conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def delete_record(self, record_id: str) -> None:
        c = self.conn
        try:
            c.execute("BEGIN")
            c.execute("DELETE FROM records WHERE id = ?", (record_id,))
            c.execute("DELETE FROM vec_problem WHERE record_id = ?", (record_id,))
            c.execute("DELETE FROM vec_solution WHERE record_id = ?", (record_id,))
            c.execute("DELETE FROM vec_code_context WHERE record_id = ?", (record_id,))
            c.execute("DELETE FROM fts_records WHERE record_id = ?", (record_id,))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def _upsert_record_row(self, record: ResolutionRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO records(
                id, problem_text, error_type, stack_trace, solution_text,
                code_snippet, code_diff, language, framework, libraries,
                tags, agent, os, file_path, resolved, confidence, timestamp,
                occurrence_count, resolution_time_secs, last_seen, source,
                feedback_applied, feedback_worked
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                problem_text = excluded.problem_text,
                error_type = excluded.error_type,
                stack_trace = excluded.stack_trace,
                solution_text = excluded.solution_text,
                code_snippet = excluded.code_snippet,
                code_diff = excluded.code_diff,
                language = excluded.language,
                framework = excluded.framework,
                libraries = excluded.libraries,
                tags = excluded.tags,
                agent = excluded.agent,
                os = excluded.os,
                file_path = excluded.file_path,
                resolved = excluded.resolved,
                confidence = excluded.confidence,
                timestamp = excluded.timestamp,
                occurrence_count = excluded.occurrence_count,
                resolution_time_secs = excluded.resolution_time_secs,
                last_seen = excluded.last_seen,
                source = excluded.source,
                feedback_applied = excluded.feedback_applied,
                feedback_worked = excluded.feedback_worked
            """,
            (
                record.id,
                record.problem_text,
                record.error_type,
                record.stack_trace,
                record.solution_text,
                record.code_snippet,
                record.code_diff,
                record.language,
                record.framework,
                json.dumps(list(record.libraries)),
                json.dumps(list(record.tags)),
                record.agent,
                record.os,
                record.file_path,
                1 if record.resolved else 0,
                float(record.confidence),
                record.timestamp,
                int(record.occurrence_count),
                int(record.resolution_time_secs),
                record.last_seen,
                record.source,
                int(record.feedback.applied_count),
                int(record.feedback.worked_count),
            ),
        )

    def _upsert_vec(self, table: str, column: str, record_id: str, vec: list[float]) -> None:
        # vec0 doesn't support ON CONFLICT in 0.1.x — delete + insert pattern.
        self.conn.execute(f"DELETE FROM {table} WHERE record_id = ?", (record_id,))
        self.conn.execute(
            f"INSERT INTO {table}(record_id, {column}) VALUES(?, ?)",
            (record_id, _serialize_f32(vec)),
        )

    def _upsert_fts(self, record: ResolutionRecord) -> None:
        self.conn.execute("DELETE FROM fts_records WHERE record_id = ?", (record.id,))
        self.conn.execute(
            "INSERT INTO fts_records("
            "record_id, problem_text, solution_text, code_snippet, error_type"
            ") VALUES(?, ?, ?, ?, ?)",
            (
                record.id,
                record.problem_text,
                record.solution_text,
                record.code_snippet,
                record.error_type,
            ),
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def count(self) -> int:
        try:
            row = self.conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()
            return int(row["n"])
        except sqlite3.DatabaseError:
            return 0

    def get_collection_info(self) -> dict | None:
        if not self.collection_exists():
            return None
        return {
            "status": "ready",
            "points": self.count(),
            "vectors": ["code_context", "problem", "solution"],
            "named_vector_count": 3,
            "sparse_vectors": ["keywords"],
            "sparse_supported": True,
            "hybrid_enabled": True,
            "backend": "sqlite",
            "db_path": str(self._db_path),
        }

    @property
    def sparse_supported(self) -> bool:
        return self._sparse_supported

    # ------------------------------------------------------------------
    # Search primitives
    # ------------------------------------------------------------------
    def search_dense(
        self,
        space: str,
        vector: list[float],
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        if space not in _VEC_TABLE_FOR_SPACE:
            raise ValueError(f"unknown vector space: {space!r}")
        table, column = _VEC_TABLE_FOR_SPACE[space]
        where_sql, where_params = _where_fragments(filter)

        # We KNN over vec0 (which requires a `MATCH ? AND k = ?` shape) and
        # join records back for both filtering and result hydration.
        # NB: vec0 doesn't support arbitrary WHERE on its own columns —
        # the filter goes on the joined records table.
        sql = (
            f"SELECT r.*, v.distance AS _distance "
            f"FROM {table} v "
            f"JOIN records r ON r.id = v.record_id "
            f"WHERE v.{column} MATCH ? AND k = ?" + where_sql + " ORDER BY v.distance"
        )
        params = [_serialize_f32(vector), int(limit), *where_params]
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning(f"dense search failed on {space}: {exc}")
            return []

        hits: list[ScoredHit] = []
        for row in rows:
            distance = float(row["_distance"])
            score = 1.0 - distance  # cosine_distance ∈ [0, 2] → score ∈ [-1, 1]
            hits.append(ScoredHit(record_id=row["id"], score=score, record=_row_to_record(row)))
        return hits

    def search_sparse(
        self,
        query_text: str,
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        if not query_text.strip():
            return []
        where_sql, where_params = _where_fragments(filter)
        match_query = _fts_match_query(query_text)
        if not match_query:
            return []

        # FTS5 ``rank`` is BM25, lower = better. Convert to a positive
        # similarity-style score in roughly [0, 1] via the "1 / (1 - rank)"
        # trick? No — rank is negative for BM25. We use ``-rank`` directly
        # and the engine's RRF treats raw values as ranks anyway.
        sql = (
            "SELECT r.*, fts.rank AS _rank "
            "FROM fts_records fts "
            "JOIN records r ON r.id = fts.record_id "
            "WHERE fts.fts_records MATCH ?" + where_sql + " ORDER BY fts.rank LIMIT ?"
        )
        params = [match_query, *where_params, int(limit)]
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning(f"sparse search failed: {exc}")
            return []

        hits: list[ScoredHit] = []
        for row in rows:
            # FTS5 BM25 rank is negative (lower = better). We expose
            # ``score = -rank`` so higher = better, matching the dense path.
            score = -float(row["_rank"])
            hits.append(ScoredHit(record_id=row["id"], score=score, record=_row_to_record(row)))
        return hits

    # ------------------------------------------------------------------
    # Browse / pagination
    # ------------------------------------------------------------------
    def scroll(
        self,
        filter: SearchFilter | None,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[ResolutionRecord], str | None]:
        # Cursor is just rowid > N — predictable ordering, cheap to encode.
        last_rowid = int(offset) if offset else 0
        where_sql, where_params = _where_fragments(filter)
        sql = (
            "SELECT r.*, r.rowid AS _rowid FROM records r "
            "WHERE r.rowid > ?" + where_sql + " ORDER BY r.rowid LIMIT ?"
        )
        params = [last_rowid, *where_params, int(limit)]
        rows = self.conn.execute(sql, params).fetchall()
        records = [_row_to_record(row) for row in rows]
        next_offset = str(rows[-1]["_rowid"]) if len(rows) == limit else None
        return records, next_offset


# ----------------------------------------------------------------------
# WHERE fragment builder — shared by dense, sparse, and scroll
# ----------------------------------------------------------------------
def _where_fragments(sf: SearchFilter | None) -> tuple[str, list]:
    if sf is None or sf.is_empty():
        return "", []
    parts: list[str] = []
    params: list = []
    if sf.language:
        parts.append("r.language = ?")
        params.append(sf.language.lower())
    if sf.framework:
        parts.append("r.framework = ?")
        params.append(sf.framework.lower())
    if sf.error_type:
        parts.append("r.error_type = ?")
        params.append(sf.error_type)
    if sf.source:
        parts.append("r.source = ?")
        params.append(sf.source)
    if sf.resolved_only:
        parts.append("r.resolved = 1")
    if sf.tags_any_of:
        placeholders = ",".join("?" * len(sf.tags_any_of))
        parts.append(
            f"EXISTS (SELECT 1 FROM json_each(r.tags) WHERE json_each.value IN ({placeholders}))"
        )
        params.extend(sf.tags_any_of)
    if not parts:
        return "", []
    return " AND " + " AND ".join(parts), params


# ----------------------------------------------------------------------
# FTS5 query escaping
# ----------------------------------------------------------------------
# Tokens FTS5's parser treats specially. We strip them aggressively and
# turn the rest into a phrase-soft query: each whitespace-separated token
# becomes its own quoted FTS5 term so error codes like "ERR_REQUIRE_ESM"
# survive without being parsed as boolean operators.
_FTS_RESERVED = set('"():*!^,')


def _fts_match_query(text: str) -> str:
    """Build a safe FTS5 MATCH query from arbitrary user text."""
    cleaned: list[str] = []
    for raw in text.split():
        token = "".join(ch for ch in raw if ch not in _FTS_RESERVED)
        if not token:
            continue
        # Quote everything to defang AND/OR/NOT and odd punctuation.
        cleaned.append(f'"{token}"')
    return " OR ".join(cleaned)
