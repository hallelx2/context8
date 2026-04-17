from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field

from ..embeddings import EmbeddingService
from ..ingest.seed import slug_to_id
from ..search import SearchEngine
from ..storage import StorageService
from .ground_truth import GROUND_TRUTH, GroundTruthQuery

logger = logging.getLogger("context8.benchmark")


@dataclass
class Configuration:
    name: str
    use_problem_vector: bool = True
    use_code_vector: bool = False
    use_sparse: bool = False
    use_filter: bool = False
    apply_quality_boost: bool = False


CONFIGURATIONS: list[Configuration] = [
    Configuration("dense (problem only)"),
    Configuration("+ named vectors (problem + code_context)", use_code_vector=True),
    Configuration(
        "+ hybrid fusion (+ sparse keywords)",
        use_code_vector=True,
        use_sparse=True,
    ),
    Configuration(
        "+ filtered search (language/framework)",
        use_code_vector=True,
        use_sparse=True,
        use_filter=True,
    ),
    Configuration(
        "+ quality ranker (confidence/recency/feedback)",
        use_code_vector=True,
        use_sparse=True,
        use_filter=True,
        apply_quality_boost=True,
    ),
]


@dataclass
class ConfigResult:
    config: Configuration
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    median_latency_ms: float
    queries_run: int
    queries_with_hit: int
    misses: list[GroundTruthQuery] = field(default_factory=list)


def _evaluate_config(
    config: Configuration,
    engine: SearchEngine,
    queries: list[GroundTruthQuery],
    k_max: int = 5,
) -> ConfigResult:
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks: list[float] = []
    latencies_ms: list[float] = []
    misses: list[GroundTruthQuery] = []

    for q in queries:
        expected_id = slug_to_id(q.expected_slug)

        t0 = time.perf_counter()
        results = engine.search(
            query=q.query,
            code_context=q.code_context,
            language=q.language if config.use_filter else None,
            framework=q.framework if config.use_filter else None,
            resolved_only=False,
            limit=k_max,
            score_threshold=0.0,
            use_problem_vector=config.use_problem_vector,
            use_code_vector=config.use_code_vector,
            use_sparse=config.use_sparse,
            use_filter=config.use_filter,
            apply_quality_boost=config.apply_quality_boost,
        )
        latencies_ms.append((time.perf_counter() - t0) * 1000)

        rank: int | None = None
        for i, r in enumerate(results, start=1):
            if r.record.id == expected_id:
                rank = i
                break

        if rank is None:
            reciprocal_ranks.append(0.0)
            misses.append(q)
        else:
            reciprocal_ranks.append(1.0 / rank)
            if rank <= 1:
                hits_at_1 += 1
            if rank <= 3:
                hits_at_3 += 1
            if rank <= 5:
                hits_at_5 += 1

    n = len(queries)
    return ConfigResult(
        config=config,
        recall_at_1=hits_at_1 / n if n else 0.0,
        recall_at_3=hits_at_3 / n if n else 0.0,
        recall_at_5=hits_at_5 / n if n else 0.0,
        mrr=sum(reciprocal_ranks) / n if n else 0.0,
        median_latency_ms=statistics.median(latencies_ms) if latencies_ms else 0.0,
        queries_run=n,
        queries_with_hit=hits_at_5,
        misses=misses,
    )


def run_benchmark(
    storage: StorageService | None = None,
    embeddings: EmbeddingService | None = None,
    queries: list[GroundTruthQuery] | None = None,
    configurations: list[Configuration] | None = None,
) -> list[ConfigResult]:
    own_storage = storage is None
    if own_storage:
        storage = StorageService()

    if embeddings is None:
        embeddings = EmbeddingService()

    if queries is None:
        queries = GROUND_TRUTH
    if configurations is None:
        configurations = CONFIGURATIONS

    engine = SearchEngine(storage, embeddings)
    embeddings.warmup()

    results: list[ConfigResult] = []
    for config in configurations:
        logger.info(f"Evaluating: {config.name}")
        results.append(_evaluate_config(config, engine, queries))

    if own_storage:
        storage.close()

    return results
