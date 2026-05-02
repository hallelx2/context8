"""Reciprocal Rank Fusion — combines multiple ranked lists into one.

Replaces the Actian-specific ``av.reciprocal_rank_fusion`` we used to
call from :mod:`context8.search.engine`. Fusion is purely a function of
result *ranks* (1, 2, 3, ...), not raw scores — which means it works
identically across SQLite cosine-distance scores and Actian similarity
scores without any normalisation step.

Formula::

    score(d) = Σᵢ wᵢ × 1 / (k + rank_i(d))

with ``k=60`` as the de facto standard (originally from Cormack,
Clarke & Buettcher, 2009). Higher k flattens the curve; lower k makes
top-1 dominate. 60 is balanced and rarely needs tuning.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..storage.backend import ScoredHit


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[ScoredHit]],
    *,
    k: int = 60,
    weights: Sequence[float] | None = None,
    limit: int = 10,
) -> list[ScoredHit]:
    """Fuse N ranked result lists into one.

    Each input list is assumed to be already sorted best-first. The
    returned list carries fused scores; the original :class:`ScoredHit`
    payload (record + per-list raw score) is preserved on whichever
    instance was seen first.
    """
    if not result_lists:
        return []
    if weights is None:
        weights = [1.0] * len(result_lists)
    if len(weights) != len(result_lists):
        raise ValueError(
            f"weights length ({len(weights)}) must match result_lists ({len(result_lists)})"
        )

    fused_scores: dict[str, float] = {}
    payloads: dict[str, ScoredHit] = {}

    for weight, hits in zip(weights, result_lists):
        for rank, hit in enumerate(hits, start=1):
            fused_scores[hit.record_id] = fused_scores.get(hit.record_id, 0.0) + weight / (k + rank)
            payloads.setdefault(hit.record_id, hit)

    ordered_ids = sorted(fused_scores.items(), key=lambda kv: -kv[1])
    return [
        ScoredHit(
            record_id=rid,
            score=score,
            record=payloads[rid].record,
        )
        for rid, score in ordered_ids[:limit]
    ]
