from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ..adaptive_types import RiskLevel, StrategySuggestion, TaskProfile
from ..types import MaestroAction


class StrategyBandit:
    """Shadow/recommendation bandit for intervention strategies with sample-size gates.

    Rewards are segmented by a stable task-profile bucket, then backed off to a global bucket. This keeps the
    strategy memory useful for similar workflows without letting sparse or critical cases auto-apply decisions.
    """

    GLOBAL_BUCKET = "*"

    def __init__(self, min_sample_size: int = 5):
        self.min_sample_size = min_sample_size
        self._stats: dict[str, dict[MaestroAction, list[float]]] = defaultdict(lambda: defaultdict(list))

    def record(self, strategy: MaestroAction, reward: float, profile: TaskProfile | None = None) -> None:
        bucket = self._bucket(profile) if profile is not None else self.GLOBAL_BUCKET
        clipped = max(0.0, min(1.0, reward))
        self._stats[bucket][strategy].append(clipped)
        if bucket != self.GLOBAL_BUCKET:
            self._stats[self.GLOBAL_BUCKET][strategy].append(clipped)

    def suggest(self, profile: TaskProfile) -> StrategySuggestion:
        if profile.risk == RiskLevel.CRITICAL:
            return StrategySuggestion(
                strategy=MaestroAction.ESCALATE,
                confidence=0.0,
                sample_size=0,
                reason="critical workflows remain in recommend/human-gated mode",
                safe_to_apply=False,
            )
        bucket = self._bucket(profile)
        strategy, scores, source = self._best(bucket)
        if strategy is None:
            strategy, scores, source = self._best(self.GLOBAL_BUCKET)
        if strategy is None or scores is None:
            return StrategySuggestion(
                strategy=MaestroAction.OBSERVE,
                confidence=0.0,
                sample_size=0,
                reason="insufficient samples for strategy recommendation",
                safe_to_apply=False,
            )
        mean = sum(scores) / len(scores)
        reason = f"highest historical reward for {source} among sufficiently sampled strategies"
        return StrategySuggestion(
            strategy=strategy,
            confidence=round(mean, 4),
            sample_size=len(scores),
            reason=reason,
            safe_to_apply=False,
        )

    def export_json(self, path: str | Path) -> None:
        path = Path(path)
        payload = {
            bucket: {action.value: rewards for action, rewards in stats.items()}
            for bucket, stats in self._stats.items()
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_json(self, path: str | Path) -> None:
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._stats.clear()
        for bucket, stats in payload.items():
            for action_value, rewards in stats.items():
                self._stats[bucket][MaestroAction(action_value)].extend(float(x) for x in rewards)

    def _best(self, bucket: str) -> tuple[MaestroAction | None, list[float] | None, str]:
        stats = self._stats.get(bucket, {})
        eligible = [(strategy, scores) for strategy, scores in stats.items() if len(scores) >= self.min_sample_size]
        if not eligible:
            return None, None, bucket
        strategy, scores = max(eligible, key=lambda item: sum(item[1]) / len(item[1]))
        return strategy, list(scores), bucket

    @staticmethod
    def _bucket(profile: TaskProfile | None) -> str:
        if profile is None:
            return StrategyBandit.GLOBAL_BUCKET
        return "|".join((profile.size.value, profile.duration.value, profile.risk.value, profile.ambiguity.value))
