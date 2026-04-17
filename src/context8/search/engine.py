from __future__ import annotations

import logging

from ..config import (
    COLLECTION_NAME,
    DEDUP_THRESHOLD,
    DEFAULT_CODE_WEIGHT,
    DEFAULT_DENSE_WEIGHT,
    DEFAULT_SPARSE_WEIGHT,
    SCORE_THRESHOLD,
)
from ..embeddings import EmbeddingService
from ..models import ResolutionRecord, SearchResult
from ..storage import StorageService, _require_actian
from .analyzer import QueryAnalyzer
from .attribution import AttributionTracker
from .ranking import QualityRanker

logger = logging.getLogger("context8.search")


class SearchEngine:
    def __init__(
        self,
        storage: StorageService,
        embeddings: EmbeddingService,
        ranker: QualityRanker | None = None,
        dense_weight: float = DEFAULT_DENSE_WEIGHT,
        code_weight: float = DEFAULT_CODE_WEIGHT,
        sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
    ):
        self.storage = storage
        self.embeddings = embeddings
        self.ranker = ranker or QualityRanker()
        self.dense_weight = dense_weight
        self.code_weight = code_weight
        self.sparse_weight = sparse_weight

    def search(
        self,
        query: str,
        code_context: str = "",
        language: str | None = None,
        framework: str | None = None,
        error_type: str | None = None,
        resolved_only: bool = True,
        limit: int = 5,
        score_threshold: float = SCORE_THRESHOLD,
        *,
        use_problem_vector: bool = True,
        use_code_vector: bool = True,
        use_sparse: bool = True,
        use_filter: bool = True,
        apply_quality_boost: bool = True,
    ) -> list[SearchResult]:
        av = _require_actian()
        query_vectors = self.embeddings.embed_query(query, code_context)

        search_filter = (
            self._build_filter(
                language=language,
                framework=framework,
                error_type=error_type,
                resolved_only=resolved_only,
            )
            if use_filter
            else None
        )

        weights = QueryAnalyzer.analyze(query, code_context)
        prefetch_limit = min(limit * 10, 50)
        result_lists: list[list] = []
        fusion_weights: list[float] = []
        tracker = AttributionTracker()

        if use_problem_vector:
            problem_results = self._search_named(
                "problem",
                query_vectors["problem"],
                search_filter,
                prefetch_limit,
            )
            if problem_results:
                result_lists.append(problem_results)
                fusion_weights.append(weights["dense"])
                tracker.record("problem", problem_results)

        if use_code_vector:
            code_results = self._search_named(
                "code_context",
                query_vectors["code_context"],
                search_filter,
                prefetch_limit,
                strict=False,
            )
            if code_results:
                result_lists.append(code_results)
                fusion_weights.append(weights["code"])
                tracker.record("code_context", code_results)

        if (
            use_sparse
            and self.storage.sparse_supported
            and query_vectors.get("keywords_indices")
        ):
            sparse_results = self._search_sparse(
                query_vectors["keywords_values"],
                query_vectors["keywords_indices"],
                search_filter,
                prefetch_limit,
            )
            if sparse_results:
                result_lists.append(sparse_results)
                fusion_weights.append(weights["sparse"])
                tracker.record("keywords", sparse_results)

        if not result_lists:
            return []

        if len(result_lists) == 1:
            fused = result_lists[0][:limit]
            base_match_type = tracker.strategies_used[0]
        else:
            fused = av.reciprocal_rank_fusion(
                result_lists,
                limit=limit,
                ranking_constant_k=60,
                weights=fusion_weights,
            )
            base_match_type = "hybrid"

        results: list[SearchResult] = []
        for r in fused:
            if r.score < score_threshold:
                continue
            try:
                record = ResolutionRecord.from_payload(str(r.id), r.payload)
            except Exception as e:
                logger.warning(f"Failed to parse result {r.id}: {e}")
                continue
            results.append(
                SearchResult(
                    record=record,
                    score=float(r.score),
                    raw_score=float(r.score),
                    match_type=base_match_type,
                    attribution=tracker.build_for(str(r.id)),
                )
            )

        if apply_quality_boost:
            results = self.ranker.boost(results)

        return results

    def search_by_solution(
        self,
        approach: str,
        language: str | None = None,
        limit: int = 5,
        apply_quality_boost: bool = True,
    ) -> list[SearchResult]:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        query_vec = self.embeddings.embed_text(approach)
        search_filter = self._build_filter(language=language)

        try:
            results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vec,
                using="solution",
                filter=search_filter,
                limit=limit,
                with_payload=True,
            )
        except VectorAIError as e:
            logger.warning(f"Solution vector search failed: {e}")
            return []

        out = [
            SearchResult(
                record=ResolutionRecord.from_payload(str(r.id), r.payload),
                score=float(r.score),
                raw_score=float(r.score),
                match_type="solution",
            )
            for r in results
        ]
        if apply_quality_boost:
            out = self.ranker.boost(out)
        return out

    def find_duplicate(
        self,
        problem_text: str,
        threshold: float = DEDUP_THRESHOLD,
    ) -> SearchResult | None:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        query_vec = self.embeddings.embed_text(problem_text)

        try:
            results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vec,
                using="problem",
                limit=1,
                with_payload=True,
            )
        except VectorAIError:
            results = self.storage.client.points.search(
                COLLECTION_NAME,
                vector=query_vec,
                limit=1,
                with_payload=True,
            )

        if not results:
            return None
        top = results[0]
        if top.score < threshold:
            return None
        return SearchResult(
            record=ResolutionRecord.from_payload(str(top.id), top.payload),
            score=float(top.score),
            raw_score=float(top.score),
            match_type="dense",
        )

    def _search_named(
        self,
        vector_name: str,
        vector: list[float],
        search_filter,
        limit: int,
        strict: bool = True,
    ) -> list:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        try:
            return self.storage.client.points.search(
                COLLECTION_NAME,
                vector=vector,
                using=vector_name,
                filter=search_filter,
                limit=limit,
                with_payload=True,
            )
        except VectorAIError as e:
            if strict:
                logger.warning(f"{vector_name} vector search failed: {e}")
                try:
                    return self.storage.client.points.search(
                        COLLECTION_NAME,
                        vector=vector,
                        filter=search_filter,
                        limit=limit,
                        with_payload=True,
                    )
                except VectorAIError:
                    return []
            logger.debug(f"{vector_name} vector search not available: {e}")
            return []

    def _search_sparse(
        self,
        values: list[float],
        indices: list[int],
        search_filter,
        limit: int,
    ) -> list:
        av = _require_actian()
        VectorAIError = av.exceptions.VectorAIError

        try:
            return self.storage.client.points.search(
                COLLECTION_NAME,
                vector=values,
                vector_name="keywords",
                sparse_indices=indices,
                filter=search_filter,
                limit=limit,
                with_payload=True,
            )
        except VectorAIError as e:
            logger.debug(f"Sparse search not available: {e}")
            return []

    def _build_filter(
        self,
        language: str | None = None,
        framework: str | None = None,
        error_type: str | None = None,
        resolved_only: bool = False,
    ):
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
