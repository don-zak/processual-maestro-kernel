from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.supervisor_session_keys import (
    revoke_supervisor_session_keys_for_identity,
)


class ExternalAuthorityRevocationUnavailableError(RuntimeError):
    """External authority could not be revoked safely."""


@dataclass(frozen=True, slots=True)
class ExternalAuthorityRevocationReceipt:
    supervisor_session_keys_revoked: int
    api_keys_revoked: int


class AccountRecoveryExternalAuthorityRevoker:
    """Fail-closed external account authority revocation."""

    def __init__(
        self,
        *,
        supervisor_store_path: Path,
        settings_loader: Callable[
            [str],
            dict[str, Any],
        ],
        settings_saver: Callable[
            [str, dict[str, Any]],
            None,
        ],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._supervisor_store_path = supervisor_store_path
        self._settings_loader = settings_loader
        self._settings_saver = settings_saver
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()

        if now.tzinfo is None:
            raise ValueError("External authority revocation clock must be timezone-aware.")

        return now.astimezone(UTC)

    @staticmethod
    def _normalize_user_id(
        user_id: str,
    ) -> str:
        normalized = str(user_id or "").strip()

        if not normalized:
            raise ValueError("Account-recovery user id is required.")

        return normalized

    @staticmethod
    def _aliases(
        *,
        user_id: str,
        aliases: tuple[str, ...],
    ) -> tuple[str, ...]:
        values = {
            user_id,
            *(str(alias or "").strip() for alias in aliases if str(alias or "").strip()),
        }

        return tuple(sorted(values))

    def _revoke_api_keys(
        self,
        *,
        user_id: str,
        revoked_at: datetime,
    ) -> int:
        try:
            raw = self._settings_loader(user_id)
        except Exception as exc:
            raise (ExternalAuthorityRevocationUnavailableError("API key authority is unavailable.")) from exc

        if not isinstance(raw, dict):
            raise (ExternalAuthorityRevocationUnavailableError("API key authority is invalid."))

        keys = raw.get(
            "api_keys",
            [],
        )

        if keys is None:
            keys = []

        if not isinstance(keys, list):
            raise (ExternalAuthorityRevocationUnavailableError("API key authority is invalid."))

        revoked_at_iso = revoked_at.isoformat()
        revoked_count = 0

        for key in keys:
            if not isinstance(key, dict):
                raise (ExternalAuthorityRevocationUnavailableError("API key authority is invalid."))

            owner = str(key.get("user_id") or user_id).strip()

            if owner != user_id:
                continue

            if key.get("revoked_at"):
                continue

            status = str(key.get("status") or "enabled").strip().casefold()

            if status in {
                "revoked",
                "disabled",
                "expired",
            }:
                continue

            key["status"] = "revoked"
            key["revoked_at"] = revoked_at_iso
            key["revocation_reason"] = "account_recovery_completed"
            revoked_count += 1

        if not revoked_count:
            return 0

        raw["api_keys"] = keys

        try:
            self._settings_saver(
                user_id,
                raw,
            )
        except Exception as exc:
            raise (ExternalAuthorityRevocationUnavailableError("API key authority could not be persisted.")) from exc

        return revoked_count

    def revoke(
        self,
        *,
        user_id: str,
        identity_aliases: tuple[str, ...] = (),
    ) -> ExternalAuthorityRevocationReceipt:
        normalized_user_id = self._normalize_user_id(user_id)
        now = self._now()

        identities = self._aliases(
            user_id=normalized_user_id,
            aliases=identity_aliases,
        )

        try:
            supervisor_count = revoke_supervisor_session_keys_for_identity(
                self._supervisor_store_path,
                identities,
                revoked_by="account_recovery",
                reason="account_recovery_completed",
                revoked_at=now,
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            raise (
                ExternalAuthorityRevocationUnavailableError("Supervisor session key authority could not be revoked.")
            ) from exc

        api_key_count = self._revoke_api_keys(
            user_id=normalized_user_id,
            revoked_at=now,
        )

        return ExternalAuthorityRevocationReceipt(
            supervisor_session_keys_revoked=(supervisor_count),
            api_keys_revoked=api_key_count,
        )


__all__ = [
    "AccountRecoveryExternalAuthorityRevoker",
    "ExternalAuthorityRevocationReceipt",
    "ExternalAuthorityRevocationUnavailableError",
]
