from __future__ import annotations

from ..models import Attribution, StrategyContribution


class AttributionTracker:
    def __init__(self) -> None:
        self._strategy_results: dict[str, list] = {}

    def record(self, strategy: str, results: list) -> None:
        self._strategy_results[strategy] = list(results)

    def build_for(self, record_id: str) -> Attribution:
        contributions: list[StrategyContribution] = []
        for strategy, results in self._strategy_results.items():
            for rank, point in enumerate(results, start=1):
                if str(point.id) == record_id:
                    contributions.append(
                        StrategyContribution(
                            strategy=strategy,
                            score=float(getattr(point, "score", 0.0)),
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
