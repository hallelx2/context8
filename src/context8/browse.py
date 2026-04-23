"""Tag-based and metadata browsing for Context8.

Browse records without a vector query — pure payload filtering
via Actian's FilterBuilder and scroll API.
"""

from __future__ import annotations

import logging

from .config import COLLECTION_NAME
from .models import ResolutionRecord
from .storage import StorageService, _require_actian

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
    av = _require_actian()

    conditions = []
    if tag:
        conditions.append(av.Field("tags").any_of([tag]))
    if language:
        conditions.append(av.Field("language").eq(language.lower()))
    if framework:
        conditions.append(av.Field("framework").eq(framework.lower()))
    if error_type:
        conditions.append(av.Field("error_type").eq(error_type))
    if source:
        conditions.append(av.Field("source").eq(source))

    scroll_filter = None
    if conditions:
        builder = av.FilterBuilder()
        for cond in conditions:
            builder = builder.must(cond)
        scroll_filter = builder.build()

    try:
        points, _ = storage.client.points.scroll(
            COLLECTION_NAME,
            filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as e:
        logger.warning(f"Browse scroll failed: {e}")
        return []

    return [ResolutionRecord.from_payload(str(p.id), p.payload) for p in points]
