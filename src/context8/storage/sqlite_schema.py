"""DDL and schema-migration helpers for the SQLite backend.

The schema is small and stable. ``apply_migrations(conn, code_dim)`` is
idempotent — call it on every connection. It records its version in the
``schema_version`` table so future schema bumps can be staged.

The vec0 dim for ``vec_code_context`` is **fixed at create time**. If the
caller flips ``CONTEXT8_USE_CODE_MODEL`` after the DB is initialised, we
detect the mismatch via the ``meta`` table and raise a clear error
pointing at ``context8 init --force``.
"""

from __future__ import annotations

import sqlite3
from typing import Any

CURRENT_SCHEMA_VERSION = 1

# Tables that must exist before vec0/FTS5 virtuals are created.
DDL_BASE = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
      version    INTEGER PRIMARY KEY,
      applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS records (
      id                   TEXT PRIMARY KEY,
      problem_text         TEXT NOT NULL,
      error_type           TEXT NOT NULL DEFAULT '',
      stack_trace          TEXT NOT NULL DEFAULT '',
      solution_text        TEXT NOT NULL DEFAULT '',
      code_snippet         TEXT NOT NULL DEFAULT '',
      code_diff            TEXT NOT NULL DEFAULT '',
      language             TEXT NOT NULL DEFAULT '',
      framework            TEXT NOT NULL DEFAULT '',
      libraries            TEXT NOT NULL DEFAULT '[]',
      tags                 TEXT NOT NULL DEFAULT '[]',
      agent                TEXT NOT NULL DEFAULT 'unknown',
      os                   TEXT NOT NULL DEFAULT '',
      file_path            TEXT NOT NULL DEFAULT '',
      resolved             INTEGER NOT NULL DEFAULT 1,
      confidence           REAL NOT NULL DEFAULT 0.5,
      timestamp            TEXT NOT NULL,
      occurrence_count     INTEGER NOT NULL DEFAULT 1,
      resolution_time_secs INTEGER NOT NULL DEFAULT 0,
      last_seen            TEXT NOT NULL,
      source               TEXT NOT NULL DEFAULT 'local',
      feedback_applied     INTEGER NOT NULL DEFAULT 0,
      feedback_worked      INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_records_language   ON records(language)",
    "CREATE INDEX IF NOT EXISTS idx_records_framework  ON records(framework)",
    "CREATE INDEX IF NOT EXISTS idx_records_error_type ON records(error_type)",
    "CREATE INDEX IF NOT EXISTS idx_records_source     ON records(source)",
    "CREATE INDEX IF NOT EXISTS idx_records_resolved   ON records(resolved)",
    "CREATE INDEX IF NOT EXISTS idx_records_last_seen  ON records(last_seen)",
]

DDL_VEC_PROBLEM = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_problem USING vec0("
    "record_id TEXT PRIMARY KEY, "
    "problem_vec FLOAT[{dim}] distance=cosine)"
)
DDL_VEC_SOLUTION = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_solution USING vec0("
    "record_id TEXT PRIMARY KEY, "
    "solution_vec FLOAT[{dim}] distance=cosine)"
)
DDL_VEC_CODE_CONTEXT = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_code_context USING vec0("
    "record_id TEXT PRIMARY KEY, "
    "code_vec FLOAT[{dim}] distance=cosine)"
)
DDL_FTS = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS fts_records USING fts5("
    "record_id UNINDEXED, "
    "problem_text, solution_text, code_snippet, error_type, "
    "tokenize = 'unicode61 remove_diacritics 2')"
)


def _meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


class DimMismatchError(RuntimeError):
    """Raised when ``CONTEXT8_USE_CODE_MODEL`` (and thus the desired
    ``code_context`` dim) disagrees with what the existing DB was built
    against. vec0 dims are immutable after creation."""


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Always-on settings: WAL, busy-timeout, normal sync, JSON1 ready."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")


def apply_migrations(
    conn: sqlite3.Connection,
    *,
    text_dim: int,
    code_dim: int,
    use_code_model: bool,
) -> bool:
    """Create / verify schema. Returns True if anything new was created.

    Raises :class:`DimMismatchError` if the existing DB was built with a
    different ``code_dim``.
    """
    # Base tables first — they hold the meta we need to sanity-check the
    # vec0 dims before we (might) try to create them.
    for stmt in DDL_BASE:
        conn.execute(stmt)

    existing_code_dim = _meta_get(conn, "code_dim")
    if existing_code_dim is not None and int(existing_code_dim) != code_dim:
        raise DimMismatchError(
            f"context8 db was created with code_dim={existing_code_dim}, "
            f"but CONTEXT8_USE_CODE_MODEL={'1' if use_code_model else '0'} "
            f"wants code_dim={code_dim}. vec0 dims are immutable.\n\n"
            "To rebuild, export your data first then re-init:\n"
            "  context8 export -o backup.json\n"
            "  context8 init --force\n"
            "  context8 import backup.json"
        )

    existing_text_dim = _meta_get(conn, "text_dim")
    if existing_text_dim is not None and int(existing_text_dim) != text_dim:
        raise DimMismatchError(
            f"context8 db was created with text_dim={existing_text_dim}, "
            f"but config now wants text_dim={text_dim}. Use --force to rebuild."
        )

    created_anything = False

    # Vec tables — dims baked at create time.
    for stmt in (
        DDL_VEC_PROBLEM.format(dim=text_dim),
        DDL_VEC_SOLUTION.format(dim=text_dim),
        DDL_VEC_CODE_CONTEXT.format(dim=code_dim),
        DDL_FTS,
    ):
        cur = conn.execute(stmt)
        # SQLite doesn't tell us whether IF NOT EXISTS triggered creation,
        # but the row count is a poor signal anyway. Track via meta below.
        cur.close()

    if existing_code_dim is None:
        _meta_set(conn, "text_dim", text_dim)
        _meta_set(conn, "code_dim", code_dim)
        _meta_set(conn, "use_code_model", "1" if use_code_model else "0")
        _meta_set(
            conn,
            "schema_created_at",
            conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0],
        )
        created_anything = True

    # Record schema version (idempotent).
    conn.execute(
        "INSERT INTO schema_version(version) VALUES(?) ON CONFLICT(version) DO NOTHING",
        (CURRENT_SCHEMA_VERSION,),
    )

    conn.commit()
    return created_anything


def drop_all(conn: sqlite3.Connection) -> None:
    """Drop every Context8 object. Used by ``context8 init --force``."""
    for tbl in (
        "vec_problem",
        "vec_solution",
        "vec_code_context",
        "fts_records",
        "records",
        "meta",
        "schema_version",
    ):
        try:
            conn.execute(f"DROP TABLE IF EXISTS {tbl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
