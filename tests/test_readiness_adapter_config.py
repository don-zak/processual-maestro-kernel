import json

from processual_api.readiness import check_adapter_config_integrity


def test_missing_adapter_config_is_ready(tmp_path):
    result = check_adapter_config_integrity(tmp_path / "adapter_config.json")
    assert result.ok is True
    assert result.status == "not_configured"


def test_metadata_only_adapter_config_is_ready(tmp_path):
    path = tmp_path / "adapter_config.json"
    path.write_text(
        json.dumps({"provider": "generic_openai_compatible", "model": "llama3", "base_url": "http://localhost"}),
        encoding="utf-8",
    )

    result = check_adapter_config_integrity(path)
    assert result.ok is True
    assert result.status == "metadata_only"


def test_plaintext_secret_field_degrades_readiness(tmp_path):
    path = tmp_path / "adapter_config.json"
    path.write_text(json.dumps({"provider": "openai", "api_key": "secret"}), encoding="utf-8")

    result = check_adapter_config_integrity(path)
    assert result.ok is False
    assert result.status == "plaintext_secret_field"


def test_incomplete_encrypted_envelope_degrades_readiness(tmp_path):
    path = tmp_path / "adapter_config.json"
    path.write_text(
        json.dumps({"provider": "openai", "encrypted_key": json.dumps({"algorithm": "AES-256-GCM"})}),
        encoding="utf-8",
    )

    result = check_adapter_config_integrity(path)
    assert result.ok is False
    assert result.status == "incomplete_envelope"


def test_complete_encrypted_envelope_is_ready(tmp_path):
    envelope = {
        "algorithm": "AES-256-GCM",
        "key_id": "openai",
        "nonce_b64": "bm9uY2U=",
        "aad_b64": "",
        "ciphertext_b64": "Y2lwaGVydGV4dA==",
        "plaintext_sha3_256": "a",
        "ciphertext_sha3_256": "b",
        "schema_version": 1,
        "created_at": "2026-08-30T00:00:00Z",
    }
    path = tmp_path / "adapter_config.json"
    path.write_text(json.dumps({"provider": "openai", "encrypted_key": json.dumps(envelope)}), encoding="utf-8")

    result = check_adapter_config_integrity(path)
    assert result.ok is True
    assert result.status == "encrypted"
