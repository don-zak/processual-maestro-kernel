from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


# Make Windows console friendlier with UTF-8 output.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


BASE_URL = os.environ.get("MAESTRO_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.environ.get("MAESTRO_API_KEY", os.environ.get("API_KEYS", "local_test_key_123456789"))

RUN_ID = datetime.now().strftime("provider_readiness_%Y%m%d_%H%M%S")

DATA_DIR = Path("data/provider_experiments")
REPORT_DIR = Path("docs/reports/provider_experiments")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

JSON_PATH = DATA_DIR / f"{RUN_ID}.json"
MD_PATH = REPORT_DIR / f"{RUN_ID}.md"


TASKS = [
    {
        "task_id": "A_customer_service_plan",
        "language": "en",
        "client_query": (
            "Write a practical 5-step plan to improve customer service in a telecom company. "
            "Keep it concise and actionable."
        ),
        "system_prompt": "",
    },
    {
        "task_id": "B_python_code_review",
        "language": "en",
        "client_query": (
            "Review this Python function for bugs and suggest a safer version: "
            "def divide(a, b): return a / b"
        ),
        "system_prompt": "",
    },
    {
        "task_id": "C_arabic_safe_support_agent",
        "language": "ar",
        "client_query": (
            "اشرح باختصار كيف يمكن لمؤسسة صغيرة أن تستخدم وكيل ذكاء اصطناعي "
            "لمساعدة فريق الدعم دون تعريض بيانات العملاء للخطر."
        ),
        "system_prompt": "Answer in Arabic. Keep it brief and practical.",
    },
]


def request_json(method: str, path: str, body: dict | None = None, timeout: int = 240) -> tuple[bool, dict]:
    url = f"{BASE_URL}{path}"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json; charset=utf-8",
    }

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return True, {}
            return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return False, {
            "error": "http_error",
            "status": exc.code,
            "body": raw[:2000],
            "url": url,
        }
    except Exception as exc:
        return False, {
            "error": "request_error",
            "type": type(exc).__name__,
            "message": str(exc),
            "url": url,
        }


def provider_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def first_result(compare_response: dict) -> dict:
    results = compare_response.get("results") or []
    if not results:
        return {}
    return results[0] or {}


