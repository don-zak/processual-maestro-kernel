# `ContextMetadata` — Evaluation Context

`ContextMetadata` is an optional Pydantic model that attaches provenance metadata to each governance evaluation entry. It ships as a field on `GovernRequest` and is unpacked into the stored evaluation record.

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `str` | `""` | Experiment or batch run identifier |
| `agent_id` | `str` | `""` | Logical agent name (e.g., `qwen3-planner`) |
| `model` | `str` | `""` | LLM model name (e.g., `qwen3-coder:30b`) |
| `provider` | `str` | `""` | Provider or adapter (e.g., `ollama`, `openai`) |
| `scenario_id` | `str` | `""` | Scenario or test case identifier |
| `dataset_id` | `str` | `""` | Dataset identifier when running benchmarks |
| `tags` | `list[str]` | `[]` | Arbitrary tags for filtering (e.g., `["planner", "local"]`) |
| `environment` | `str` | `""` | Deployment context (e.g., `dev`, `staging`, `production`) |
| `policy_version` | `str` | `""` | Policy engine version used |
| `repair_round` | `int` | `0` | Repair iteration number (auto-repair loop) |
| `parent_eval_id` | `str` | `""` | Links child evaluations back to a parent evaluation |
| `created_by` | `str` | `""` | User or automation that triggered the evaluation |

## How It Flows

```
GovernRequest.context (optional)
  → _evaluate_and_record(context=req.context)
    → entry["run_id"] = context.run_id
    → entry["agent_id"] = context.agent_id
    → ... all fields unpacked into the stored JSONL entry
    → entry["eval_id"] = _generate_eval_id()
    → stored in data/governance_runs.jsonl
```

## Usage in HTTP

```json
POST /cgt/govern
{
  "agent_response": "...",
  "client_query": "...",
  "context": {
    "run_id": "exp_001",
    "agent_id": "planner-v2",
    "model": "qwen3-coder:30b",
    "provider": "ollama",
    "scenario_id": "customer_service",
    "tags": ["planner", "local", "v2"],
    "environment": "staging",
    "policy_version": "2.0.0",
    "repair_round": 0,
    "parent_eval_id": "eval_20240601_120000_abc123"
  }
}
```

## Parent-Child Linking

`parent_eval_id` enables traceability across auto-repair iterations. Each repair round produces a child evaluation with `parent_eval_id` set to the original evaluation's `eval_id`, forming a repair chain.

## Definition

**File**: `cgt_governor.py:81-93`

```python
class ContextMetadata(BaseModel):
    run_id: str = ""
    agent_id: str = ""
    model: str = ""
    provider: str = ""
    scenario_id: str = ""
    dataset_id: str = ""
    tags: list[str] = []
    environment: str = ""
    policy_version: str = ""
    repair_round: int = 0
    parent_eval_id: str = ""
    created_by: str = ""
```
