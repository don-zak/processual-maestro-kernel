from __future__ import annotations

import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise ValueError("email must be a string.")
    normalized = unicodedata.normalize("NFKC", email).strip().casefold()
    if normalized.count("@") != 1 or any(ord(character) < 32 for character in normalized):
        raise ValueError("email has an invalid structure.")
    local, domain = normalized.split("@", 1)
    if not local or not domain or len(local) > 64:
        raise ValueError("email has an invalid structure.")
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("email domain is invalid.") from exc
    result = f"{local}@{ascii_domain}"
    if len(result) > 320 or "." not in ascii_domain:
        raise ValueError("email has an invalid structure.")
    return result


def normalize_display_name(display_name: str) -> str:
    if not isinstance(display_name, str):
        raise ValueError("display_name must be a string.")
    normalized = " ".join(unicodedata.normalize("NFKC", display_name).split())
    if not normalized or len(normalized) > 200:
        raise ValueError("display_name must contain between 1 and 200 characters.")
    return normalized


def organization_slug(display_name: str, *, suffix: str) -> str:
    normalized_name = normalize_display_name(display_name)
    ascii_name = unicodedata.normalize("NFKD", normalized_name).encode("ascii", "ignore").decode("ascii").casefold()
    stem = _SLUG_RE.sub("-", ascii_name).strip("-") or "organization"
    normalized_suffix = _SLUG_RE.sub("", suffix.casefold())
    if len(normalized_suffix) < 6:
        raise ValueError("organization slug suffix is too short.")
    return f"{stem[:80].rstrip('-')}-{normalized_suffix[:12]}"


__all__ = ["normalize_display_name", "normalize_email", "organization_slug"]
