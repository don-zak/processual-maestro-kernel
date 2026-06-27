# Multi-Agent Governance Experiment

`scripts/run_multi_agent_governance.py`

## Purpose

Compares multiple LLM agents on the same task using the CGT Governor's Gateway. Each agent receives the same `client_query` but with a different system prompt, and their responses are evaluated side-by-side.

## Agents

| Agent ID | Role | System Prompt Style |
|----------|------|-------------------|
| `qwen3-planner` | planner | Meticulous, step-by-step |
| `qwen3-concise` | concise | Brief, bullet-points |
| `qwen3-critical` | critical | Risk-focused, constructive criticism |

## Flow

```
CLIENT_QUERY
  → Ollama (3× system prompts)
    → 3 answers
      → POST /cgt/govern/gateway/evaluate
        → GatewayEngine.evaluate()
          → analyze_cgt() → govern_answer() → PolicyEngine.decide()
        ← decision (rank, reward, action, eval_id)
  → Comparison table
  → Best agent selected (highest reward)
  → Results saved to data/multi_agent_run_<RUN_ID>.json
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://127.0.0.1:11434/v1/chat/completions` | Ollama API endpoint |
| `MAESTRO_URL` | `http://127.0.0.1:8000` | Maestro API endpoint |
| `API_KEY` | `local_test_key_123456789` | Maestro API key |
| `MODEL` | `qwen3-coder:30b` | Ollama model |
| `CLIENT_QUERY` | `"Write a practical plan to improve customer service..."` | Task prompt |

## Registration

Each agent is registered with the Gateway before evaluation:

```python
POST /cgt/govern/gateway/agents
{
  "agent_id": "qwen3-planner",
  "name": "Qwen Planner",
  "model": "qwen3-coder:30b",
  "tags": ["planner", "local", "ollama"],
  "priority": 1,
  "risk_level": "medium",
  "policy_profile": "default"
}
```

## Output

A comparison table is printed to stdout and the full results are saved to `data/multi_agent_run_<RUN_ID>.json`.

### Sample Table

```
Agent                    Rank            Reward     Policy                    Action
------------------------------------------------------------------------
qwen3-planner            flourishing     +0.8912    keep                     keep
qwen3-critical           hybrid          +0.6543    repair_scaffold          repair
qwen3-concise            stable          +0.7231    accept                   keep
------------------------------------------------------------------------
BEST AGENT: qwen3-planner (reward=0.8912, rank=flourishing)
```

## Requirements

- Python 3.14+
- `requests` library
- Running Maestro API at `http://127.0.0.1:8000`
- Running Ollama at `http://127.0.0.1:11434`
- Required model pulled: `ollama pull qwen3-coder:30b`

## Usage

```bash
uv run python scripts/run_multi_agent_governance.py
```

## Related

- `scripts/run_external_pilot.py` — runs 10 questions × 3 agents, generates a refined pilot report
- `scripts/run_ollama_to_maestro.py` — single-agent evaluation
- `scripts/run_ollama_maestro_repair_loop.py` — single-agent with auto-repair
