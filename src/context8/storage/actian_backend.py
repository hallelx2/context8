"""Actian VectorAI DB storage backend (legacy, hackathon-era).

Optional — install via ``pip install context8[actian]`` and select with
``CONTEXT8_BACKEND=actian``. Preserved so the original Actian hackathon
submission can still be reproduced from this repo without a separate
branch.

The class wraps the same Actian gRPC SDK calls the original
``storage.py`` made, plus the ``search_dense`` / ``search_sparse`` /
``scroll`` methods required by the Protocol — those used to live inline
in ``search/engine.py`` / ``browse.py`` / ``export.py``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..config import COLLECTION_NAME
from ..models import ResolutionRecord
from .backend import ScoredHit, SearchFilter

if TYPE_CHECKING:
    from ..embeddings import EmbeddingService

logger = logging.getLogger("context8.storage.actian")


ACTIAN_INSTALL_HINT = (
    "actian-vectorai is not installed. Install it with:\n\n"
    "  pip install context8[actian]\n\n"
    "or directly:\n"
    '  pip install "actian-vectorai @ '
    "https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/"
    'actian_vectorai-0.1.0b2-py3-none-any.whl"\n'
)


def _require_actian():
    """Import the Actian SDK or raise a clear install error.

    Kept module-level so legacy callers (browse.py, search/engine.py
    pre-refactor) can still import it from ``context8.storage``.
    """
    try:
        import actian_vectorai

        return actian_vectorai
    except ImportError:
        raise ImportError(ACTIAN_INSTALL_HINT) from None


class ActianBackend:
    """The original gRPC-backed implementation, behind the StorageBackend
    protocol so callers can swap it for SQLite without code changes."""

    def __init__(
        self,
        url: str,
        *,
        text_dim: int,
        code_dim: int,
        embeddings: EmbeddingService | None = None,
    ):
        self.url = url
        self._text_dim = text_dim
        self._code_dim = code_dim
        # Sparse search needs the BM25 tokenizer — ActianBackend keeps a
        # reference (lazily injected by the StorageService facade).
        self._embeddings = embeddings
        self._client = None
        self._sparse_supported: bool | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            av = _require_actian()
            self._client = av.VectorAIClient(self.url, timeout=10.0)
            self._client.connect()
        return self._client

    def attach_embeddings(self, embeddings: EmbeddingService) -> None:
        """Wire in the embedding service. Required before search_sparse."""
        self._embeddings = embeddings

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        if self.collection_exists():
            return False

        try:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config={
                    "problem": av.VectorParams(size=self._text_dim, distance=av.Distance.Cosine),
                    "solution": av.VectorParams(size=self._text_dim, distance=av.Distance.Cosine),
                    "code_context": av.VectorParams(
                        size=self._code_dim, distance=av.Distance.Cosine
                    ),
                },
                sparse_vectors_config={"keywords": av.SparseVectorParams()},
                hnsw_config=av.HnswConfigDiff(m=16, ef_construct=200),
            )
            self._sparse_supported = True
            logger.info("Created hybrid Actian collection (dense + sparse)")
            return True
        except VectorAIError as exc:
            logger.warning(f"Hybrid collection failed ({exc}), falling back to dense-only")

        try:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config={
                    "problem": av.VectorParams(size=self._text_dim, distance=av.Distance.Cosine),
                    "solution": av.VectorParams(size=self._text_dim, distance=av.Distance.Cosine),
                    "code_context": av.VectorParams(
                        size=self._code_dim, distance=av.Distance.Cosine
                    ),
                },
                hnsw_config=av.HnswConfigDiff(m=16, ef_construct=200),
            )
            self._sparse_supported = False
            return True
        except VectorAIError:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config=av.VectorParams(size=self._text_dim, distance=av.Distance.Cosine),
            )
            self._sparse_supported = False
            return True

    @property
    def sparse_supported(self) -> bool:
        if self._sparse_supported is None:
            try:
                info = self.client.collections.get_info(COLLECTION_NAME)
                self._sparse_supported = bool(self._discover_sparse_vectors(info))
            except Exception:
                self._sparse_supported = False
        return self._sparse_supported

    def collection_exists(self) -> bool:
        try:
            return self.client.collections.exists(COLLECTION_NAME)
        except Exception:
            return False

    def drop_collection(self) -> None:
        try:
            if self.collection_exists():
                self.client.collections.delete(COLLECTION_NAME)
        except Exception as exc:
            logger.warning(f"Failed to drop Actian collection: {exc}")

    # ------------------------------------------------------------------
    # Record CRUD
    # ------------------------------------------------------------------
    def store_record(self, record: ResolutionRecord, vectors: dict) -> str:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        vector_data: dict = {
            "problem": vectors["problem"],
            "solution": vectors["solution"],
            "code_context": vectors["code_context"],
        }
        if self.sparse_supported and "keywords_indices" in vectors and vectors["keywords_indices"]:
            vector_data["keywords"] = av.SparseVector(
                indices=vectors["keywords_indices"],
                values=vectors["keywords_values"],
            )

        point = av.PointStruct(id=record.id, vector=vector_data, payload=record.to_payload())
        try:
            self.client.points.upsert(COLLECTION_NAME, [point])
        except VectorAIError:
            point_fallback = av.PointStruct(
                id=record.id,
                vector={
                    "problem": vectors["problem"],
                    "solution": vectors["solution"],
                    "code_context": vectors["code_context"],
                },
                payload=record.to_payload(),
            )
            self.client.points.upsert(COLLECTION_NAME, [point_fallback])
            self._sparse_supported = False
        return record.id

    def update_payload_only(self, record: ResolutionRecord) -> str:
        av = _require_actian()
        try:
            points = self.client.points.get(
                COLLECTION_NAME,
                ids=[record.id],
                with_payload=True,
                with_vectors=True,
            )
        except Exception:
            points = []

        if not points:
            logger.warning(f"update_payload_only: record {record.id} not found")
            return record.id

        existing = points[0]
        existing_vector = getattr(existing, "vector", None)
        if existing_vector:
            point = av.PointStruct(
                id=record.id, vector=existing_vector, payload=record.to_payload()
            )
            self.client.points.upsert(COLLECTION_NAME, [point])
        return record.id

    def update_record(self, record: ResolutionRecord, vectors: dict) -> str:
        try:
            self.client.points.delete_by_ids(COLLECTION_NAME, [record.id])
        except Exception as exc:
            logger.debug(f"Pre-update delete had no effect: {exc}")
        return self.store_record(record, vectors)

    def get_record(self, record_id: str) -> ResolutionRecord | None:
        try:
            results = self.client.points.get(COLLECTION_NAME, ids=[record_id], with_payload=True)
            if not results:
                return None
            return ResolutionRecord.from_payload(str(results[0].id), results[0].payload)
        except Exception:
            return None

    def delete_record(self, record_id: str) -> None:
        try:
            self.client.points.delete_by_ids(COLLECTION_NAME, [record_id])
        except Exception as exc:
            logger.warning(f"Failed to delete record {record_id}: {exc}")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def count(self) -> int:
        try:
            return self.client.points.count(COLLECTION_NAME)
        except Exception:
            return 0

    def get_collection_info(self) -> dict | None:
        try:
            info = self.client.collections.get_info(COLLECTION_NAME)
            named = self._discover_named_vectors(info)
            sparse = self._discover_sparse_vectors(info)
            return {
                "status": str(getattr(info, "status", "unknown")),
                "points": getattr(info, "points_count", 0),
                "vectors": named or ["problem", "solution", "code_context"],
                "named_vector_count": len(named),
                "sparse_vectors": sparse,
                "sparse_supported": bool(sparse),
                "hybrid_enabled": len(named) >= 2 and bool(sparse),
                "backend": "actian",
                "endpoint": self.url,
            }
        except Exception:
            return None

    @staticmethod
    def _discover_named_vectors(info) -> list[str]:
        candidates = [
            getattr(info, "vectors", None),
            getattr(getattr(info, "config", None), "vectors", None),
            getattr(getattr(info, "params", None), "vectors", None),
        ]
        for c in candidates:
            if isinstance(c, dict):
                return sorted(c.keys())
            if hasattr(c, "keys"):
                try:
                    return sorted(list(c.keys()))
                except Exception:
                    continue
        return []

    @staticmethod
    def _discover_sparse_vectors(info) -> list[str]:
        candidates = [
            getattr(info, "sparse_vectors", None),
            getattr(getattr(info, "config", None), "sparse_vectors", None),
            getattr(getattr(info, "params", None), "sparse_vectors", None),
        ]
        for c in candidates:
            if isinstance(c, dict):
                return sorted(c.keys())
            if hasattr(c, "keys"):
                try:
                    return sorted(list(c.keys()))
                except Exception:
                    continue
        return []

    # ------------------------------------------------------------------
    # Search primitives (lifted from search/engine.py)
    # ------------------------------------------------------------------
    def search_dense(
        self,
        space: str,
        vector: list[float],
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError
        av_filter = self._build_av_filter(filter)
        try:
            results = self.client.points.search(
                COLLECTION_NAME,
                vector=vector,
                using=space,
                filter=av_filter,
                limit=limit,
                with_payload=True,
            )
        except VectorAIError as exc:
            logger.debug(f"{space} dense search not available: {exc}")
            return []
        hits: list[ScoredHit] = []
        for r in results:
            try:
                record = ResolutionRecord.from_payload(str(r.id), r.payload)
            except Exception:
                record = None
            hits.append(ScoredHit(record_id=str(r.id), score=float(r.score), record=record))
        return hits

    def search_sparse(
        self,
        query_text: str,
        filter: SearchFilter | None,
        limit: int,
    ) -> list[ScoredHit]:
        if self._embeddings is None:
            logger.warning("ActianBackend.search_sparse: no EmbeddingService attached")
            return []
        if not self.sparse_supported:
            return []

        indices, values = self._embeddings.embed_sparse(query_text)
        if not indices:
            return []

        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError
        av_filter = self._build_av_filter(filter)
        try:
            results = self.client.points.search(
                COLLECTION_NAME,
                vector=values,
                using="keywords",
                sparse_indices=indices,
                filter=av_filter,
                limit=limit,
                with_payload=True,
            )
        except VectorAIError as exc:
            logger.debug(f"sparse search not available: {exc}")
            return []
        hits: list[ScoredHit] = []
        for r in results:
            try:
                record = ResolutionRecord.from_payload(str(r.id), r.payload)
            except Exception:
                record = None
            hits.append(ScoredHit(record_id=str(r.id), score=float(r.score), record=record))
        return hits

    def scroll(
        self,
        filter: SearchFilter | None,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[ResolutionRecord], str | None]:
        av_filter = self._build_av_filter(filter)
        try:
            points, next_offset = self.client.points.scroll(
                COLLECTION_NAME,
                offset=offset,
                filter=av_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.warning(f"scroll failed at offset {offset!r}: {exc}")
            return [], None
        records = [ResolutionRecord.from_payload(str(p.id), p.payload) for p in points]
        next_str = str(next_offset) if next_offset is not None else None
        return records, next_str

    # ------------------------------------------------------------------
    # Filter translation
    # ------------------------------------------------------------------
    def _build_av_filter(self, sf: SearchFilter | None):
        if sf is None or sf.is_empty():
            return None
        av = _require_actian()
        conditions = []
        if sf.language:
            conditions.append(av.Field("language").eq(sf.language.lower()))
        if sf.framework:
            conditions.append(av.Field("framework").eq(sf.framework.lower()))
        if sf.error_type:
            conditions.append(av.Field("error_type").eq(sf.error_type))
        if sf.source:
            conditions.append(av.Field("source").eq(sf.source))
        if sf.resolved_only:
            conditions.append(av.Field("resolved").eq(True))
        if sf.tags_any_of:
            conditions.append(av.Field("tags").any_of(sf.tags_any_of))
        if not conditions:
            return None
        builder = av.FilterBuilder()
        for c in conditions:
            builder = builder.must(c)
        return builder.build()
