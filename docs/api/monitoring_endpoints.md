# Monitoring Endpoints

Two endpoints serve the Overview dashboard and external monitoring tools.

---

## `GET /cgt/govern/metrics`

Returns aggregated governance metrics for the Overview UI. **Authentication required** (JWT or API Key).

### Response

```json
{
  "total_evaluations": 42,
  "avg_reward": 0.7314,
  "rank_distribution": {
    "flourishing": 18,
    "stable": 12,
    "hybrid": 8,
    "distorted": 3,
    "transient": 1
  },
  "psi_history": [
    { "index": 0, "reward": 0.85, "rank": "flourishing" },
    { "index": 1, "reward": 0.72, "rank": "stable" }
  ],
  "total_agents": 5,
  "active_agents": 3,
  "agent_avg_reward": 0.65,
  "action_distribution": {
    "keep": 30,
    "repair": 10,
    "retry": 2
  },
  "policy_action_count": 42
}
```

### Fields

| Field | Source | Description |
|-------|--------|-------------|
| `total_evaluations` | `eval_store` | Count of all JSONL entries (decrypted) |
| `avg_reward` | `eval_store` | Mean reward across all entries |
| `rank_distribution` | `eval_store` | Rank → count map |
| `psi_history` | `eval_store` | Last 100 evaluation rewards (for PSI chart) |
| `total_agents` | `gateway_registry` | Number of registered gateway agents |
| `active_agents` | `gateway_registry` | Agents in `ACTIVE` state |
| `agent_avg_reward` | `gateway_registry` | Mean average_reward across all agents |
| `action_distribution` | `runtime_policy_engine` | Action → count from policy engine history |
| `policy_action_count` | `runtime_policy_engine` | Total records in policy engine history |

### Consumer

The Overview dashboard (`static/js/pages/overview.js`) fetches this endpoint on load.

---

## `GET /telemetry/query`

Queries the telemetry store (generic operational metrics). **Authentication required** (JWT or API Key).

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric` | `str` | `None` | Filter by metric name (e.g., `cpu_usage`) |
| `since` | `str` (ISO 8601) | `None` | Include entries >= this timestamp |
| `limit` | `int` | `100` | Maximum number of entries to return |

### Response

```json
{
  "total": 50,
  "entries": [
    {
      "timestamp": "2026-06-01T12:00:00",
      "metric": "cpu_usage",
      "value": 45.2,
      "labels": {}
    }
  ],
  "signature": "abc123..."
}
```

### Storage Backend

Data is stored in `data/telemetry.jsonl` via `JsonlTelemetryStore`.

### Ingestion

Telemetry is posted via `POST /telemetry/ingest`:

```json
{
  "points": [
    { "metric": "cpu_usage", "value": 45.2, "labels": {} }
  ]
}
```

The ingest endpoint uses API Key authentication (`X-API-Key` header).

---

## Prometheus Metrics

Additionally, the following Prometheus counters are exposed (via `/metrics`):

| Counter | Labels | Description |
|---------|--------|-------------|
| `processual_governance_actions_total` | `action` | Total governance actions by type |
| `processual_cgt_total` | — | Total CGT evaluations |
| `processual_rank_total` | `rank` | Total evaluations by rank |
