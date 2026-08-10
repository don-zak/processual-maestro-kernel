from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
AES_256_KEY_BYTES = 32
PAYMENT_DESTINATION_PURPOSE = "admin_marketplace_payment_destination"


@dataclass(frozen=True, slots=True)
class EncryptedPaymentDestinationIdentifier:
    ciphertext: bytes
    key_version: str


class PaymentDestinationCipher:
    def __init__(
        self,
        *,
        current_key_version: str,
        keys: Mapping[str, bytes],
    ) -> None:
        normalized_version = current_key_version.strip()
        copied = dict(keys)

        if not normalized_version:
            raise ValueError("current_key_version must not be empty.")
        if normalized_version not in copied:
            raise ValueError("Current payment destination key version is unavailable.")

        for version, key in copied.items():
            if not version.strip():
                raise ValueError("Payment destination key version must not be empty.")
            if not isinstance(key, bytes) or len(key) != AES_256_KEY_BYTES:
                raise ValueError(
                    "Every payment destination encryption key must be a named "
                    "32-byte key."
                )

        self.current_key_version = normalized_version
        self._keys = MappingProxyType(copied)

    @staticmethod
    def _aad(
        *,
        payment_destination_id: str,
        destination_ref: str,
    ) -> bytes:
        values = (
            payment_destination_id.strip(),
            destination_ref.strip().lower(),
            PAYMENT_DESTINATION_PURPOSE,
        )
        if any(not value for value in values):
            raise ValueError("Payment destination encryption authority is required.")

        return (
            f"pmk-admin-marketplace-v1:{values[0]}:{values[1]}:{values[2]}"
        ).encode()

    def encrypt(
        self,
        raw_identifier: str,
        *,
        payment_destination_id: str,
        destination_ref: str,
    ) -> EncryptedPaymentDestinationIdentifier:
        if not isinstance(raw_identifier, str) or not raw_identifier:
            raise ValueError("raw_identifier must be a non-empty string.")

        nonce = os.urandom(NONCE_BYTES)
        aad = self._aad(
            payment_destination_id=payment_destination_id,
            destination_ref=destination_ref,
        )
        key = self._keys[self.current_key_version]
        ciphertext = nonce + AESGCM(key).encrypt(
            nonce,
            raw_identifier.encode(),
            aad,
        )

        return EncryptedPaymentDestinationIdentifier(
            ciphertext=ciphertext,
            key_version=self.current_key_version,
        )

    def decrypt(
        self,
        encrypted: EncryptedPaymentDestinationIdentifier,
        *,
        payment_destination_id: str,
        destination_ref: str,
    ) -> str:
        key = self._keys.get(encrypted.key_version)
        if key is None:
            raise ValueError("Payment destination encryption key is unavailable.")
        if len(encrypted.ciphertext) <= NONCE_BYTES:
            raise ValueError("Payment destination ciphertext is truncated.")

        nonce = encrypted.ciphertext[:NONCE_BYTES]
        payload = encrypted.ciphertext[NONCE_BYTES:]
        aad = self._aad(
            payment_destination_id=payment_destination_id,
            destination_ref=destination_ref,
        )

        try:
            plaintext = AESGCM(key).decrypt(nonce, payload, aad)
        except InvalidTag as exc:
            raise ValueError(
                "Payment destination ciphertext authentication failed."
            ) from exc

        try:
            return plaintext.decode()
        except UnicodeDecodeError as exc:
            raise ValueError(
                "Payment destination plaintext encoding is invalid."
            ) from exc


__all__ = [
    "EncryptedPaymentDestinationIdentifier",
    "PaymentDestinationCipher",
]