def main() -> int:
    started = datetime.now().isoformat(timespec="seconds")

    print("=== Processual Maestro Provider Readiness Scanner ===")
    print(f"Base URL: {BASE_URL}")
    print(f"Run ID:   {RUN_ID}")
    print()

    report: dict = {
        "run_id": RUN_ID,
        "started_at": started,
        "base_url": BASE_URL,
        "health": {},
        "adapters_status": {},
        "readiness_tests": [],
        "governance_tests": [],
        "summary": {},
    }

    ok, health = request_json("GET", "/health/live", timeout=20)
    report["health"] = {
        "ok": ok,
        "response": health,
    }

    if not ok:
        print("HEALTH: FAIL")
        print(json.dumps(health, ensure_ascii=False, indent=2))
        JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    print("HEALTH: OK")
    print(f"Service: {health.get('service')} / version {health.get('version')}")
    print()

    ok, status = request_json("GET", "/adapters/status", timeout=30)
    report["adapters_status"] = {
        "ok": ok,
        "response": status,
    }

    if not ok:
        print("ADAPTER STATUS: FAIL")
        print(json.dumps(status, ensure_ascii=False, indent=2))
        JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    providers = status.get("providers") or []
    configured = [p for p in providers if p.get("configured")]
    configured_keys = [provider_key(p.get("name", "")) for p in configured]

    print("ADAPTERS:")
    for p in providers:
        marker = "configured" if p.get("configured") else "not_configured"
        print(f"- {p.get('name'):10} {marker:15} model={p.get('default_model')}")
    print()

    if not configured_keys:
        print("No configured providers found.")
        JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    print("READINESS TESTS:")
    for key in configured_keys:
        body = {"provider": key}
        t0 = time.monotonic()
        ok, response = request_json("POST", "/adapters/test", body=body, timeout=60)
        elapsed = round((time.monotonic() - t0) * 1000)

        item = {
            "provider": key,
            "http_ok": ok,
            "elapsed_ms": elapsed,
            "response": response,
        }
        report["readiness_tests"].append(item)

        adapter_ok = bool(ok and response.get("ok"))
        msg = response.get("message") if isinstance(response, dict) else ""
        model = response.get("model") if isinstance(response, dict) else ""
        print(f"- {key:10} ok={adapter_ok!s:5} latency={response.get('latency_ms', elapsed)}ms model={model} message={msg}")
    print()

    print("GOVERNANCE TESTS:")
    for task in TASKS:
        for key in configured_keys:
            body = {
                "client_query": task["client_query"],
                "providers": [key],
                "system_prompt": task["system_prompt"],
                "language": task["language"],
            }

            t0 = time.monotonic()
            ok, response = request_json("POST", "/cgt/govern/compare", body=body, timeout=300)
            elapsed = round((time.monotonic() - t0) * 1000)

            result = first_result(response) if ok else {}
            item = {
                "task_id": task["task_id"],
                "provider": key,
                "http_ok": ok,
                "elapsed_ms": elapsed,
                "request": {
                    "client_query": task["client_query"],
                    "language": task["language"],
                },
                "response": response,
                "result_summary": {
                    "model": result.get("model"),
                    "latency_ms": result.get("latency_ms"),
                    "response_length": result.get("response_length"),
                    "rank": result.get("rank"),
                    "reward": result.get("reward"),
                    "policy": result.get("policy"),
                    "error": result.get("error"),
                    "scores": result.get("scores", {}),
                },
            }
            report["governance_tests"].append(item)

            rank = result.get("rank")
            reward = result.get("reward")
            policy = result.get("policy")
            error = result.get("error")
            length = result.get("response_length")
            latency = result.get("latency_ms", elapsed)

            print(
                f"- {task['task_id']:30} provider={key:10} "
                f"rank={rank} reward={reward} policy={policy} "
                f"len={length} latency={latency}ms error={error}"
            )

    accepted = 0
    failed = 0
    for item in report["governance_tests"]:
        s = item.get("result_summary", {})
        if s.get("error") is None and s.get("rank") is not None:
            accepted += 1
        else:
            failed += 1

    report["summary"] = {
        "configured_provider_count": len(configured_keys),
        "configured_providers": configured_keys,
        "governance_tests_total": len(report["governance_tests"]),
        "governance_tests_with_rank": accepted,
        "governance_tests_failed": failed,
        "json_path": str(JSON_PATH),
        "markdown_path": str(MD_PATH),
    }

    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Provider Readiness Report — {RUN_ID}",
        "",
        f"- Base URL: `{BASE_URL}`",
        f"- Started at: `{started}`",
        f"- Health: `{health.get('status')}` / `{health.get('service')}` / `{health.get('version')}`",
        f"- Configured providers: `{', '.join(configured_keys)}`",
        "",
        "## Readiness",
        "",
        "| Provider | OK | Model | Latency | Message |",
        "|---|---:|---|---:|---|",
    ]

    for item in report["readiness_tests"]:
        resp = item.get("response", {})
        md_lines.append(
            f"| {item.get('provider')} | {resp.get('ok')} | {resp.get('model')} | "
            f"{resp.get('latency_ms', item.get('elapsed_ms'))} | {resp.get('message')} |"
        )

    md_lines.extend([
        "",
        "## Governance Tests",
        "",
        "| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |",
        "|---|---|---|---|---:|---|---:|---:|---|",
    ])

    for item in report["governance_tests"]:
        s = item.get("result_summary", {})
        md_lines.append(
            f"| {item.get('task_id')} | {item.get('provider')} | {s.get('model')} | "
            f"{s.get('rank')} | {s.get('reward')} | {s.get('policy')} | "
            f"{s.get('response_length')} | {s.get('latency_ms')} | {s.get('error')} |"
        )

    md_lines.extend([
        "",
        "## Summary",
        "",
        f"- Governance tests total: `{report['summary']['governance_tests_total']}`",
        f"- Tests with rank: `{report['summary']['governance_tests_with_rank']}`",
        f"- Failed tests: `{report['summary']['governance_tests_failed']}`",
        "",
        "Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.",
        "",
    ])

    MD_PATH.write_text("\n".join(md_lines), encoding="utf-8")

    print()
    print("SAVED:")
    print(f"- JSON: {JSON_PATH}")
    print(f"- MD:   {MD_PATH}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())