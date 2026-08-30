#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    path = Path("processual_api/routers/settings.py")
    text = path.read_text(encoding="utf-8-sig")

    old_encrypt = '''    except Exception:\n        return None\n\n\ndef _decrypt_api_key'''
    new_encrypt = '''    except Exception as exc:\n        raise RuntimeError("Provider secret encryption failed") from exc\n\n\ndef _decrypt_api_key'''
    text = replace_once(text, old_encrypt, new_encrypt, "encrypt failure handling")

    old_call = '''    encrypted = _encrypt_api_key(body.api_key, user_id) if body.api_key else None\n    if body.api_key and not encrypted:\n        raise HTTPException(\n            status_code=503,\n            detail="Provider secret encryption is unavailable",\n        )\n'''
    new_call = '''    try:\n        encrypted = _encrypt_api_key(body.api_key, user_id) if body.api_key else None\n    except RuntimeError as exc:\n        raise HTTPException(\n            status_code=503,\n            detail="Provider secret encryption failed",\n        ) from exc\n    if body.api_key and not encrypted:\n        raise HTTPException(\n            status_code=503,\n            detail="Provider secret encryption is unavailable",\n        )\n'''
    text = replace_once(text, old_call, new_call, "legacy provider save")
    path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
