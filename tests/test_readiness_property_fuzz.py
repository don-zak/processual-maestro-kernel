from __future__ import annotations

import json

from hypothesis import given, strategies as st

from processual_api.readiness import check_adapter_config_integrity


FORBIDDEN = st.sampled_from(["api_key", "secret", "token", "password"])
JSON_SCALAR = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=64))


@given(field=FORBIDDEN, value=JSON_SCALAR)
def test_any_top_level_plaintext_secret_field_fails_closed(tmp_path, field, value) -> None:
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps({"provider": "test", field: value}), encoding="utf-8")

    result = check_adapter_config_integrity(path)

    assert result.ok is False
    assert result.status == "plaintext_secret_field"


@given(payload=st.one_of(st.lists(JSON_SCALAR, max_size=8), JSON_SCALAR))
def test_non_object_adapter_config_never_becomes_ready(tmp_path, payload) -> None:
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = check_adapter_config_integrity(path)

    assert result.ok is False
    assert result.status == "invalid_shape"


@given(
    missing=st.sampled_from(
        [
            "algorithm",
            "key_id",
            "nonce_b64",
            "ciphertext_b64",
            "plaintext_sha3_256",
            "ciphertext_sha3_256",
            "schema_version",
        ]
    )
)
def test_encrypted_envelope_missing_any_required_field_fails_closed(tmp_path, missing) -> None:
    envelope = {
        "algorithm": "AES-256-GCM",
        "key_id": "test",
        "nonce_b64": "bm9uY2U=",
        "ciphertext_b64": "Y2lwaGVydGV4dA==",
        "plaintext_sha3_256": "a" * 64,
        "ciphertext_sha3_256": "b" * 64,
        "schema_version": 1,
    }
    envelope.pop(missing)
    path = tmp_path / "adapter.json"
    path.write_text(
        json.dumps({"provider": "test", "encrypted_key": json.dumps(envelope)}),
        encoding="utf-8",
    )

    result = check_adapter_config_integrity(path)

    assert result.ok is False
    assert result.status == "incomplete_envelope"
