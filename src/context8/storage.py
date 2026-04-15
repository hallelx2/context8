"""Actian VectorAI DB storage layer for Context8."""

from __future__ import annotations

import logging
from typing import Optional

from actian_vectorai import (
    VectorAIClient,
    VectorParams,
    Distance,
    SparseVectorParams,
    PointStruct,
    SparseVector,
    HnswConfigDiff,
)
from actian_vectorai.exceptions import VectorAIError

from .config import (
    DB_URL,
    COLLECTION_NAME,
    TEXT_EMBED_DIM,
    CODE_EMBED_DIM,
)
from .models import ResolutionRecord

logger = logging.getLogger("context8.storage")


class StorageService:
    """Manages all Actian VectorAI DB operations for Context8."""

    def __init__(self, url: str = DB_URL):
        self.url = url
        self._client: Optional[VectorAIClient] = None
        self._sparse_supported: Optional[bool] = None

    @property
    def client(self) -> VectorAIClient:
        if self._client is None:
            self._client = VectorAIClient(self.url, timeout=10.0)
        return self._client

    def initialize(self) -> bool:
        """Create collection if it doesn't exist.

        Returns True if collection was created, False if it already existed.

        Attempts hybrid (dense + sparse). Falls back to dense-only
        if the server doesn't support sparse vectors.
        """
        if self.collection_exists():
            return False

        # Try hybrid first (dense + sparse)
        try:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config={
                    "problem": VectorParams(
                        size=TEXT_EMBED_DIM, distance=Distance.Cosine
                    ),
                    "solution": VectorParams(
                        size=TEXT_EMBED_DIM, distance=Distance.Cosine
                    ),
                    "code_context": VectorParams(
                        size=CODE_EMBED_DIM, distance=Distance.Cosine
                    ),
                },
                sparse_vectors_config={
                    "keywords": SparseVectorParams(),
                },
                hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
            )
            self._sparse_supported = True
            logger.info("Created hybrid collection (dense + sparse)")
            return True

        except VectorAIError as e:
            logger.warning(f"Hybrid collection failed ({e}), falling back to dense-only")

        # Fallback: dense-only
        try:
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config={
                    "problem": VectorParams(
                        size=TEXT_EMBED_DIM, distance=Distance.Cosine
                    ),
                    "solution": VectorParams(
                        size=TEXT_EMBED_DIM, distance=Distance.Cosine
                    ),
                    "code_context": VectorParams(
                        size=CODE_EMBED_DIM, distance=Distance.Cosine
                    ),
                },
                hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
            )
            self._sparse_supported = False
            logger.info("Created dense-only collection (sparse not supported)")
            return True

        except VectorAIError:
            # Last resort: single vector space
            self.client.collections.create(
                COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=TEXT_EMBED_DIM, distance=Distance.Cosine
                ),
            )
            self._sparse_supported = False
            logger.info("Created single-vector collection (named vectors not supported)")
            return True

    @property
    def sparse_supported(self) -> bool:
        """Check if the collection supports sparse vectors."""
        if self._sparse_supported is None:
            # Detect from existing collection
            try:
                info = self.client.collections.get_info(COLLECTION_NAME)
                # If collection has config, check for sparse
                self._sparse_supported = False  # Safe default
                # TODO: inspect info.config for sparse_vectors presence
            except Exception:
                self._sparse_supported = False
        return self._sparse_supported

    def collection_exists(self) -> bool:
        """Check if the Context8 collection exists."""
        try:
            return self.client.collections.exists(COLLECTION_NAME)
        except Exception:
            return False

    def drop_collection(self) -> None:
        """Delete the collection if it exists."""
        try:
            if self.collection_exists():
                self.client.collections.delete(COLLECTION_NAME)
                logger.info(f"Dropped collection '{COLLECTION_NAME}'")
        except Exception as e:
            logger.warning(f"Failed to drop collection: {e}")

    def store_record(self, record: ResolutionRecord, vectors: dict) -> str:
        """Store a resolution record with its embedding vectors.

        Args:
            record: The resolution record
            vectors: Dict from EmbeddingService.embed_record() containing:
                - problem: list[float] (384d)
                - solution: list[float] (384d)
                - code_context: list[float] (768d)
                - keywords_indices: list[int] (optional)
                - keywords_values: list[float] (optional)

        Returns:
            The record ID.
        """
        # Build vector dict based on what the collection supports
        vector_data: dict = {
            "problem": vectors["problem"],
            "solution": vectors["solution"],
            "code_context": vectors["code_context"],
        }

        # Add sparse vectors if supported
        if (
            self.sparse_supported
            and "keywords_indices" in vectors
            and vectors["keywords_indices"]
        ):
            vector_data["keywords"] = SparseVector(
                indices=vectors["keywords_indices"],
                values=vectors["keywords_values"],
            )

        point = PointStruct(
            id=record.id,
            vector=vector_data,
            payload=record.to_payload(),
        )

        try:
            self.client.points.upsert(COLLECTION_NAME, [point])
        except VectorAIError:
            # Fallback: try without sparse
            point_fallback = PointStruct(
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

    def get_record(self, record_id: str) -> Optional[ResolutionRecord]:
        """Retrieve a record by ID."""
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
        """Get total number of records."""
        try:
            return self.client.points.count(COLLECTION_NAME)
        except Exception:
            return 0

    def get_collection_info(self) -> Optional[dict]:
        """Get collection metadata."""
        try:
            info = self.client.collections.get_info(COLLECTION_NAME)
            return {
                "status": str(getattr(info, "status", "unknown")),
                "points": getattr(info, "points_count", 0),
                "vectors": ["problem", "solution", "code_context"],
            }
        except Exception:
            return None

    def delete_record(self, record_id: str) -> None:
        """Delete a record by ID."""
        try:
            self.client.points.delete_by_ids(COLLECTION_NAME, [record_id])
        except Exception as e:
            logger.warning(f"Failed to delete record {record_id}: {e}")

    def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
