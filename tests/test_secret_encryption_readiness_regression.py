from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.routers import cgt_governor
from processual_api.routers import settings as settings_router
from processual_kernel.security import crypto

ROOT = Path(__file__).resolve().parents[1]


def _run(coro):
    return asyncio.run(coro)


def test_llm_provider_api_key_is_encrypted_when_crypto_key_available(monkeypatch, tmp_path):
    key_b64 = crypto.generate_key_b64()
    raw_secret = "sk-prod-provider-secret-do-not-store-plain"

    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_router, "_CRYPTO_KEY", key_b64)
    monkeypatch.setattr(settings_router, "_crypto_available", True)

    body = SimpleNamespace(
        provider="openai",
        api_key=raw_secret,
        model="gpt-4o-mini",
    )

    response = _run(
        settings_router.save_llm_provider(
            body,
            current_user={"sub": "secure_user"},
        )
    )

    assert response == {
        "status": "saved",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "configured": True,
    }

    settings_path = tmp_path / "settings_secure_user.json"
    raw_text = settings_path.read_text("utf-8")

    assert raw_secret not in raw_text
    assert "encrypted_key" in raw_text
    assert "ciphertext_b64" in raw_text

    stored = json.loads(raw_text)
    llm_provider = stored["llm_provider"]

    assert "api_key" not in llm_provider
    assert "encrypted_key" in llm_provider
    assert settings_router._decrypt_api_key(llm_provider["encrypted_key"]) == raw_secret


def test_llm_provider_fails_closed_when_secret_encryption_is_unavailable(monkeypatch, tmp_path):
    raw_secret = "sk-prod-provider-secret-without-crypto"

    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_router, "_CRYPTO_KEY", "")
    monkeypatch.setattr(settings_router, "_crypto_available", False)

    body = SimpleNamespace(
        provider="openai",
        api_key=raw_secret,
        model="gpt-4o-mini",
    )

    with pytest.raises(HTTPException) as exc_info:
        _run(
            settings_router.save_llm_provider(
                body,
                current_user={"sub": "fail_closed_user"},
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Provider secret encryption is unavailable"
    assert not (tmp_path / "settings_fail_closed_user.json").exists()


def test_llm_provider_fails_closed_when_encryption_raises(monkeypatch, tmp_path):
    raw_secret = "sk-prod-provider-secret-encryption-failure"

    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_router, "_CRYPTO_KEY", crypto.generate_key_b64())
    monkeypatch.setattr(settings_router, "_crypto_available", True)

    def fail_encrypt(*args, **kwargs):
        raise ValueError("simulated encryption failure")

    monkeypatch.setattr(settings_router, "encrypt_aes256_gcm", fail_encrypt)

    body = SimpleNamespace(
        provider="openai",
        api_key=raw_secret,
        model="gpt-4o-mini",
    )

    with pytest.raises(HTTPException) as exc_info:
        _run(
            settings_router.save_llm_provider(
                body,
                current_user={"sub": "encrypt_failure_user"},
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Provider secret encryption failed"
    assert not (tmp_path / "settings_encrypt_failure_user.json").exists()


def test_adapter_config_api_key_is_encrypted_when_crypto_key_available(monkeypatch, tmp_path):
    key_b64 = crypto.generate_key_b64()
    raw_secret = "sk-prod-adapter-secret-do-not-store-plain"

    monkeypatch.setattr(cgt_governor, "_ADAPTER_DATA_DIR", tmp_path)
    monkeypatch.setattr(cgt_governor, "_ADAPTER_CRYPTO_KEY", key_b64)
    monkeypatch.setattr(cgt_governor, "_adapter_crypto_available", True)

    cgt_governor._save_adapter_config(
        provider="openai",
        api_key=raw_secret,
        model="gpt-4o-mini",
        base_url="",
    )

    config_path = tmp_path / "adapter_config.json"
    raw_text = config_path.read_text("utf-8")

    assert raw_secret not in raw_text
    assert "encrypted_key" in raw_text
    assert "ciphertext_b64" in raw_text

    stored = json.loads(raw_text)

    assert stored["provider"] == "openai"
    assert stored["model"] == "gpt-4o-mini"
    assert "api_key" not in stored
    assert "encrypted_key" in stored

    envelope = json.loads(stored["encrypted_key"])
    assert envelope["key_id"] == "openai"
    assert envelope["algorithm"] == crypto.AEADAlgorithm.AES_256_GCM.value
    assert envelope["ciphertext_b64"]
    assert envelope["plaintext_sha3_256"]
    assert envelope["ciphertext_sha3_256"]


def test_adapter_config_fails_closed_when_crypto_is_unavailable(monkeypatch, tmp_path):
    raw_secret = "sk-prod-adapter-secret-without-crypto"

    monkeypatch.setattr(cgt_governor, "_ADAPTER_DATA_DIR", tmp_path)
    monkeypatch.setattr(cgt_governor, "_ADAPTER_CRYPTO_KEY", "")
    monkeypatch.setattr(cgt_governor, "_adapter_crypto_available", False)

    with pytest.raises(RuntimeError, match="Adapter credential encryption is unavailable"):
        cgt_governor._save_adapter_config(
            provider="openai",
            api_key=raw_secret,
            model="gpt-4o-mini",
            base_url="",
        )

    assert not (tmp_path / "adapter_config.json").exists()


def test_report_generation_keeps_encrypted_provider_key_decryption_path():
    source = (ROOT / "processual_api" / "routers" / "reports.py").read_text(encoding="utf-8")

    required_markers = [
        "encrypted_key",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "CryptoEnvelope",
        "decrypt_aes256_gcm",
        "_decrypt_configured_llm_key",
        'return plaintext.decode("utf-8")',
        'detail="Configured LLM credential is unavailable"',
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing encrypted report provider-key markers: {missing}"
