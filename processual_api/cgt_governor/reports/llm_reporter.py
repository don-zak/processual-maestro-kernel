"""LLM-powered report generator — explains CGT scores in natural language."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime

logger = logging.getLogger("maestro.llm_reporter")

_REPORT_PROMPT_TEMPLATE = """You are an expert AI governance analyst. Given the following CGT (Configurational Gravity Theory) evaluation results, write a clear professional report in {language}.  # noqa: E501

## CGT Results
- Fate Vector: {fate_vector}
- Existence Rank: {existence_rank}
- Robustness Score: {robustness}
- Sensitivity Score: {sensitivity}
- Compatibility Score: {compatibility}
- Dynamic Lift: {lift}
- Possibility Score: {possibility}
- Aftermath Score: {aftermath}

## Report Style: {style}

## Instructions
{instructions}

Write the report in a professional tone suitable for an AI governance dashboard."""

_STYLE_INSTRUCTIONS = {
    "executive_summary": "Write a brief executive summary (1-2 paragraphs). Focus on the overall health, key risks, and the most important action item. Avoid technical jargon.",  # noqa: E501
    "detailed": "Write a detailed technical analysis covering each CGT dimension. Explain what each score means, how they interact, and specific recommendations for improvement. Include both strengths and weaknesses.",  # noqa: E501
    "technical": "Write a technical report with precise analysis of each CGT metric. Include numerical interpretations, cross-dimensional correlations, and actionable remediation steps for any concerning scores.",  # noqa: E501
}


async def generate_llm_report(
    fate_vector: dict[str, float],
    existence_rank: str,
    *,
    provider: str = "",
    model: str = "",
    api_key: str = "",
    language: str = "en",
    style: str = "executive_summary",
    robustness: float | None = None,
    sensitivity: float | None = None,
    compatibility: float | None = None,
    lift: float | None = None,
    possibility: float | None = None,
    aftermath: float | None = None,
) -> dict:
    """Generate a natural-language CGT report using an LLM."""

    provider = provider.lower() if provider else "opencode"

    language_name = "English" if language == "en" else "Arabic"
    instructions = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["executive_summary"])

    prompt = _REPORT_PROMPT_TEMPLATE.format(
        language=language_name,
        fate_vector=json.dumps(fate_vector),
        existence_rank=existence_rank,
        robustness=robustness if robustness is not None else "N/A",
        sensitivity=sensitivity if sensitivity is not None else "N/A",
        compatibility=compatibility if compatibility is not None else "N/A",
        lift=lift if lift is not None else "N/A",
        possibility=possibility if possibility is not None else "N/A",
        aftermath=aftermath if aftermath is not None else "N/A",
        style=style,
        instructions=instructions,
    )

    messages = [
        {"role": "system", "content": "You are an expert AI governance analyst specializing in CGT (Configurational Gravity Theory) evaluation. Provide clear, professional analysis."},  # noqa: E501
        {"role": "user", "content": prompt},
    ]

    start = time.time()
    generated_text = ""
    model_used = model or ""
    tokens_used = {}

    try:
        if provider in ("openai", "opencode"):
            base_url = os.environ.get("OPENCODE_API_URL", "http://localhost:11434/v1") if provider == "opencode" else "https://api.openai.com/v1"  # noqa: E501
            model_used = model or (os.environ.get("OPENCODE_DEFAULT_MODEL", "llama3") if provider == "opencode" else os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o"))  # noqa: E501

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            body = {
                "model": model_used,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.3,
            }

            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(f"{base_url}/chat/completions", json=body, headers=headers)
                if res.status_code != 200:
                    return _error_result(f"OpenAI API error: HTTP {res.status_code}", provider, model_used, start)

                data = res.json()
                generated_text = data["choices"][0]["message"]["content"]
                if "usage" in data:
                    tokens_used = {
                        "prompt": data["usage"].get("prompt_tokens", 0),
                        "completion": data["usage"].get("completion_tokens", 0),
                        "total": data["usage"].get("total_tokens", 0),
                    }

        elif provider == "anthropic":
            model_used = model or os.environ.get("ANTHROPIC_DEFAULT_MODEL", "claude-3-5-haiku-latest")
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json={
                        "model": model_used,
                        "max_tokens": 2048,
                        "messages": messages,
                    },
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
                if res.status_code != 200:
                    return _error_result(f"Anthropic API error: HTTP {res.status_code}", provider, model_used, start)
                data = res.json()
                generated_text = data["content"][0]["text"]
                if "usage" in data:
                    tokens_used = {
                        "input": data["usage"].get("input_tokens", 0),
                        "output": data["usage"].get("output_tokens", 0),
                    }

        elif provider == "gemini":
            model_used = model or os.environ.get("GEMINI_DEFAULT_MODEL", "gemini-2.0-flash")
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(
                    f"https://generativelanguage.googleapis.com/v1/models/{model_used}:generateContent?key={api_key}",
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
                if res.status_code != 200:
                    return _error_result(f"Gemini API error: HTTP {res.status_code}", provider, model_used, start)
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    generated_text = " ".join(p.get("text", "") for p in parts)

        elif provider == "deepseek":
            model_used = model or os.environ.get("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat")
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    json={"model": model_used, "messages": messages, "max_tokens": 2048, "temperature": 0.3},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if res.status_code != 200:
                    return _error_result(f"DeepSeek API error: HTTP {res.status_code}", provider, model_used, start)
                data = res.json()
                generated_text = data["choices"][0]["message"]["content"]

        else:
            return _error_result(f"Unknown provider: {provider}", provider, model_used, start)

        elapsed = round((time.time() - start) * 1000, 1)

        return {
            "report": generated_text,
            "provider_used": provider,
            "model_used": model_used,
            "latency_ms": elapsed,
            "tokens_used": tokens_used if tokens_used else None,
            "generated_at": _utc_now_iso(),
        }

    except Exception as e:
        logger.exception("LLM report generation failed")
        return _error_result(str(e)[:200], provider, model_used, start)


def _error_result(error: str, provider: str, model: str, start: float) -> dict:
    return {
        "report": "",
        "provider_used": provider,
        "model_used": model or "",
        "error": error,
        "latency_ms": round((time.time() - start) * 1000, 1),
        "generated_at": _utc_now_iso(),
    }


def _utc_now_iso() -> str:
    """Return an ISO UTC timestamp without relying on system zoneinfo data."""
    return datetime.now(UTC).isoformat()
