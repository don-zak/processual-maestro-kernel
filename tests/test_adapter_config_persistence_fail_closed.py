import json

import pytest

from processual_api.routers import cgt_governor


def test_adapter_config_does_not_persist_when_encryption_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(cgt_governor, "_ADAPTER_DATA_DIR", tmp_path)
    monkeypatch.setattr(cgt_governor, "_adapter_crypto_available", True)
    monkeypatch.setattr(cgt_governor, "_ADAPTER_CRYPTO_KEY", "configured-key")

    def fail_encrypt(*args, **kwargs):
        raise ValueError("synthetic encryption failure")

    monkeypatch.setattr(cgt_governor, "encrypt_aes256_gcm", fail_encrypt)

    with pytest.raises(RuntimeError, match="Failed to encrypt adapter credential"):
        cgt_governor._save_adapter_config("openai", "secret", "model")

    assert not (tmp_path / "adapter_config.json").exists()


def test_adapter_config_requires_crypto_for_supplied_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(cgt_governor, "_ADAPTER_DATA_DIR", tmp_path)
    monkeypatch.setattr(cgt_governor, "_adapter_crypto_available", False)
    monkeypatch.setattr(cgt_governor, "_ADAPTER_CRYPTO_KEY", "")

    with pytest.raises(RuntimeError, match="encryption is unavailable"):
        cgt_governor._save_adapter_config("openai", "secret", "model")

    assert not (tmp_path / "adapter_config.json").exists()


def test_adapter_config_without_secret_remains_supported(monkeypatch, tmp_path):
    monkeypatch.setattr(cgt_governor, "_ADAPTER_DATA_DIR", tmp_path)
    monkeypatch.setattr(cgt_governor, "_adapter_crypto_available", False)
    monkeypatch.setattr(cgt_governor, "_ADAPTER_CRYPTO_KEY", "")

    cgt_governor._save_adapter_config("generic_openai_compatible", "", "llama3", "http://localhost:11434/v1")

    payload = json.loads((tmp_path / "adapter_config.json").read_text(encoding="utf-8"))
    assert payload == {
        "provider": "generic_openai_compatible",
        "model": "llama3",
        "base_url": "http://localhost:11434/v1",
    }
