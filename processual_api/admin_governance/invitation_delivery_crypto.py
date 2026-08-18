from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
AES_256_KEY_BYTES = 32
PURPOSE = "admin_governance_invitation"


@dataclass(frozen=True, slots=True)
class EncryptedAdministratorInvitationPayload:
    ciphertext: bytes
    key_version: str


class AdministratorInvitationPayloadCipher:
    def __init__(self, *, current_key_version: str, keys: Mapping[str, bytes]) -> None:
        if not current_key_version.strip():
            raise ValueError("current_key_version must not be empty.")
        copied = dict(keys)
        if current_key_version not in copied:
            raise ValueError("The current governance delivery key version is unavailable.")
        for version, key in copied.items():
            if not version.strip() or not isinstance(key, bytes) or len(key) != AES_256_KEY_BYTES:
                raise ValueError("Every governance delivery key must be a named 32-byte key.")
        self.current_key_version = current_key_version
        self._keys = MappingProxyType(copied)

    @staticmethod
    def _aad(*, outbox_id: str, invitation_id: str, recipient_email: str) -> bytes:
        values = (outbox_id, invitation_id, recipient_email)
        if any(not value.strip() for value in values):
            raise ValueError("Governance delivery encryption authority identifiers are required.")
        return (
            f"pmk-admin-governance-delivery-v1:{outbox_id}:{invitation_id}:{recipient_email}:{PURPOSE}"
        ).encode()

    def encrypt(
        self,
        raw_token: str,
        *,
        outbox_id: str,
        invitation_id: str,
        recipient_email: str,
    ) -> EncryptedAdministratorInvitationPayload:
        if not isinstance(raw_token, str) or not raw_token:
            raise ValueError("raw_token must be a non-empty string.")
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = nonce + AESGCM(self._keys[self.current_key_version]).encrypt(
            nonce,
            raw_token.encode(),
            self._aad(
                outbox_id=outbox_id,
                invitation_id=invitation_id,
                recipient_email=recipient_email,
            ),
        )
        return EncryptedAdministratorInvitationPayload(
            ciphertext=ciphertext,
            key_version=self.current_key_version,
        )

    def decrypt(
        self,
        encrypted: EncryptedAdministratorInvitationPayload,
        *,
        outbox_id: str,
        invitation_id: str,
        recipient_email: str,
    ) -> str:
        key = self._keys.get(encrypted.key_version)
        if key is None:
            raise ValueError("Governance delivery encryption key version is unavailable.")
        if len(encrypted.ciphertext) <= NONCE_BYTES:
            raise ValueError("Governance delivery ciphertext is truncated.")
        nonce = encrypted.ciphertext[:NONCE_BYTES]
        payload = encrypted.ciphertext[NONCE_BYTES:]
        try:
            plaintext = AESGCM(key).decrypt(
                nonce,
                payload,
                self._aad(
                    outbox_id=outbox_id,
                    invitation_id=invitation_id,
                    recipient_email=recipient_email,
                ),
            )
        except InvalidTag as exc:
            raise ValueError("Governance delivery ciphertext authentication failed.") from exc
        try:
            return plaintext.decode()
        except UnicodeDecodeError as exc:
            raise ValueError("Governance delivery plaintext encoding is invalid.") from exc


__all__ = [
    "AdministratorInvitationPayloadCipher",
    "EncryptedAdministratorInvitationPayload",
    "PURPOSE",
]
