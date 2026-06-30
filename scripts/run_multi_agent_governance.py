#!/usr/bin/env python3
"""Multi-Agent Governance Experiment v1.

Registers 3 virtual agents (planner, concise, critical) with the Gateway,
sends the same client_query to Ollama (qwen3-coder:30b) with different
system prompts, evaluates each via /cgt/govern/gateway/evaluate, prints a
comparison table, and selects the best agent.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
MAESTRO_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("MAESTRO_API_KEY") or os.getenv("API_KEY") or os.getenv("X_API_KEY") or "local_test_key_123456789"
MODEL = "qwen3-coder:30b"
RUN_ID = f"multi_agent_v1_{int(time.time())}"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

AGENT_MODES: list[dict[str, str]] = [
    {
        "agent_id": "qwen3-planner",
        "name": "Qwen Planner",
        "role": "planner",
        "system_prompt": (
            "You are a meticulous planner. Break down every task step by step. "
            "Provide structured, detailed plans with clear sections, rationale, and expected outcomes."
        ),
    },
    {
        "agent_id": "qwen3-concise",
        "name": "Qwen Concise",
        "role": "concise",
        "system_prompt": (
            "You are a concise assistant. Give brief, direct, and practical answers. "
            "Use bullet points where helpful. Avoid fluff and unnecessary detail."
        ),
    },
    {
        "agent_id": "qwen3-critical",
        "name": "Qwen Critical",
        "role": "critical",
        "system_prompt": (
            "You are a critical analyst. Focus on risks, gaps, and weaknesses. "
            "Provide constructive criticism and highlight what could go wrong."
        ),
    },
]

CLIENT_QUERY = "Write a practical plan to improve customer service in a telecom company. Keep it concise but useful."


@dataclass
class AgentResult:
    agent_id: str
    name: str
    role: str
    answer: str
    rank: str
    reward: float
    policy: str
    policy_label: str
    action: str
    agent_state: str
    latency_ms: int
    error: str | None = None


def call_ollama(system_prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": CLIENT_QUERY},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def register_agent(agent_id: str, name: str, role: str) -> bool:
    payload = {
        "agent_id": agent_id,
        "name": name,
        "role": role,
        "adapter_name": "ollama",
        "model": MODEL,
        "language": "en",
        "tags": [role, "local", "ollama"],
        "priority": 1,
        "risk_level": "medium",
        "owner": "experiment",
        "policy_profile": "default",
    }
    resp = requests.post(
        f"{MAESTRO_URL}/cgt/govern/gateway/agents",
        json=payload,
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 409:
        return True
    resp.raise_for_status()
    return True


def activate_agent(agent_id: str) -> bool:
    payload = {
        "action": "activate",
        "reason": "Auto-activated for local multi-agent governance proof",
    }
    resp = requests.post(
        f"{MAESTRO_URL}/cgt/govern/gateway/agents/{agent_id}/action",
        json=payload,
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return True

def evaluate_agent(agent_id: str, role: str, answer: str) -> dict[str, Any]:
    payload = {
        "agent_id": agent_id,
        "client_query": CLIENT_QUERY,
        "agent_response": answer,
        "language": "en",
        "run_id": RUN_ID,
        "scenario_id": "customer_service",
        "tags": [role, "local", "ollama"],
        "repair_round": 0,
    }
    resp = requests.post(
        f"{MAESTRO_URL}/cgt/govern/gateway/evaluate",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    print("=" * 72)
    print("  Multi-Agent Governance Experiment v1")
    print(f"  Run ID: {RUN_ID}")
    print(f"  Model:  {MODEL}")
    print(f"  Query:  {CLIENT_QUERY[:60]}...")
    print("=" * 72)

    # Register agents
    print("\n>>> Registering agents...")
    for mode in AGENT_MODES:
        try:
            register_agent(mode["agent_id"], mode["name"], mode["role"])
            activate_agent(mode["agent_id"])
            print(f"  [OK] {mode['agent_id']} registered and activated")
        except Exception as e:
            print(f"  [FAIL] {mode['agent_id']} registration failed: {e}")
            sys.exit(1)

    # Call Ollama + Evaluate for each agent
    results: list[AgentResult] = []
    for mode in AGENT_MODES:
        print(f"\n>>> Processing {mode['agent_id']} ({mode['role']})...")
        t0 = time.monotonic()

        try:
            answer = call_ollama(mode["system_prompt"])
            ollama_latency = int((time.monotonic() - t0) * 1000)
            print(f"  Ollama response: {len(answer)} chars in {ollama_latency}ms")

            decision = evaluate_agent(mode["agent_id"], mode["role"], answer)
            total_latency = int((time.monotonic() - t0) * 1000)

            result = AgentResult(
                agent_id=mode["agent_id"],
                name=mode["name"],
                role=mode["role"],
                answer=answer[:200],
                rank=decision.get("rank", "?"),
                reward=decision.get("reward", 0.0),
                policy=decision.get("policy", ""),
                policy_label=decision.get("policy_label", ""),
                action=decision.get("action", ""),
                agent_state=decision.get("agent_state", ""),
                latency_ms=total_latency,
            )
            results.append(result)
            print(f"  Rank={result.rank} Reward={result.reward:.4f} Action={result.action}")

        except Exception as e:
            print(f"  [FAIL] Error: {e}")
            results.append(AgentResult(
                agent_id=mode["agent_id"],
                name=mode["name"],
                role=mode["role"],
                answer="",
                rank="ERROR",
                reward=0.0,
                policy="",
                policy_label="",
                action="error",
                agent_state="",
                latency_ms=0,
                error=str(e),
            ))

    # Print comparison table
    print("\n" + "=" * 72)
    print("  COMPARISON TABLE")
    print("=" * 72)
    header = f"{'Agent':<22} {'Rank':<14} {'Reward':<10} {'Policy':<24} {'Action':<12}"
    print(header)
    print("-" * 72)
    for r in results:
        reward_str = f"{r.reward:+.4f}" if r.error is None else "ERROR"
        print(f"{r.agent_id:<22} {r.rank:<14} {reward_str:<10} {r.policy:<24} {r.action:<12}")
    print("-" * 72)

    # Select best agent
    valid = [r for r in results if r.error is None and r.reward is not None]
    if valid:
        valid.sort(key=lambda r: r.reward, reverse=True)
        best = valid[0]
        print(f"\n  BEST AGENT: {best.agent_id} (reward={best.reward:.4f}, rank={best.rank})")
    else:
        print("\n  No valid results to select best agent.")

    # Summary
    print(f"\n  Total agents: {len(results)}")
    print(f"  Successful:   {len(valid)}")
    print(f"  Failed:       {len(results) - len(valid)}")
    print(f"  Run ID:       {RUN_ID}")
    print("=" * 72)

    # Save experiment results
    output = {
        "run_id": RUN_ID,
        "model": MODEL,
        "client_query": CLIENT_QUERY,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [
            {
                "agent_id": r.agent_id,
                "name": r.name,
                "role": r.role,
                "rank": r.rank,
                "reward": r.reward,
                "policy": r.policy,
                "action": r.action,
                "latency_ms": r.latency_ms,
                "error": r.error,
            }
            for r in results
        ],
        "best_agent": valid[0].agent_id if valid else None,
    }
    import pathlib

    out_dir = pathlib.Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"multi_agent_run_{RUN_ID}.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()




