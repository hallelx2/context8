from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .config import (
    CODE_EMBED_DIM,
    COLLECTION_NAME,
    DB_URL,
    TEXT_EMBED_DIM,
)
from .models import ResolutionRecord

if TYPE_CHECKING:
    from actian_vectorai import VectorAIClient

logger = logging.getLogger("context8.storage")

ACTIAN_INSTALL_HINT = (
    "actian-vectorai is not installed. Install it with:\n\n"
    '  pip install "actian-vectorai @ '
    "https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/"
    'actian_vectorai-0.1.0b2-py3-none-any.whl"\n'
)


def _require_actian():
    try:
        import actian_vectorai

        return actian_vectorai
    except ImportError:
        raise ImportError(ACTIAN_INSTALL_HINT) from None


class StorageService:
    def __init__(self, url: str = DB_URL):
        self.url = url
        self._client: VectorAIClient | None = None
        self._sparse_supported: bool | None = None

    @property
    def client(self) -> VectorAIClient:
        if self._client is None:
            av = _require_actian()
            self._client = av.VectorAIClient(self.url, timeout=10.0)
            self._client.connect()
        return self._client

    def initialize(self) -> bool:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        if self.collection_exists():
            return False

        try:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config={
                    "problem": av.VectorParams(size=TEXT_EMBED_DIM, distance=av.Distance.Cosine),
                    "solution": av.VectorParams(size=TEXT_EMBED_DIM, distance=av.Distance.Cosine),
                    "code_context": av.VectorParams(
                        size=CODE_EMBED_DIM, distance=av.Distance.Cosine
                    ),
                },
                sparse_vectors_config={
                    "keywords": av.SparseVectorParams(),
                },
                hnsw_config=av.HnswConfigDiff(m=16, ef_construct=200),
            )
            self._sparse_supported = True
            logger.info("Created hybrid collection (dense + sparse)")
            return True
        except VectorAIError as e:
            logger.warning(f"Hybrid collection failed ({e}), falling back to dense-only")

        try:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config={
                    "problem": av.VectorParams(size=TEXT_EMBED_DIM, distance=av.Distance.Cosine),
                    "solution": av.VectorParams(size=TEXT_EMBED_DIM, distance=av.Distance.Cosine),
                    "code_context": av.VectorParams(
                        size=CODE_EMBED_DIM, distance=av.Distance.Cosine
                    ),
                },
                hnsw_config=av.HnswConfigDiff(m=16, ef_construct=200),
            )
            self._sparse_supported = False
            logger.info("Created dense-only collection (sparse not supported)")
            return True
        except VectorAIError:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config=av.VectorParams(size=TEXT_EMBED_DIM, distance=av.Distance.Cosine),
            )
            self._sparse_supported = False
            logger.info("Created single-vector collection (named vectors not supported)")
            return True

    @property
    def sparse_supported(self) -> bool:
        if self._sparse_supported is None:
            try:
                self.client.collections.get_info(COLLECTION_NAME)
                self._sparse_supported = False
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
                logger.info(f"Dropped collection '{COLLECTION_NAME}'")
        except Exception as e:
            logger.warning(f"Failed to drop collection: {e}")

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

        point = av.PointStruct(
            id=record.id,
            vector=vector_data,
            payload=record.to_payload(),
        )

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

    def update_record(self, record: ResolutionRecord, vectors: dict) -> str:
        try:
            self.client.points.delete_by_ids(COLLECTION_NAME, [record.id])
        except Exception as e:
            logger.debug(f"Pre-update delete had no effect: {e}")
        return self.store_record(record, vectors)

    def get_record(self, record_id: str) -> ResolutionRecord | None:
        try:
            results = self.client.points.get(
                COLLECTION_NAME,
                ids=[record_id],
                with_payload=True,
            )
            if not results:
                return None
            return ResolutionRecord.from_payload(str(results[0].id), results[0].payload)
        except Exception:
            return None

    def count(self) -> int:
        try:
            return self.client.points.count(COLLECTION_NAME)
        except Exception:
            return 0

    def get_collection_info(self) -> dict | None:
        try:
            info = self.client.collections.get_info(COLLECTION_NAME)
            named_vectors = self._discover_named_vectors(info)
            sparse_vectors = self._discover_sparse_vectors(info)
            return {
                "status": str(getattr(info, "status", "unknown")),
                "points": getattr(info, "points_count", 0),
                "vectors": named_vectors or ["problem", "solution", "code_context"],
                "named_vector_count": len(named_vectors),
                "sparse_vectors": sparse_vectors,
                "sparse_supported": bool(sparse_vectors),
                "hybrid_enabled": len(named_vectors) >= 2 and bool(sparse_vectors),
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

    def delete_record(self, record_id: str) -> None:
        try:
            self.client.points.delete_by_ids(COLLECTION_NAME, [record_id])
        except Exception as e:
            logger.warning(f"Failed to delete record {record_id}: {e}")

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
