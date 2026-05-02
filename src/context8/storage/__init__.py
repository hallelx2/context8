"""Pluggable storage for Context8.

Default backend is SQLite + sqlite-vec + FTS5 (zero infrastructure).
Optional Actian backend lives behind ``pip install context8[actian]``
and ``CONTEXT8_BACKEND=actian``.

External callers should only import :class:`StorageService`, the
backend Protocol types, and ``SearchFilter`` / ``ScoredHit`` from this
package — never reach into a concrete backend module directly.
"""

from __future__ import annotations

from .actian_backend import ACTIAN_INSTALL_HINT, ActianBackend, _require_actian
from .backend import ScoredHit, SearchFilter, StorageBackend
from .service import StorageService
from .sqlite_backend import SQLiteBackend
from .sqlite_schema import DimMismatchError

__all__ = [
    "StorageService",
    "StorageBackend",
    "SQLiteBackend",
    "ActianBackend",
    "SearchFilter",
    "ScoredHit",
    "DimMismatchError",
    "ACTIAN_INSTALL_HINT",
    # Legacy import path — engine.py / browse.py still use it pre-refactor.
    "_require_actian",
]
