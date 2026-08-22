from __future__ import annotations

import base64
import binascii
import json

from processual_api.admin_governance.durable_invitation_repository import (
    SqlAlchemyDurableAdministratorInvitationUnitOfWork,
)
from processual_api.admin_governance.invitation_delivery_crypto import (
    AdministratorInvitationPayloadCipher,
)
from processual_api.admin_governance.invitation_service import (
    AdministratorInvitationService,
)
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings


class AdministratorInvitationRuntimeUnavailableError(RuntimeError):
    pass


def _delivery_keys(raw_json: str | None) -> dict[str, bytes]:
    if raw_json is None:
        raise AdministratorInvitationRuntimeUnavailableError(
            "Administrator invitation delivery key authority is unavailable."
        )
    try:
        payload = json.loads(raw_json)
        if not isinstance(payload, dict) or not payload:
            raise ValueError
        keys = {
            str(version): base64.b64decode(encoded, validate=True)
            for version, encoded in payload.items()
            if isinstance(version, str) and isinstance(encoded, str)
        }
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise AdministratorInvitationRuntimeUnavailableError(
            "Administrator invitation delivery key authority is invalid."
        ) from exc
    if len(keys) != len(payload):
        raise AdministratorInvitationRuntimeUnavailableError(
            "Administrator invitation delivery key authority is invalid."
        )
    return keys


def build_administrator_invitation_service(
    config: APISettings = settings,
) -> AdministratorInvitationService:
    try:
        session_factory = get_session_factory()
        cipher = AdministratorInvitationPayloadCipher(
            current_key_version=config.auth_delivery_current_key_version or "",
            keys=_delivery_keys(config.auth_delivery_key_ring_json),
        )
    except AdministratorInvitationRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise AdministratorInvitationRuntimeUnavailableError(
            "Administrator invitation runtime authority is unavailable."
        ) from exc

    return AdministratorInvitationService(
        unit_of_work_factory=lambda: SqlAlchemyDurableAdministratorInvitationUnitOfWork(
            session_factory
        ),
        payload_cipher=cipher,
    )


__all__ = [
    "AdministratorInvitationRuntimeUnavailableError",
    "build_administrator_invitation_service",
]
