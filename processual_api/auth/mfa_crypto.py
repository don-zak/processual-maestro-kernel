from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
AES_256_KEY_BYTES = 32


@dataclass(frozen=True, slots=True)
class EncryptedMfaSecret:
    ciphertext: bytes
    key_version: str


class MfaSecretCipher:
    def __init__(self, *, current_key_version: str, keys: Mapping[str, bytes]) -> None:
        if not current_key_version.strip():
            raise ValueError("current_key_version must not be empty.")
        copied = dict(keys)
        if current_key_version not in copied:
            raise ValueError("The current MFA key version is unavailable.")
        for version, key in copied.items():
            if not version.strip() or not isinstance(key, bytes) or len(key) != AES_256_KEY_BYTES:
                raise ValueError("Every MFA encryption key must be a named 32-byte key.")
        self.current_key_version = current_key_version
        self._keys = MappingProxyType(copied)

    @staticmethod
    def _aad(*, user_id: str, factor_id: str) -> bytes:
        if not user_id.strip() or not factor_id.strip():
            raise ValueError("user_id and factor_id are required for MFA encryption.")
        return f"pmk-mfa-v1:{user_id}:{factor_id}".encode()

    def encrypt(self, secret: bytes, *, user_id: str, factor_id: str) -> EncryptedMfaSecret:
        if not isinstance(secret, bytes) or len(secret) < 20:
            raise ValueError("TOTP secret material must contain at least 20 bytes.")
        nonce = os.urandom(NONCE_BYTES)
        aad = self._aad(user_id=user_id, factor_id=factor_id)
        key = self._keys[self.current_key_version]
        ciphertext = nonce + AESGCM(key).encrypt(nonce, secret, aad)
        return EncryptedMfaSecret(
            ciphertext=ciphertext,
            key_version=self.current_key_version,
        )

    def decrypt(
        self,
        encrypted: EncryptedMfaSecret,
        *,
        user_id: str,
        factor_id: str,
    ) -> bytes:
        key = self._keys.get(encrypted.key_version)
        if key is None:
            raise ValueError("MFA encryption key version is unavailable.")
        if len(encrypted.ciphertext) <= NONCE_BYTES:
            raise ValueError("MFA ciphertext is truncated.")
        nonce = encrypted.ciphertext[:NONCE_BYTES]
        payload = encrypted.ciphertext[NONCE_BYTES:]
        aad = self._aad(user_id=user_id, factor_id=factor_id)
        try:
            return AESGCM(key).decrypt(nonce, payload, aad)
        except InvalidTag as exc:
            raise ValueError("MFA ciphertext authentication failed.") from exc

    def rotate(
        self,
        encrypted: EncryptedMfaSecret,
        *,
        user_id: str,
        factor_id: str,
    ) -> EncryptedMfaSecret:
        secret = self.decrypt(
            encrypted,
            user_id=user_id,
            factor_id=factor_id,
        )
        return self.encrypt(secret, user_id=user_id, factor_id=factor_id)


__all__ = ["EncryptedMfaSecret", "MfaSecretCipher"]
