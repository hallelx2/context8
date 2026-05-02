"""Hybrid search engine — backend-agnostic.

The engine assembles dense + sparse result lists, fuses them with RRF,
hydrates :class:`ResolutionRecord` payloads, applies the quality
re-ranker, and returns :class:`SearchResult` instances. It never
imports a vendor SDK; everything goes through the
:class:`StorageBackend` Protocol.
"""

from __future__ import annotations

import logging

from ..config import (
    DEDUP_THRESHOLD,
    DEFAULT_CODE_WEIGHT,
    DEFAULT_DENSE_WEIGHT,
    DEFAULT_SPARSE_WEIGHT,
    SCORE_THRESHOLD,
)
from ..embeddings import EmbeddingService
from ..models import ResolutionRecord, SearchResult
from ..storage import SearchFilter, StorageService
from .analyzer import QueryAnalyzer
from .attribution import AttributionTracker
from .fusion import reciprocal_rank_fusion
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
        # Actian sparse search needs the embedding service to tokenize.
        # Idempotent for SQLite (no-op).
        self.storage.attach_embeddings(embeddings)
        self.ranker = ranker or QualityRanker()
        self.dense_weight = dense_weight
        self.code_weight = code_weight
        self.sparse_weight = sparse_weight

    # ------------------------------------------------------------------
    # Main hybrid search
    # ------------------------------------------------------------------
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
        query_vectors = self.embeddings.embed_query(query, code_context)

        sf = (
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
            problem_hits = self.storage.search_dense(
                "problem", query_vectors["problem"], sf, prefetch_limit
            )
            if problem_hits:
                result_lists.append(problem_hits)
                fusion_weights.append(weights["dense"])
                tracker.record("problem", problem_hits)

        if use_code_vector:
            code_hits = self.storage.search_dense(
                "code_context", query_vectors["code_context"], sf, prefetch_limit
            )
            if code_hits:
                result_lists.append(code_hits)
                fusion_weights.append(weights["code"])
                tracker.record("code_context", code_hits)

        if use_sparse and self.storage.sparse_supported:
            sparse_query = f"{query} {code_context}".strip()
            sparse_hits = self.storage.search_sparse(sparse_query, sf, prefetch_limit)
            if sparse_hits:
                result_lists.append(sparse_hits)
                fusion_weights.append(weights["sparse"])
                tracker.record("keywords", sparse_hits)

        if not result_lists:
            return []

        if len(result_lists) == 1:
            fused = result_lists[0][:limit]
            base_match_type = tracker.strategies_used[0]
        else:
            fused = reciprocal_rank_fusion(
                result_lists,
                k=60,
                weights=fusion_weights,
                limit=limit,
            )
            base_match_type = "hybrid"

        results: list[SearchResult] = []
        for hit in fused:
            if hit.score < score_threshold:
                continue
            record = hit.record or self.storage.get_record(hit.record_id)
            if record is None:
                logger.warning(f"could not hydrate record {hit.record_id}")
                continue
            results.append(
                SearchResult(
                    record=record,
                    score=float(hit.score),
                    raw_score=float(hit.score),
                    match_type=base_match_type,
                    attribution=tracker.build_for(hit.record_id),
                )
            )

        if apply_quality_boost:
            results = self.ranker.boost(results)

        return results

    # ------------------------------------------------------------------
    # Solution-vector search (find records by *approach*)
    # ------------------------------------------------------------------
    def search_by_solution(
        self,
        approach: str,
        language: str | None = None,
        limit: int = 5,
        apply_quality_boost: bool = True,
    ) -> list[SearchResult]:
        query_vec = self.embeddings.embed_text(approach)
        sf = self._build_filter(language=language)

        hits = self.storage.search_dense("solution", query_vec, sf, limit)
        out: list[SearchResult] = []
        for hit in hits:
            record = hit.record or self.storage.get_record(hit.record_id)
            if record is None:
                continue
            out.append(
                SearchResult(
                    record=record,
                    score=float(hit.score),
                    raw_score=float(hit.score),
                    match_type="solution",
                )
            )
        if apply_quality_boost:
            out = self.ranker.boost(out)
        return out

    # ------------------------------------------------------------------
    # Dedup helpers — exposed via mcp/tools.py:_handle_log
    # ------------------------------------------------------------------
    def find_duplicate(
        self,
        problem_text: str,
        threshold: float = DEDUP_THRESHOLD,
    ) -> SearchResult | None:
        query_vec = self.embeddings.embed_text(problem_text)
        hits = self.storage.search_dense("problem", query_vec, None, 1)
        if not hits:
            return None
        top = hits[0]
        if top.score < threshold:
            return None
        record = top.record or self.storage.get_record(top.record_id)
        if record is None:
            return None
        return SearchResult(
            record=record,
            score=float(top.score),
            raw_score=float(top.score),
            match_type="dense",
        )

    def find_duplicate_or_variant(
        self,
        problem_text: str,
        solution_text: str,
        exact_threshold: float = DEDUP_THRESHOLD,
        variant_threshold: float = 0.85,
        solution_diff_threshold: float = 0.7,
    ) -> tuple[str, SearchResult | None]:
        """Same problem AND same solution → ``"duplicate"``;
        same problem but different solution → ``"variant"``;
        otherwise ``"new"``."""
        existing = self.find_duplicate(problem_text, threshold=variant_threshold)
        if existing is None:
            return "new", None

        if existing.score >= exact_threshold:
            existing_sol_vec = self.embeddings.embed_text(existing.record.solution_text)
            new_sol_vec = self.embeddings.embed_text(solution_text)

            import math

            dot = sum(a * b for a, b in zip(existing_sol_vec, new_sol_vec))
            norm_a = math.sqrt(sum(a * a for a in existing_sol_vec))
            norm_b = math.sqrt(sum(b * b for b in new_sol_vec))
            sol_sim = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

            if sol_sim >= solution_diff_threshold:
                return "duplicate", existing
            return "variant", existing

        return "new", None

    # ------------------------------------------------------------------
    # Filter construction
    # ------------------------------------------------------------------
    @staticmethod
    def _build_filter(
        language: str | None = None,
        framework: str | None = None,
        error_type: str | None = None,
        resolved_only: bool = False,
        source: str | None = None,
        tags_any_of: list[str] | None = None,
    ) -> SearchFilter | None:
        sf = SearchFilter(
            language=language,
            framework=framework,
            error_type=error_type,
            source=source,
            resolved_only=resolved_only,
            tags_any_of=tags_any_of or [],
        )
        return None if sf.is_empty() else sf


def _record_from_payload(record_id: str, payload: dict) -> ResolutionRecord:
    """Kept for callers that still need it (currently none)."""
    return ResolutionRecord.from_payload(record_id, payload)
