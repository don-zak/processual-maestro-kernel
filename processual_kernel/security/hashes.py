from __future__ import annotations

import hashlib


def sha256_hex_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha3_256_hex_bytes(value: bytes) -> str:
    return hashlib.sha3_256(value).hexdigest()
