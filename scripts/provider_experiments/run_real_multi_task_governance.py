from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_URL = "http://127.0.0.1:8000"

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

DATA_DIR = ROOT / "data" / "provider_experiments"
DOCS_DIR = ROOT / "docs" / "reports" / "provider_experiments"

PROVIDERS_TO_RUN = ["opencode", "openrouter"]

SKIPPED_PROVIDERS = {
    "openai": "BLOCKED_BY_QUOTA â€” latest governance test returned 429 insufficient_quota.",
    "gemini": "BLOCKED_BY_QUOTA â€” latest governance test returned 429 RESOURCE_EXHAUSTED / free-tier limit 0.",
    "deepseek": "BLOCKED_BY_BALANCE â€” latest governance test returned 402 Insufficient Balance.",
    "anthropic": "INVALID_API_KEY â€” latest governance test returned 401 invalid x-api-key.",
}

TASKS = [
    {
        "id": "A_governance_kernel_plan",
        "language": "en",
        "system_prompt": "Answer clearly and practically.",
        "client_query": "Write a concise plan for testing a multi-provider AI governance kernel across reliability, safety, latency, and report quality.",
    },
    {
        "id": "B_python_adapter_review",
        "language": "en",
        "system_prompt": "You are a careful Python code reviewer. Be concise and actionable.",
        "client_query": (
            "Review this pseudo-adapter design and identify risks: "
            "it reads provider keys from environment variables, calls a chat completion endpoint, "
            "then returns response_text, latency_ms, model, and error fields."
        ),
    },
    {
        "id": "C_arabic_safe_support",
        "language": "ar",
        "system_prompt": "Ø£Ø¬Ø¨ Ø¨Ø§Ù„Ø¹Ø±Ø¨ÙŠØ© Ø¨ÙˆØ¶ÙˆØ­ ÙˆØ¨Ø£Ø³Ù„ÙˆØ¨ Ø¯Ø¹Ù… Ø¢Ù…Ù† ÙˆØ¹Ù…Ù„ÙŠ.",
        "client_query": "Ø§ÙƒØªØ¨ Ø±Ø¯ Ø¯Ø¹Ù… Ù‚ØµÙŠØ± Ù„Ù…Ø³ØªØ®Ø¯Ù… ÙŠÙ‚ÙˆÙ„ Ø¥Ù† Ù…Ø²ÙˆØ¯ Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ Ù„Ø§ ÙŠØ¹Ù…Ù„ Ø±ØºÙ… Ø£Ù† Ø­Ø§Ù„ØªÙ‡ configured=true.",
    },
    {
        "id": "D_failure_classification",
        "language": "en",
        "system_prompt": "Classify failures precisely. Do not overclaim.",
        "client_query": (
            "Classify these provider failures: 429 insufficient_quota, "
            "429 RESOURCE_EXHAUSTED limit 0, 402 Insufficient Balance, "
            "401 invalid x-api-key, and local Ollama connection error."
        ),
    },
]


def load_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def request_json(method: str, url: str, api_key: str, payload: dict | None = None) -> dict:
    body = None
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(url=url, method=method, data=body, headers=headers)

    try:
        with urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "error": f"HTTPError {exc.code}: {detail}",
            "error_type": "HTTPError",
        }
    except TimeoutError as exc:
        return {
            "error": f"TimeoutError: {exc}",
            "error_type": "TimeoutError",
        }
    except URLError as exc:
        return {
            "error": f"URLError: {exc}",
            "error_type": "URLError",
        }


