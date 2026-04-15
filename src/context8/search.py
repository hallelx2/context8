"""Hybrid search engine for Context8.

Combines dense semantic search across named vectors with optional
sparse keyword search and metadata filtering, fused with RRF.
"""

from __future__ import annotations

import logging
from typing import Optional

from .config import (
    COLLECTION_NAME,
    DEFAULT_DENSE_WEIGHT,
    DEFAULT_CODE_WEIGHT,
    DEFAULT_SPARSE_WEIGHT,
    DEDUP_THRESHOLD,
    SCORE_THRESHOLD,
)
from .embeddings import EmbeddingService
from .storage import StorageService, _require_actian
from .models import ResolutionRecord, SearchResult

logger = logging.getLogger("context8.search")


class SearchEngine:
    """Multi-strategy search engine for Context8."""

    def __init__(
        self,
        storage: StorageService,
        embeddings: EmbeddingService,
        dense_weight: float = DEFAULT_DENSE_WEIGHT,
        code_weight: float = DEFAULT_CODE_WEIGHT,
        sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
    ):
        self.storage = storage
        self.embeddings = embeddings
        self.dense_weight = dense_weight
        self.code_weight = code_weight
        self.sparse_weight = sparse_weight

    def search(
        self,
        query: str,
        code_context: str = "",
        language: Optional[str] = None,
        framework: Optional[str] = None,
        error_type: Optional[str] = None,
        resolved_only: bool = True,
        limit: int = 5,
        score_threshold: float = SCORE_THRESHOLD,
    ) -> list[SearchResult]:
        """Execute hybrid search across all vector spaces."""
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        query_vectors = self.embeddings.embed_query(query, code_context)

        search_filter = self._build_filter(
            language=language,
            framework=framework,
            error_type=error_type,
            resolved_only=resolved_only,
        )

        weights = QueryAnalyzer.analyze(query, code_context)
        prefetch_limit = min(limit * 10, 50)
        result_lists = []
        fusion_weights = []

        # ── Dense search on "problem" vector ──────────────────────────────
        try:
            problem_results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vectors["problem"],
                using="problem",
                filter=search_filter,
                limit=prefetch_limit,
                with_payload=True,
            )
            if problem_results:
                result_lists.append(problem_results)
                fusion_weights.append(weights["dense"])
        except VectorAIError as e:
            logger.warning(f"Problem vector search failed: {e}")
            try:
                problem_results = self.storage.client.points.search(
                    COLLECTION_NAME,
                    vector=query_vectors["problem"],
                    filter=search_filter,
                    limit=prefetch_limit,
                    with_payload=True,
                )
                if problem_results:
                    result_lists.append(problem_results)
                    fusion_weights.append(weights["dense"])
            except VectorAIError:
                pass

        # ── Dense search on "code_context" vector ─────────────────────────
        try:
            code_results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vectors["code_context"],
                using="code_context",
                filter=search_filter,
                limit=prefetch_limit,
                with_payload=True,
            )
            if code_results:
                result_lists.append(code_results)
                fusion_weights.append(weights["code"])
        except VectorAIError as e:
            logger.debug(f"Code context search not available: {e}")

        # ── Sparse search on "keywords" ───────────────────────────────────
        if (
            self.storage.sparse_supported
            and query_vectors.get("keywords_indices")
        ):
            try:
                sparse_results = self.storage.client.points.search(
                    COLLECTION_NAME,
                    vector=query_vectors["keywords_values"],
                    vector_name="keywords",
                    sparse_indices=query_vectors["keywords_indices"],
                    filter=search_filter,
                    limit=prefetch_limit,
                    with_payload=True,
                )
                if sparse_results:
                    result_lists.append(sparse_results)
                    fusion_weights.append(weights["sparse"])
            except VectorAIError as e:
                logger.debug(f"Sparse search not available: {e}")

        if not result_lists:
            return []

        # ── Fuse results ──────────────────────────────────────────────────
        if len(result_lists) == 1:
            fused = result_lists[0][:limit]
        else:
            fused = av.reciprocal_rank_fusion(
                result_lists,
                limit=limit,
                ranking_constant_k=60,
                weights=fusion_weights,
            )

        # ── Convert to SearchResult ───────────────────────────────────────
        results = []
        for r in fused:
            if r.score < score_threshold:
                continue
            try:
                record = ResolutionRecord.from_payload(str(r.id), r.payload)
                results.append(SearchResult(
                    record=record,
                    score=r.score,
                    match_type="hybrid" if len(result_lists) > 1 else "dense",
                ))
            except Exception as e:
                logger.warning(f"Failed to parse result {r.id}: {e}")
                continue

        return results

    def search_by_problem(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Simple dense search on problem vector only."""
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        query_vec = self.embeddings.embed_text(query)
        search_filter = self._build_filter(language=language)

        try:
            results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vec,
                using="problem",
                filter=search_filter,
                limit=limit,
                with_payload=True,
            )
        except VectorAIError:
            results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vec,
                filter=search_filter,
                limit=limit,
                with_payload=True,
            )

        return [
            SearchResult(
                record=ResolutionRecord.from_payload(str(r.id), r.payload),
                score=r.score,
                match_type="dense",
            )
            for r in results
        ]

    def find_duplicate(
        self,
        problem_text: str,
        threshold: float = DEDUP_THRESHOLD,
    ) -> Optional[SearchResult]:
        """Check if a very similar problem already exists."""
        results = self.search_by_problem(problem_text, limit=1)
        if results and results[0].score >= threshold:
            return results[0]
        return None

    def _build_filter(
        self,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        error_type: Optional[str] = None,
        resolved_only: bool = False,
    ):
        """Build Actian filter from search parameters."""
        av = _require_actian()

        conditions = []
        if language:
            conditions.append(av.Field("language").eq(language.lower()))
        if framework:
            conditions.append(av.Field("framework").eq(framework.lower()))
        if error_type:
            conditions.append(av.Field("error_type").eq(error_type))
        if resolved_only:
            conditions.append(av.Field("resolved").eq(True))

        if not conditions:
            return None

        builder = av.FilterBuilder()
        for condition in conditions:
            builder = builder.must(condition)
        return builder.build()


class QueryAnalyzer:
    """Analyze queries to optimize search weights."""

    ERROR_PATTERNS = [
        "Error", "Exception", "Traceback", "FATAL", "panic",
        "error:", "ERR_", "E0", "TS2",
    ]
    CODE_PATTERNS = [
        "def ", "function ", "class ", "import ", "from ",
        "const ", "let ", "var ", "fn ", "pub ", "async ",
        "=>", "->", "::", "&&", "||",
    ]

    @classmethod
    def analyze(cls, query: str, code_context: str = "") -> dict:
        """Return recommended search weights based on query type."""
        has_error = any(p in query for p in cls.ERROR_PATTERNS)
        has_code = bool(code_context) or any(p in query for p in cls.CODE_PATTERNS)

        if has_error and has_code:
            return {"dense": 0.35, "code": 0.30, "sparse": 0.35}
        elif has_error:
            return {"dense": 0.40, "code": 0.15, "sparse": 0.45}
        elif has_code:
            return {"dense": 0.25, "code": 0.55, "sparse": 0.20}
        else:
            return {"dense": 0.60, "code": 0.15, "sparse": 0.25}
