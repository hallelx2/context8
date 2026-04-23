"""Export and import Context8 knowledge bases."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .embeddings import EmbeddingService
from .ingest.pipeline import IngestPipeline
from .models import ResolutionRecord
from .storage import StorageService

logger = logging.getLogger("context8.export")


def export_json(storage: StorageService, output: Path) -> int:
    """Export all records to a JSON file.

    Returns the number of records exported.
    """
    from .config import COLLECTION_NAME

    records: list[dict] = []
    offset = None

    while True:
        try:
            points, next_offset = storage.client.points.scroll(
                COLLECTION_NAME,
                offset=offset,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as e:
            logger.warning(f"Scroll failed at offset {offset}: {e}")
            break

        for point in points:
            record = ResolutionRecord.from_payload(str(point.id), point.payload)
            records.append({"id": record.id, **record.to_payload()})

        if next_offset is None:
            break
        offset = next_offset

    data = {
        "version": 1,
        "format": "context8-export",
        "count": len(records),
        "records": records,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(records)


def import_json(
    storage: StorageService,
    embeddings: EmbeddingService,
    input_path: Path,
) -> int:
    """Import records from a JSON export file.

    Returns the number of records imported.
    """
    text = input_path.read_text(encoding="utf-8")
    data = json.loads(text)

    if data.get("format") != "context8-export":
        raise ValueError(f"Unknown export format: {data.get('format')}")

    records = []
    for entry in data.get("records", []):
        record_id = entry.pop("id", None)
        record = ResolutionRecord.from_payload(record_id or "", entry)
        if record_id:
            record.id = record_id
        records.append(record)

    pipeline = IngestPipeline(storage, embeddings)
    stats = pipeline.ingest(records, skip_existing=True)
    return stats.stored
