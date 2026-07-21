from __future__ import annotations

from dataclasses import replace

import pytest

from processual_api.auth.passwords import PasswordHashPolicy, PasswordService


def test_passwords_use_argon2id_and_verify_without_exposing_material() -> None:
    service = PasswordService()
    password = "correct horse battery staple"

    encoded = service.hash_password(password)

    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert service.verify_password(encoded, password).valid is True
    assert service.verify_password(encoded, "wrong password").valid is False
    assert service.verify_password("not-an-argon2-hash", password).valid is False


@pytest.mark.parametrize(
    "changes",
    (
        {"time_cost": 2},
        {"memory_cost_kib": 32_768},
        {"parallelism": 0},
        {"hash_len": 16},
        {"salt_len": 8},
    ),
)
def test_password_policy_rejects_weakened_parameters(changes: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        replace(PasswordHashPolicy(), **changes)


def test_hash_from_changed_policy_is_marked_for_rehash() -> None:
    stronger = PasswordService(replace(PasswordHashPolicy(), time_cost=4))
    default = PasswordService()
    encoded = stronger.hash_password("a password that will be rehashed")

    result = default.verify_password(encoded, "a password that will be rehashed")

    assert result.valid is True
    assert result.needs_rehash is True
