from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class KeySource(StrEnum):
    ENV = "env"
    FILE = "file"
    KUBERNETES = "kubernetes"
    VAULT = "vault"


@dataclass(frozen=True, slots=True)
class CryptoKey:
    key_id: str
    key_bytes: bytes
    source: KeySource
    algorithm: str = "AES-256-GCM"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def get_key_source() -> KeySource:
    if os.environ.get("PROCESSUAL_CRYPTO_KEY_B64"):
        return KeySource.ENV
    if os.environ.get("PROCESSUAL_CRYPTO_KEY_FILE"):
        return KeySource.FILE
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
        return KeySource.KUBERNETES
    return KeySource.ENV


def load_key_from_env() -> CryptoKey:
    key_b64 = os.environ.get("PROCESSUAL_CRYPTO_KEY_B64")
    if key_b64:
        import base64

        key_bytes = base64.urlsafe_b64decode(key_b64.encode("ascii"))
        key_id = os.environ.get("PROCESSUAL_CRYPTO_KEY_ID", "env-key")
        algorithm = os.environ.get("PROCESSUAL_CRYPTO_ALGORITHM", "AES-256-GCM")
        return CryptoKey(key_id=key_id, key_bytes=key_bytes, source=KeySource.ENV, algorithm=algorithm)

    env_file = os.environ.get("PROCESSUAL_CRYPTO_KEY_FILE")
    if env_file and os.path.isfile(env_file):
        key_bytes = open(env_file, "rb").read().strip()
        key_id = os.environ.get("PROCESSUAL_CRYPTO_KEY_ID", "file-key")
        algorithm = os.environ.get("PROCESSUAL_CRYPTO_ALGORITHM", "AES-256-GCM")
        return CryptoKey(key_id=key_id, key_bytes=key_bytes, source=KeySource.FILE, algorithm=algorithm)

    raise ValueError(
        "no crypto key found. Set PROCESSUAL_CRYPTO_KEY_B64 env var "
        "or PROCESSUAL_CRYPTO_KEY_FILE pointing to a key file."
    )


class KeyRing:
    def __init__(self) -> None:
        self._keys: dict[str, CryptoKey] = {}

    def add_key(self, key: CryptoKey) -> None:
        self._keys[key.key_id] = key

    def get_key(self, key_id: str) -> CryptoKey:
        try:
            return self._keys[key_id]
        except KeyError:
            raise KeyError(f"key not found: {key_id}")

    def list_keys(self) -> list[str]:
        return list(self._keys)

    def load_from_env(self) -> CryptoKey:
        key = load_key_from_env()
        self.add_key(key)
        return key
