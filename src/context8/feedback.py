from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .storage import StorageService

logger = logging.getLogger("context8.feedback")


@dataclass
class FeedbackOutcome:
    record_id: str
    applied_count: int
    worked_count: int
    worked_ratio: float
    accepted: bool
    note: str = ""


class FeedbackService:
    def __init__(self, storage: StorageService):
        self.storage = storage

    def rate(
        self,
        record_id: str,
        worked: bool,
        notes: str = "",
    ) -> FeedbackOutcome:
        record = self.storage.get_record(record_id)
        if record is None:
            return FeedbackOutcome(
                record_id=record_id,
                applied_count=0,
                worked_count=0,
                worked_ratio=0.0,
                accepted=False,
                note="record not found",
            )

        record.feedback.applied_count += 1
        if worked:
            record.feedback.worked_count += 1

        record.last_seen = datetime.now(timezone.utc).isoformat()

        if notes:
            tag = "feedback:positive" if worked else "feedback:negative"
            if tag not in record.tags:
                record.tags.append(tag)

        try:
            # Payload-only update — reuses existing vectors from Actian,
            # avoids re-embedding (~40ms) when only counters/tags changed.
            self.storage.update_payload_only(record)
        except Exception as e:
            logger.warning(f"Feedback persistence failed for {record_id}: {e}")
            return FeedbackOutcome(
                record_id=record_id,
                applied_count=record.feedback.applied_count,
                worked_count=record.feedback.worked_count,
                worked_ratio=record.feedback.worked_ratio,
                accepted=False,
                note=str(e),
            )

        return FeedbackOutcome(
            record_id=record_id,
            applied_count=record.feedback.applied_count,
            worked_count=record.feedback.worked_count,
            worked_ratio=record.feedback.worked_ratio,
            accepted=True,
        )
