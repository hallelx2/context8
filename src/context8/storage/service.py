"""Backend-resolution facade.

The rest of the codebase imports ``StorageService`` and never thinks
about which implementation it is calling. The decision is made once,
at construction time, from the ``CONTEXT8_BACKEND`` env var (default
``sqlite``).

Example::

    from context8.storage import StorageService
    storage = StorageService()       # picks backend from env
    storage.initialize()             # creates schema or collection
    storage.store_record(record, vectors)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..config import (
    BACKEND,
    CODE_EMBED_DIM,
    DB_PATH,
    DB_URL,
    TEXT_EMBED_DIM,
    USE_CODE_MODEL,
)
from .backend import ScoredHit, SearchFilter, StorageBackend  # noqa: F401

if TYPE_CHECKING:
    from ..embeddings import EmbeddingService
    from ..models import ResolutionRecord

logger = logging.getLogger("context8.storage")


def _make_backend(name: str) -> StorageBackend:
    name = (name or "sqlite").lower()
    if name == "sqlite":
        from .sqlite_backend import SQLiteBackend

        return SQLiteBackend(
            DB_PATH,
            text_dim=TEXT_EMBED_DIM,
            code_dim=CODE_EMBED_DIM,
            use_code_model=USE_CODE_MODEL,
        )
    if name == "actian":
        from .actian_backend import ActianBackend

        return ActianBackend(
            DB_URL,
            text_dim=TEXT_EMBED_DIM,
            code_dim=CODE_EMBED_DIM,
        )
    raise ValueError(f"Unknown CONTEXT8_BACKEND={name!r}. Supported: 'sqlite' (default), 'actian'.")


class StorageService:
    """Thin facade. Delegates every Protocol method to the active backend.

    Construction is cheap (no I/O). Connections are opened lazily on the
    first call that needs them (``initialize``, ``count``, ``search_*``,
    etc.), so importing this module never touches the disk or network.
    """

    def __init__(self, backend: StorageBackend | None = None, *, name: str | None = None):
        if backend is not None:
            self._backend = backend
        else:
            self._backend = _make_backend(name or BACKEND)
        self.name = name or BACKEND

    # ------------------------------------------------------------------
    # Direct backend access (escape hatch — try not to use)
    # ------------------------------------------------------------------
    @property
    def backend(self) -> StorageBackend:
        return self._backend

    def attach_embeddings(self, embeddings: EmbeddingService) -> None:
        """ActianBackend needs the embedding service for sparse tokenisation.
        SQLiteBackend ignores this. The CLI / MCP wires it up after
        constructing both services."""
        attach = getattr(self._backend, "attach_embeddings", None)
        if attach is not None:
            attach(embeddings)

    # ------------------------------------------------------------------
    # Protocol delegation — kept verbose to keep mypy / IDEs happy
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        return self._backend.initialize()

    def collection_exists(self) -> bool:
        return self._backend.collection_exists()

    def drop_collection(self) -> None:
        self._backend.drop_collection()

    def close(self) -> None:
        self._backend.close()

    def store_record(self, record: ResolutionRecord, vectors: dict) -> str:
        return self._backend.store_record(record, vectors)

    def update_payload_only(self, record: ResolutionRecord) -> str:
        return self._backend.update_payload_only(record)

    def update_record(self, record: ResolutionRecord, vectors: dict) -> str:
        return self._backend.update_record(record, vectors)

    def get_record(self, record_id: str) -> ResolutionRecord | None:
        return self._backend.get_record(record_id)

    def delete_record(self, record_id: str) -> None:
        self._backend.delete_record(record_id)

    def count(self) -> int:
        return self._backend.count()

    def get_collection_info(self) -> dict | None:
        return self._backend.get_collection_info()

    @property
    def sparse_supported(self) -> bool:
        return self._backend.sparse_supported

    def search_dense(
        self,
        space: str,
        vector: list[float],
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        return self._backend.search_dense(space, vector, filter, limit)

    def search_sparse(
        self,
        query_text: str,
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        return self._backend.search_sparse(query_text, filter, limit)

    def scroll(
        self,
        filter: SearchFilter | None,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[ResolutionRecord], str | None]:
        return self._backend.scroll(filter, limit, offset)

    # ------------------------------------------------------------------
    # Legacy access — preserved so the (still-Actian-only) bits in
    # search/engine.py / browse.py / export.py keep compiling until the
    # commit-2 refactor lifts them onto the Protocol.
    # ------------------------------------------------------------------
    @property
    def url(self) -> str:
        return getattr(self._backend, "url", "")

    @property
    def client(self) -> Any:
        client = getattr(self._backend, "client", None)
        if client is None:
            raise AttributeError(
                "StorageService.client is only available on the Actian backend. "
                "Use the search_dense/search_sparse/scroll methods instead."
            )
        return client
