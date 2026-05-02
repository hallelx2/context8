"""Tag-based and metadata browsing for Context8.

Pure metadata-only filtering — no vector query involved. Goes through
:meth:`StorageService.scroll` which both backends implement
(SQLiteBackend uses an indexed ``WHERE`` + JSON1 for tags;
ActianBackend uses :class:`FilterBuilder` + the scroll API).
"""

from __future__ import annotations

import logging

from .models import ResolutionRecord
from .storage import SearchFilter, StorageService

logger = logging.getLogger("context8.browse")


def browse(
    storage: StorageService,
    tag: str | None = None,
    language: str | None = None,
    framework: str | None = None,
    error_type: str | None = None,
    source: str | None = None,
    limit: int = 20,
) -> list[ResolutionRecord]:
    """Browse records by metadata filters (no vector search)."""
    sf = SearchFilter(
        language=language,
        framework=framework,
        error_type=error_type,
        source=source,
        tags_any_of=[tag] if tag else [],
    )
    if sf.is_empty():
        sf = None

    try:
        records, _next_offset = storage.scroll(sf, limit=limit)
    except Exception as exc:
        logger.warning(f"Browse scroll failed: {exc}")
        return []
    return records
