#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    settings = Path("processual_api/routers/settings.py")
    text = settings.read_text(encoding="utf-8-sig")
    old = '''    encrypted = _encrypt_api_key(body.api_key, user_id) if body.api_key else None
    raw["llm_provider"] = {
        "configured": bool(body.api_key and body.provider),
        "provider": body.provider,
        "model": body.model,
        "last_tested": raw.get("llm_provider", {}).get("last_tested"),
    }

    if encrypted:
        raw["llm_provider"]["encrypted_key"] = encrypted

    _save_raw(user_id, raw)

    return {
        "status": "saved",
        "provider": body.provider,
        "model": body.model or "",
        "configured": bool(body.api_key and body.provider),
    }
'''
    new = '''    encrypted = _encrypt_api_key(body.api_key, user_id) if body.api_key else None
    if body.api_key and not encrypted:
        raise HTTPException(
            status_code=503,
            detail="Provider secret encryption is unavailable",
        )

    raw["llm_provider"] = {
        "configured": bool(encrypted and body.provider),
        "provider": body.provider,
        "model": body.model,
        "last_tested": raw.get("llm_provider", {}).get("last_tested"),
    }

    if encrypted:
        raw["llm_provider"]["encrypted_key"] = encrypted

    _save_raw(user_id, raw)

    return {
        "status": "saved",
        "provider": body.provider,
        "model": body.model or "",
        "configured": bool(encrypted and body.provider),
    }
'''
    text = replace_once(text, old, new, "legacy llm-provider")
    settings.write_text(text, encoding="utf-8")

    pyproject = Path("pyproject.toml")
    project_text = pyproject.read_text(encoding="utf-8")
    old_description = (
        'description = "Production-ready Processual Maestro Kernel with CGT v2, '
        'security layer, backend API, observability, and Discord monitoring."'
    )
    new_description = (
        'description = "Agentic operations and governance control plane with CGT, '
        'security, API, observability, and controlled integration surfaces."'
    )
    project_text = replace_once(
        project_text,
        old_description,
        new_description,
        "package description",
    )
    pyproject.write_text(project_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
