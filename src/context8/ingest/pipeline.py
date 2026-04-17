from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..embeddings import EmbeddingService
from ..models import ResolutionRecord
from ..storage import StorageService

logger = logging.getLogger("context8.ingest")


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
    ) -> IngestStats:
        stats = IngestStats()

        for record in records:
            stats.attempted += 1

            if skip_existing and self.storage.get_record(record.id) is not None:
                stats.duplicates += 1
                continue

            try:
                vectors = self.embeddings.embed_record(
                    problem_text=record.problem_text,
                    solution_text=record.solution_text,
                    code_snippet=record.code_snippet,
                )
                self.storage.store_record(record, vectors)
                stats.stored += 1
                stats.bump(record.source)
            except Exception as e:
                stats.failed += 1
                logger.warning(f"Failed to ingest record {record.id}: {e}")

        return stats
