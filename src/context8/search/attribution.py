from __future__ import annotations

from ..models import Attribution, StrategyContribution


def _hit_id(hit) -> str:
    """Extract the record id from any hit shape.

    Tolerates both the new :class:`ScoredHit` (``record_id`` attr) and
    the older Actian point shape (``id`` attr) so the tracker stays
    backend-agnostic.
    """
    rid = getattr(hit, "record_id", None)
    if rid is not None:
        return str(rid)
    return str(getattr(hit, "id", ""))


class AttributionTracker:
    def __init__(self) -> None:
        self._strategy_results: dict[str, list] = {}

    def record(self, strategy: str, results: list) -> None:
        self._strategy_results[strategy] = list(results)

    def build_for(self, record_id: str) -> Attribution:
        contributions: list[StrategyContribution] = []
        for strategy, results in self._strategy_results.items():
            for rank, hit in enumerate(results, start=1):
                if _hit_id(hit) == record_id:
                    contributions.append(
                        StrategyContribution(
                            strategy=strategy,
                            score=float(getattr(hit, "score", 0.0)),
                            rank=rank,
                        )
                    )
                    break
        return Attribution(
            contributions=contributions,
            fused=len(self._strategy_results) > 1,
        )

    @property
    def strategies_used(self) -> list[str]:
        return list(self._strategy_results.keys())
