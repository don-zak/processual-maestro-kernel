# `client_query` — Governance Input Requirement

The `client_query` is the user's original question or instruction. It is a **required input** for CGT scoring and is passed through every governance endpoint.

## Role in Scoring

`analyze_cgt(client_query, agent_response)` uses the query to:

- Tokenize and measure **keyword overlap** between query and response
- Compute **compatibility**, **coherence**, and **structural_support** scores
- Produce the 13 CGT dimension scores used by `govern_answer()` → `PolicyEngine.decide()`

## Endpoints That Require `client_query`

| Endpoint | Field | Required |
|----------|-------|----------|
| `POST /cgt/govern` | `client_query: str` | No (default `""`, but triggers a warning) |
| `POST /cgt/govern/auto-repair` | `client_query: str` | Yes (no sensible default) |
| `POST /cgt/govern/compare-adapters` | `client_query: str` | Yes |
| `POST /cgt/govern/gateway/evaluate` | `client_query: str` | Yes |
| `POST /cgt/analyze` | `client_query: str` | No (returns warning if empty) |

## Behavior When Empty

If `client_query` is empty or `""`, the router logs:

```
client_query is empty — falling back to default scores.
Send 'client_query' for real CGT analysis.
```

Score resolution follows this priority:
1. **Explicit scores** (if provided in the request body, e.g. `compatibility`, `coherence`)
2. **Auto scores** from `analyze_cgt()` (skipped when `client_query` is empty)
3. **Fallback defaults** (all dimensions = 0.5)

If you supply explicit scores, they are used regardless of `client_query`. Without either explicit scores or `client_query`, all CGT dimensions default to 0.5 and produce degraded governance.

**Always provide a meaningful `client_query` for accurate governance.**

## Usage in Scripts

```python
# Direct API call
requests.post(f"{MAESTRO_URL}/cgt/govern", json={
    "agent_response": "...",
    "client_query": "What is the capital of France?",  # <-- required
})

# Gateway evaluation
requests.post(f"{MAESTRO_URL}/cgt/govern/gateway/evaluate", json={
    "agent_id": "my-agent",
    "client_query": "Solve this equation",
    "agent_response": "x = 42",
})
```

## Implementation

- **Pydantic field**: `cgt_governor.py:98` — `GovernRequest.client_query: str = ""`
- **Core function**: `analyzer.py:602` — `def analyze_cgt(client_query: str, ...)`
- **Warning gate**: `cgt_governor.py:252-253` — logs warning if empty