def summarize_result(task_id: str, provider: str, response: dict) -> dict:
    results = response.get("results") or []

    if not results:
        return {
            "task_id": task_id,
            "provider": provider,
            "ok": False,
            "rank": None,
            "reward": None,
            "policy": None,
            "response_length": 0,
            "latency_ms": None,
            "error": response.get("error") or "No provider result returned.",
        }

    item = results[0]
    return {
        "task_id": task_id,
        "provider": provider,
        "ok": item.get("error") is None,
        "rank": item.get("rank"),
        "reward": item.get("reward"),
        "policy": item.get("policy"),
        "response_length": item.get("response_length"),
        "latency_ms": item.get("latency_ms"),
        "error": item.get("error"),
        "model": item.get("model"),
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = []
    lines.append(f"# Real Multi-Task Governance Report â€” {report['run_id']}")
    lines.append("")
    lines.append(f"- Base URL: `{report['base_url']}`")
    lines.append(f"- Created at: `{report['created_at']}`")
    lines.append(f"- Providers executed: `{', '.join(report['providers_to_run'])}`")
    lines.append("")

    lines.append("## Skipped providers")
    lines.append("")
    lines.append("| Provider | Classification |")
    lines.append("|---|---|")
    for provider, reason in report["skipped_providers"].items():
        lines.append(f"| {provider} | {reason} |")
    lines.append("")

    lines.append("## Results")
    lines.append("")
    lines.append("| Task | Provider | OK | Model | Rank | Reward | Policy | Length | Latency | Error |")
    lines.append("|---|---|---:|---|---|---:|---|---:|---:|---|")

    for row in report["summary"]:
        error = row.get("error") or ""
        if len(error) > 120:
            error = error[:117] + "..."
        lines.append(
            f"| {row['task_id']} | {row['provider']} | {row['ok']} | "
            f"{row.get('model')} | {row.get('rank')} | {row.get('reward')} | "
            f"{row.get('policy')} | {row.get('response_length')} | "
            f"{row.get('latency_ms')} | {error} |"
        )

    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    ok_count = sum(1 for row in report["summary"] if row["ok"])
    total_count = len(report["summary"])
    lines.append(f"- Successful governance runs: `{ok_count}/{total_count}`.")
    lines.append("- OpenCode/Ollama is the current working baseline.")
    lines.append("- External providers remain skipped until quota, balance, or key issues are resolved.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    env = load_env(ENV_PATH)
    api_key = env.get("API_KEYS") or env.get("MAESTRO_API_KEY")

    if not api_key:
        raise SystemExit("Missing API_KEYS or MAESTRO_API_KEY in .env")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = "real_multi_task_governance_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=== Real Multi-Task Governance Runner ===")
    print(f"Base URL: {BASE_URL}")
    print(f"Run ID:   {run_id}")
    print(f"Providers executed: {', '.join(PROVIDERS_TO_RUN)}")
    print("")

    status = request_json("GET", f"{BASE_URL}/adapters/status", api_key)

    raw_results = []
    summary = []

    for task in TASKS:
        for provider in PROVIDERS_TO_RUN:
            print(f"- {task['id']} provider={provider}")

            payload = {
                "client_query": task["client_query"],
                "providers": [provider],
                "system_prompt": task["system_prompt"],
                "language": task["language"],
            }

            started = time.time()
            response = request_json("POST", f"{BASE_URL}/cgt/govern/compare", api_key, payload)
            elapsed_ms = int((time.time() - started) * 1000)

            raw_results.append({
                "task": task,
                "provider": provider,
                "elapsed_ms": elapsed_ms,
                "response": response,
            })

            row = summarize_result(task["id"], provider, response)
            summary.append(row)

            print(
                f"  ok={row['ok']} rank={row.get('rank')} "
                f"reward={row.get('reward')} policy={row.get('policy')} "
                f"len={row.get('response_length')} latency={row.get('latency_ms')} "
                f"error={row.get('error')}"
            )

    report = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": BASE_URL,
        "providers_to_run": PROVIDERS_TO_RUN,
        "skipped_providers": SKIPPED_PROVIDERS,
        "adapter_status": status,
        "tasks": TASKS,
        "summary": summary,
        "raw_results": raw_results,
    }

    json_path = DATA_DIR / f"{run_id}.json"
    md_path = DOCS_DIR / f"{run_id}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)

    print("")
    print("SAVED:")
    print(f"- JSON: {json_path.relative_to(ROOT)}")
    print(f"- MD:   {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
