#!/usr/bin/env python3
"""External Pilot — 10 questions × 3 agents, final PDF report.

Prerequisites:
  - Maestro API running on MAESTRO_URL
  - Ollama running on OLLAMA_URL with MODEL available

Configuration via environment variables (with defaults):
  OLLAMA_URL=http://127.0.0.1:11434/v1/chat/completions
  MAESTRO_URL=http://127.0.0.1:8000
  API_KEY=local_test_key_123456789
  MODEL=qwen3-coder:30b
  OUTPUT_DIR=data
"""

from __future__ import annotations

import io
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/v1/chat/completions")
MAESTRO_URL = os.environ.get("MAESTRO_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("API_KEY", "local_test_key_123456789")
MODEL = os.environ.get("MODEL", "qwen3-coder:30b")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data"))
RUN_ID = f"external_pilot_{int(time.time())}"

HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

CLIENT_QUERIES = [
    "Write a practical plan to improve customer service in a telecom company. Keep it concise but useful.",
    "Explain the difference between correlation and causation in statistics, with a real-world example.",
    "Write a short product description for a smart water bottle that tracks hydration.",
    "Summarize the key principles of effective project management in under 100 words.",
    "List 5 best practices for writing secure REST API endpoints.",
    "Describe the steps to debug a memory leak in a Python web application.",
    "Compare SQL and NoSQL databases. When would you choose each?",
    "Write a short poem about artificial intelligence in the style of Robert Frost.",
    "Explain the concept of 'technical debt' to a non-technical stakeholder.",
    "What are the ethical considerations when deploying AI in healthcare?",
]

AGENT_MODES: list[dict[str, str]] = [
    {"agent_id": "pilot-planner", "name": "Pilot Planner", "role": "planner",
     "system_prompt": "You are a meticulous planner. Break down every task step by step. Provide structured, detailed plans with clear sections."},
    {"agent_id": "pilot-concise", "name": "Pilot Concise", "role": "concise",
     "system_prompt": "You are a concise assistant. Give brief, direct, and practical answers. Use bullet points where helpful."},
    {"agent_id": "pilot-critical", "name": "Pilot Critical", "role": "critical",
     "system_prompt": "You are a critical analyst. Focus on risks, gaps, and weaknesses. Provide constructive criticism."},
]


@dataclass
class PilotResult:
    agent_id: str
    name: str
    role: str
    query_idx: int
    query: str
    answer: str
    rank: str
    reward: float
    policy: str
    action: str
    agent_state: str
    latency_ms: int
    error: str | None = None


@dataclass
class AgentSummary:
    agent_id: str
    name: str
    total: int
    passed: int
    avg_reward: float
    rank_dist: dict[str, int]


def call_ollama(system_prompt: str, user_query: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def evaluate_via_gateway(agent_id: str, role: str, query: str, answer: str) -> dict[str, Any]:
    payload = {
        "agent_id": agent_id, "client_query": query, "agent_response": answer,
        "run_id": RUN_ID, "scenario_id": "pilot",
        "tags": [role, "pilot"], "repair_round": 0,
    }
    resp = requests.post(
        f"{MAESTRO_URL}/cgt/govern/gateway/evaluate",
        json=payload, headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def register_agent(agent_id: str, name: str, role: str) -> None:
    payload = {
        "agent_id": agent_id, "name": name, "role": role,
        "adapter_name": "ollama", "model": MODEL,
        "tags": [role, "pilot"], "priority": 1, "risk_level": "medium",
    }
    resp = requests.post(
        f"{MAESTRO_URL}/cgt/govern/gateway/agents",
        json=payload, headers=HEADERS, timeout=10,
    )
    if resp.status_code not in (200, 409):
        resp.raise_for_status()


def build_text_report(results: list[PilotResult], elapsed: float) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("  EXTERNAL PILOT REPORT")
    lines.append("=" * 72)
    lines.append(f"  Model:      {MODEL}")
    lines.append(f"  Questions:  {len(CLIENT_QUERIES)}")
    lines.append(f"  Agents:     {len(AGENT_MODES)}")
    lines.append(f"  Total Runs: {len(results)}")
    lines.append(f"  Duration:   {elapsed:.1f}s")
    lines.append(f"  Timestamp:  {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    lines.append("")

    for mode in AGENT_MODES:
        agent_results = [r for r in results if r.agent_id == mode["agent_id"]]
        valid = [r for r in agent_results if r.error is None]
        if not valid:
            lines.append(f"  Agent: {mode['name']} — ALL FAILED")
            continue
        avg_r = sum(v.reward for v in valid) / len(valid)
        pass_ct = sum(1 for v in valid if v.rank in ("flourishing", "stable"))
        dist: dict[str, int] = {}
        for v in valid:
            dist[v.rank] = dist.get(v.rank, 0) + 1
        lines.append(f"  Agent: {mode['name']:<20} Pass={pass_ct}/{len(valid)}  AvgReward={avg_r:.4f}")
        for rk, cnt in sorted(dist.items()):
            lines.append(f"    {rk:<20} {cnt}")
        lines.append("")

    lines.append("-" * 72)
    lines.append(f"{'#':<4} {'Agent':<22} {'Rank':<14} {'Reward':<10} {'Action':<14}")
    lines.append("-" * 72)
    for i, r in enumerate(results):
        rew = f"{r.reward:+.4f}" if r.error is None else "ERROR"
        act = r.action if r.error is None else "error"
        lines.append(f"{i:<4} {r.agent_id:<22} {r.rank:<14} {rew:<10} {act:<14}")
    lines.append("-" * 72)

    valid_all = [r for r in results if r.error is None]
    if valid_all:
        valid_all.sort(key=lambda r: r.reward, reverse=True)
        best = valid_all[0]
        lines.append(f"\n  BEST RUN: #{best.query_idx} {best.agent_id} (reward={best.reward:.4f}, rank={best.rank})")
        lines.append(f"  Query: {best.query[:80]}...")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


def build_pdf_report(results: list[PilotResult], elapsed: float) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return b""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    doc.title = "External Pilot Report"
    doc.author = "Processual Maestro Kernel v2.0.0"
    doc.subject = f"External Pilot — {len(AGENT_MODES)} agents × {len(CLIENT_QUERIES)} queries"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PilotTitle", parent=styles["Title"], fontSize=16, spaceAfter=6)
    heading_style = ParagraphStyle("PilotHeading", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    normal_style = ParagraphStyle("PilotBody", parent=styles["Normal"], fontSize=9, spaceAfter=3, leading=12)
    label_style = ParagraphStyle("PilotLabel", parent=normal_style, textColor=colors.HexColor("#555555"), fontSize=8)

    elements = []
    ts_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    elements.append(Paragraph("External Pilot Report", title_style))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph(f"Model: {MODEL} &nbsp;|&nbsp; Queries: {len(CLIENT_QUERIES)} &nbsp;|&nbsp; Agents: {len(AGENT_MODES)} &nbsp;|&nbsp; Duration: {elapsed:.1f}s &nbsp;|&nbsp; {ts_str}", label_style))
    elements.append(Spacer(1, 4*mm))

    for mode in AGENT_MODES:
        agent_results = [r for r in results if r.agent_id == mode["agent_id"]]
        valid = [r for r in agent_results if r.error is None]
        if not valid:
            continue
        avg_r = sum(v.reward for v in valid) / len(valid)
        pass_ct = sum(1 for v in valid if v.rank in ("flourishing", "stable"))
        elements.append(Paragraph(f"{mode['name']} — Pass: {pass_ct}/{len(valid)} &nbsp; Avg Reward: {avg_r:.4f}", heading_style))
        dist: dict[str, int] = {}
        for v in valid:
            dist[v.rank] = dist.get(v.rank, 0) + 1
        tbl_data = [[Paragraph("<b>Rank</b>", label_style), Paragraph("<b>Count</b>", label_style)]]
        for rk, cnt in sorted(dist.items()):
            tbl_data.append([Paragraph(rk, normal_style), str(cnt)])
        tbl = Table(tbl_data, colWidths=[80*mm, 80*mm])
        tbl.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
                                 ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f0f0f5")),
                                 ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                                 ("TOPPADDING", (0,0), (-1,-1), 2),
                                 ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
        elements.append(tbl)
        elements.append(Spacer(1, 3*mm))

    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph("Detailed Results", heading_style))
    det_data = [[Paragraph("<b>#</b>", label_style), Paragraph("<b>Agent</b>", label_style),
                 Paragraph("<b>Rank</b>", label_style), Paragraph("<b>Reward</b>", label_style)]]
    for i, r in enumerate(results):
        rew = f"{r.reward:+.4f}" if r.error is None else "ERROR"
        det_data.append([str(i), r.agent_id, r.rank if r.error is None else "ERROR", rew])
    det_tbl = Table(det_data, colWidths=[10*mm, 55*mm, 45*mm, 30*mm])
    det_tbl.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
                                 ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f0f0f5")),
                                 ("FONTSIZE", (0,0), (-1,-1), 8),
                                 ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                                 ("TOPPADDING", (0,0), (-1,-1), 2),
                                 ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
    elements.append(det_tbl)

    doc.build(elements)
    return buf.getvalue()


def main() -> None:
    print("External Pilot: 10 questions x 3 agents")
    print(f"Model: {MODEL}")
    t_start = time.monotonic()

    # Register agents
    print("Registering agents...")
    for mode in AGENT_MODES:
        try:
            register_agent(mode["agent_id"], mode["name"], mode["role"])
            print(f"  OK  {mode['agent_id']}")
        except Exception as e:
            print(f"  ERR {mode['agent_id']}: {e}")
            return

    # Run
    results: list[PilotResult] = []
    for qi, query in enumerate(CLIENT_QUERIES):
        for mode in AGENT_MODES:
            t0 = time.monotonic()
            agent_id = mode["agent_id"]
            print(f"  [{qi + 1}/{len(CLIENT_QUERIES)}] {agent_id}...", end=" ", flush=True)
            try:
                answer = call_ollama(mode["system_prompt"], query)
                decision = evaluate_via_gateway(agent_id, mode["role"], query, answer)
                lat = int((time.monotonic() - t0) * 1000)
                decision["eval_id"] = decision.get("eval_id", "")
                results.append(PilotResult(
                    agent_id=agent_id, name=mode["name"], role=mode["role"],
                    query_idx=qi, query=query, answer=answer[:200],
                    rank=decision.get("rank", "?"), reward=decision.get("reward", 0),
                    policy=decision.get("policy", ""), action=decision.get("action", ""),
                    agent_state=decision.get("agent_state", ""), latency_ms=lat,
                ))
                print(f"rank={decision.get('rank', '?')} reward={decision.get('reward', 0):.4f}")
            except Exception as e:
                lat = int((time.monotonic() - t0) * 1000)
                results.append(PilotResult(
                    agent_id=agent_id, name=mode["name"], role=mode["role"],
                    query_idx=qi, query=query, answer="", rank="ERROR", reward=0,
                    policy="", action="error", agent_state="", latency_ms=lat, error=str(e),
                ))
                print(f"ERROR: {e}")

    elapsed = time.monotonic() - t_start
    text_report = build_text_report(results, elapsed)
    pdf_bytes = build_pdf_report(results, elapsed)
    json_data = {
        "run_id": RUN_ID, "model": MODEL, "timestamp": datetime.now(UTC).isoformat(),
        "duration_s": round(elapsed, 2), "agents": len(AGENT_MODES), "queries": len(CLIENT_QUERIES),
        "results": [
            {
                "agent_id": r.agent_id, "name": r.name, "role": r.role,
                "query_idx": r.query_idx, "query": r.query, "answer": r.answer,
                "rank": r.rank, "reward": r.reward, "policy": r.policy, "action": r.action,
                "agent_state": r.agent_state, "latency_ms": r.latency_ms, "error": r.error,
            }
            for r in results
        ],
    }

    # Save reports
    out_dir = Path(__file__).resolve().parent.parent / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    txt_path = out_dir / f"pilot_report_{ts}.txt"
    txt_path.write_text(text_report, encoding="utf-8")
    print(text_report)
    print(f"\nText report: {txt_path}")

    json_path = out_dir / f"pilot_report_{ts}.json"
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON report: {json_path}")

    if pdf_bytes:
        pdf_path = out_dir / f"pilot_report_{ts}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        print(f"PDF report:  {pdf_path}")


if __name__ == "__main__":
    main()
