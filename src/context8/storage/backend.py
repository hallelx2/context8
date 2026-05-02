"""Pluggable storage backend interface for Context8.

Two implementations live alongside this module: ``SQLiteBackend`` (default,
zero-infrastructure) and ``ActianBackend`` (optional, hackathon-era,
gated behind the ``[actian]`` extra and ``CONTEXT8_BACKEND=actian``).

The engine, browse, export, feedback, and ingest layers all talk to the
backend through this Protocol — never to a vendor-specific client. The
``StorageService`` facade in :mod:`context8.storage.service` resolves the
backend from environment at import time and delegates every call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..models import ResolutionRecord


@dataclass
class SearchFilter:
    """Backend-agnostic filter built once and translated by each backend.

    Each backend converts this into its native form: ``SQLiteBackend``
    builds an SQL ``WHERE`` fragment + JSON1 ``json_each`` clause for
    ``tags_any_of``; ``ActianBackend`` builds a ``FilterBuilder`` chain.
    """

    language: str | None = None
    framework: str | None = None
    error_type: str | None = None
    source: str | None = None
    resolved_only: bool = False
    tags_any_of: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            self.language is None
            and self.framework is None
            and self.error_type is None
            and self.source is None
            and not self.resolved_only
            and not self.tags_any_of
        )


@dataclass
class ScoredHit:
    """A search result before quality boosting.

    ``record`` is populated when the backend can produce it cheaply
    (typical for SQLite — a single JOIN). When ``None``, the engine
    hydrates by calling ``backend.get_record(record_id)``.
    """

    record_id: str
    score: float
    record: ResolutionRecord | None = None


@runtime_checkable
class StorageBackend(Protocol):
    """The contract every backend implements.

    Methods are grouped by lifecycle, CRUD, introspection, search, and
    pagination. Adding a new backend (e.g., a future ``PostgresBackend``)
    means implementing every method here — nothing else in the codebase
    needs to change.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        """Create schema if missing. Return True if newly created."""
        ...

    def collection_exists(self) -> bool: ...

    def drop_collection(self) -> None:
        """Remove all data. Used by ``context8 init --force``."""
        ...

    def close(self) -> None: ...

    # ------------------------------------------------------------------
    # Record CRUD
    # ------------------------------------------------------------------
    def store_record(self, record: ResolutionRecord, vectors: dict) -> str: ...

    def update_payload_only(self, record: ResolutionRecord) -> str:
        """Update metadata without re-embedding vectors."""
        ...

    def update_record(self, record: ResolutionRecord, vectors: dict) -> str: ...

    def get_record(self, record_id: str) -> ResolutionRecord | None: ...

    def delete_record(self, record_id: str) -> None: ...

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def count(self) -> int: ...

    def get_collection_info(self) -> dict | None:
        """Return a dict with at least: ``status``, ``points``,
        ``vectors`` (list of named-vector names), ``named_vector_count``,
        ``sparse_vectors`` (list), ``sparse_supported`` (bool),
        ``hybrid_enabled`` (bool)."""
        ...

    @property
    def sparse_supported(self) -> bool: ...

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
        """KNN search in a named vector space.

        ``space`` is one of: ``problem``, ``solution``, ``code_context``.
        Returns hits sorted by score descending (higher = more similar).
        """
        ...

    def search_sparse(
        self,
        query_text: str,
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        """Lexical / BM25 search.

        Takes raw text — the backend owns tokenization (FTS5 for SQLite,
        :class:`BM25Tokenizer` round-trip for Actian). Returns hits sorted
        by score descending.
        """
        ...

    # ------------------------------------------------------------------
    # Browse / pagination
    # ------------------------------------------------------------------
    def scroll(
        self,
        filter: SearchFilter | None,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[ResolutionRecord], str | None]:
        """Page through records by metadata. Returns (records, next_offset).

        ``offset`` is opaque — pass back what the previous call returned
        to continue. ``None`` next_offset signals end of stream.
        """
        ...
