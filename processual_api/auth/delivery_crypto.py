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
class EncryptedDeliveryPayload:
    ciphertext: bytes
    key_version: str


class DeliveryPayloadCipher:
    def __init__(self, *, current_key_version: str, keys: Mapping[str, bytes]) -> None:
        if not current_key_version.strip():
            raise ValueError("current_key_version must not be empty.")
        copied = dict(keys)
        if current_key_version not in copied:
            raise ValueError("The current delivery key version is unavailable.")
        for version, key in copied.items():
            if not version.strip() or not isinstance(key, bytes) or len(key) != AES_256_KEY_BYTES:
                raise ValueError("Every delivery encryption key must be a named 32-byte key.")
        self.current_key_version = current_key_version
        self._keys = MappingProxyType(copied)

    @staticmethod
    def _aad(
        *,
        outbox_id: str,
        user_id: str,
        action_token_id: str,
        purpose: str,
    ) -> bytes:
        values = (outbox_id, user_id, action_token_id, purpose)
        if any(not value.strip() for value in values):
            raise ValueError("Delivery encryption authority identifiers are required.")
        return (f"pmk-auth-delivery-v1:{outbox_id}:{user_id}:{action_token_id}:{purpose}").encode()

    def encrypt(
        self,
        raw_action_token: str,
        *,
        outbox_id: str,
        user_id: str,
        action_token_id: str,
        purpose: str,
    ) -> EncryptedDeliveryPayload:
        if not isinstance(raw_action_token, str) or not raw_action_token:
            raise ValueError("raw_action_token must be a non-empty string.")
        nonce = os.urandom(NONCE_BYTES)
        aad = self._aad(
            outbox_id=outbox_id,
            user_id=user_id,
            action_token_id=action_token_id,
            purpose=purpose,
        )
        key = self._keys[self.current_key_version]
        ciphertext = nonce + AESGCM(key).encrypt(nonce, raw_action_token.encode(), aad)
        return EncryptedDeliveryPayload(
            ciphertext=ciphertext,
            key_version=self.current_key_version,
        )

    def decrypt(
        self,
        encrypted: EncryptedDeliveryPayload,
        *,
        outbox_id: str,
        user_id: str,
        action_token_id: str,
        purpose: str,
    ) -> str:
        key = self._keys.get(encrypted.key_version)
        if key is None:
            raise ValueError("Delivery encryption key version is unavailable.")
        if len(encrypted.ciphertext) <= NONCE_BYTES:
            raise ValueError("Delivery ciphertext is truncated.")
        nonce = encrypted.ciphertext[:NONCE_BYTES]
        payload = encrypted.ciphertext[NONCE_BYTES:]
        aad = self._aad(
            outbox_id=outbox_id,
            user_id=user_id,
            action_token_id=action_token_id,
            purpose=purpose,
        )
        try:
            plaintext = AESGCM(key).decrypt(nonce, payload, aad)
        except InvalidTag as exc:
            raise ValueError("Delivery ciphertext authentication failed.") from exc
        try:
            return plaintext.decode()
        except UnicodeDecodeError as exc:
            raise ValueError("Delivery plaintext encoding is invalid.") from exc


__all__ = ["DeliveryPayloadCipher", "EncryptedDeliveryPayload"]
