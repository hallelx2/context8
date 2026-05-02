"""Shared CLI helpers — Rich console + backend-aware health probes."""

from __future__ import annotations

from rich.console import Console

from ..config import BACKEND, DB_PATH, DB_URL

console = Console()


# ---------------------------------------------------------------------------
# Backend-aware connectivity check
# ---------------------------------------------------------------------------
def check_backend() -> tuple[bool, str]:
    """Return (ok, human-readable description). Picks the probe to run
    based on the active backend so callers don't have to know which is
    in use."""
    if BACKEND == "sqlite":
        return _check_sqlite()
    if BACKEND == "actian":
        return _check_actian()
    return False, f"Unknown CONTEXT8_BACKEND={BACKEND!r}"


# Back-compat alias — many commands still call check_db_connection().
def check_db_connection() -> tuple[bool, str]:
    return check_backend()


def _check_sqlite() -> tuple[bool, str]:
    """SQLite is reachable as long as the file is creatable and the
    sqlite-vec extension is loadable."""
    try:
        import sqlite3

        import sqlite_vec  # noqa: F401
    except ImportError as exc:
        return False, f"sqlite-vec not installed — pip install sqlite-vec ({exc})"

    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            row = conn.execute("SELECT vec_version()").fetchone()
            version = row[0] if row else "unknown"
        finally:
            conn.close()
        version_str = version if str(version).startswith("v") else f"v{version}"
        return True, f"SQLite + sqlite-vec {version_str} @ {DB_PATH}"
    except Exception as exc:
        return False, f"SQLite probe failed: {exc}"


def _check_actian() -> tuple[bool, str]:
    try:
        from actian_vectorai import VectorAIClient
    except ImportError:
        return False, ("actian-vectorai SDK not installed — run:\n    pip install context8[actian]")
    try:
        with VectorAIClient(DB_URL, timeout=5.0) as client:
            info = client.health_check()
            return True, f"{info.get('title', 'VectorAI DB')} v{info.get('version', '?')}"
    except Exception as exc:
        return False, str(exc)


def check_actian_sdk() -> tuple[bool, str]:
    """Legacy probe — kept for the doctor command which lists each
    backend's prerequisite explicitly. SQLite has its own equivalent
    check_sqlite_vec() below."""
    try:
        import actian_vectorai  # noqa: F401

        return True, "installed"
    except ImportError:
        return False, "not installed — pip install context8[actian]"


def check_sqlite_vec() -> tuple[bool, str]:
    try:
        import sqlite_vec

        return True, getattr(sqlite_vec, "__version__", "installed")
    except ImportError:
        return False, "not installed — pip install sqlite-vec"


def require_db() -> str:
    ok, info = check_backend()
    if not ok:
        if BACKEND == "actian":
            console.print(f"[red]X Cannot connect to Actian:[/] {info}")
            console.print("  Run [cyan]context8 start[/] first\n")
        else:
            console.print(f"[red]X Cannot use SQLite backend:[/] {info}\n")
        raise SystemExit(1)
    return info
