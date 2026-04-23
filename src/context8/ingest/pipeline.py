from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..embeddings import EmbeddingService
from ..models import ResolutionRecord
from ..storage import StorageService

logger = logging.getLogger("context8.ingest")

DEFAULT_BATCH_SIZE = 64


@dataclass
class IngestStats:
    attempted: int = 0
    stored: int = 0
    duplicates: int = 0
    failed: int = 0
    sources: dict[str, int] = field(default_factory=dict)

    def bump(self, source: str) -> None:
        self.sources[source] = self.sources.get(source, 0) + 1


class IngestPipeline:
    def __init__(
        self,
        storage: StorageService,
        embeddings: EmbeddingService,
    ):
        self.storage = storage
        self.embeddings = embeddings

    def ingest(
        self,
        records: Iterable[ResolutionRecord],
        skip_existing: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> IngestStats:
        """Ingest records with batch embedding and batch upsert.

        Collects records into batches, embeds all texts at once via
        the model's batch encode path, then upserts the full batch
        to Actian. ~20x faster than one-at-a-time for large imports.
        """
        stats = IngestStats()
        batch: list[ResolutionRecord] = []

        for record in records:
            stats.attempted += 1

            if skip_existing and self.storage.get_record(record.id) is not None:
                stats.duplicates += 1
                continue

            batch.append(record)

            if len(batch) >= batch_size:
                self._flush_batch(batch, stats)
                batch = []

        # Flush remainder
        if batch:
            self._flush_batch(batch, stats)

        return stats

    def _flush_batch(
        self,
        batch: list[ResolutionRecord],
        stats: IngestStats,
    ) -> None:
        """Embed and store a batch of records."""
        if not batch:
            return

        try:
            # Batch embed: collect all texts, encode in one call
            problems = [r.problem_text for r in batch]
            solutions = [r.solution_text for r in batch]
            code_inputs = [r.code_snippet or r.problem_text for r in batch]
            combined = [f"{r.problem_text} {r.solution_text} {r.code_snippet}" for r in batch]

            problem_vecs = self.embeddings.text_model.encode(
                problems,
                normalize_embeddings=True,
                batch_size=len(batch),
            )
            solution_vecs = self.embeddings.text_model.encode(
                solutions,
                normalize_embeddings=True,
                batch_size=len(batch),
            )
            code_vecs = self.embeddings.code_model.encode(
                code_inputs,
                normalize_embeddings=True,
                batch_size=len(batch),
            )

            sparse_list = [self.embeddings.embed_sparse(t) for t in combined]

            for i, record in enumerate(batch):
                try:
                    vectors = {
                        "problem": problem_vecs[i].tolist(),
                        "solution": solution_vecs[i].tolist(),
                        "code_context": code_vecs[i].tolist(),
                        "keywords_indices": sparse_list[i][0],
                        "keywords_values": sparse_list[i][1],
                    }
                    self.storage.store_record(record, vectors)
                    stats.stored += 1
                    stats.bump(record.source)
                except Exception as e:
                    stats.failed += 1
                    logger.warning(f"Failed to store record {record.id}: {e}")

        except Exception as e:
            # If batch embedding itself fails, fall back to one-at-a-time
            logger.warning(f"Batch embed failed ({e}), falling back to sequential")
            for record in batch:
                try:
                    vectors = self.embeddings.embed_record(
                        problem_text=record.problem_text,
                        solution_text=record.solution_text,
                        code_snippet=record.code_snippet,
                    )
                    self.storage.store_record(record, vectors)
                    stats.stored += 1
                    stats.bump(record.source)
                except Exception as inner_e:
                    stats.failed += 1
                    logger.warning(f"Failed to ingest record {record.id}: {inner_e}")
