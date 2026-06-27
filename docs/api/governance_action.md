# `GovernanceAction` — Policy Decision Actions

`GovernanceAction` is a `StrEnum` that enumerates all possible actions the policy engine can take after evaluating an agent response.

## Actions

| Enum Value | Meaning | Triggered By |
|-----------|---------|-------------|
| `keep` | Accept the response | Rank `flourishing` or `stable`; policy `accept`/`accept_expand` |
| `repair` | Request a revised response | Rank `hybrid` or `transient`; policy `repair_scaffold`/`deepen_or_clarify` |
| `retry` | Regenerate from scratch | Rank `distorted`; policy `restructure` |
| `freeze_agent` | Freeze the agent (stop serving) | 5+ consecutive failures (overrides any rank-based action) |
| `escalate_to_human` | Escalate to human review | 3+ consecutive failures (overrides rank-based action unless already freeze) |
| `lower_priority` | Reduce agent priority | Action is `keep` AND `history_count >= 3` AND `avg_reward < 0.3` |
| `route_to_planner` | Route to planner for decomposition | Reserved for future use |
| `reject` | Reject the response outright | Rank `extinct`; policy `reject_regenerate` |

## Resolution Order

`PolicyEngine.decide()` applies rules in this order (later rules override earlier ones):

```
1. Rank → action (ACTION_MAP lookup)
2. Rank override: distorted → retry
3. Rank override: extinct → reject
4. Consecutive failure guard: ≥3 → escalate (if not already freeze/escalate)
5. Consecutive failure guard: ≥5 → freeze (if not already freeze)
6. Lower-priority: if action==keep AND history_count>=3 AND avg_reward<0.3 → lower_priority
```

This ensures that a failing agent gets escalated/frozen regardless of individual response rank.

## Mapping

```python
ACTION_MAP = {
    "flourishing":       GovernanceAction.keep,
    "stable":            GovernanceAction.keep,
    "hybrid":            GovernanceAction.repair,
    "distorted":         GovernanceAction.retry,       # overridden to retry
    "transient":         GovernanceAction.repair,
    "extinct":           GovernanceAction.reject,       # overridden to reject
    "accept_expand":     GovernanceAction.keep,
    "accept":            GovernanceAction.keep,
    "repair_scaffold":   GovernanceAction.repair,
    "restructure":       GovernanceAction.retry,
    "deepen_or_clarify": GovernanceAction.repair,
    "reject_regenerate": GovernanceAction.reject,
}
```

## Prometheus Counter

Every `decide()` call increments `processual_governance_actions_total{action="<value>"}` via `increment_governance_action(action)`.

## Where It's Used

| File | Usage |
|------|-------|
| `policy/engine.py:9-17` | Enum definition |
| `policy/engine.py:20-33` | `ACTION_MAP` |
| `policy/engine.py:124-139` | `decide()` — produces action |
| `cgt_governor.py:355, 1061` | `increment_governance_action(pd.action.value)` |
| `cgt_governor.py:362, 1074` | Stored in entry `"governance_action"` |
| `cgt_governor.py:385, 405, 426, 655, 1101` | Returned in response bodies |
