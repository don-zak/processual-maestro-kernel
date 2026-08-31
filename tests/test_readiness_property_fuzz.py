from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, strategies as st

from processual_api.readiness import check_adapter_config_integrity


FORBIDDEN = st.sampled_from(["api_key", "secret", "token", "password"])
JSON_SCALAR = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=64))


def _check_payload(payload: object):
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "adapter.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return check_adapter_config_integrity(path)


@given(field=FORBIDDEN, value=JSON_SCALAR)
def test_any_top_level_plaintext_secret_field_fails_closed(field, value) -> None:
    result = _check_payload({"provider": "test", field: value})

    assert result.ok is False
    assert result.status == "plaintext_secret_field"


@given(payload=st.one_of(st.lists(JSON_SCALAR, max_size=8), JSON_SCALAR))
def test_non_object_adapter_config_never_becomes_ready(payload) -> None:
    result = _check_payload(payload)

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
def test_encrypted_envelope_missing_any_required_field_fails_closed(missing) -> None:
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
    result = _check_payload({"provider": "test", "encrypted_key": json.dumps(envelope)})

    assert result.ok is False
    assert result.status == "incomplete_envelope"
