from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.admin_governance.onboarding_mfa_service import (
    AdministratorOnboardingMfaError,
    AdministratorOnboardingMfaService,
)
from processual_api.auth.mfa_crypto import EncryptedMfaSecret
from processual_api.auth.totp import totp_code_for_step


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000050")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000049")
FACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000051")
PROOF = "mfa-proof-secret"
SECRET = b"01234567890123456789"


@dataclass
class FakeInvitation:
    id: uuid.UUID = INVITATION_ID
    accepted_by_user_id: uuid.UUID | None = USER_ID
    onboarding_mfa_proof_hash: str | None = hashlib.sha256(PROOF.encode()).hexdigest()
    onboarding_mfa_proof_expires_at: datetime | None = NOW + timedelta(minutes=15)
    status: str = "pending"
    email_normalized: str = "admin@example.com"
    supervision_level: str = "operations_supervisor"


@dataclass
class FakeUser:
    id: uuid.UUID = USER_ID
    email_normalized: str = "admin@example.com"
    status: str = "pending_verification"
    email_verified_at: datetime | None = NOW


@dataclass
class FakeFactor:
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    secret_ciphertext: bytes
    secret_key_version: str
    last_used_step: int | None = None
    verified_at: datetime | None = None


@dataclass(frozen=True)
class FakeMaterial:
    raw: str
    digest: str


class FakeCipher:
    def encrypt(self, secret: bytes, *, factor_id: str, user_id: str) -> EncryptedMfaSecret:
        del factor_id, user_id
        return EncryptedMfaSecret(ciphertext=secret, key_version="v1")

    def decrypt(self, encrypted: EncryptedMfaSecret, *, factor_id: str, user_id: str) -> bytes:
        del factor_id, user_id
        return encrypted.ciphertext


class FakeDigester:
    def __init__(self) -> None:
        self.counter = 0

    def generate_recovery_code(self) -> FakeMaterial:
        self.counter += 1
        raw = f"RECOVERY-{self.counter:02d}"
        return FakeMaterial(raw=raw, digest=f"digest-{self.counter:02d}")


class FakeRepository:
    def __init__(self) -> None:
        self.invitation = FakeInvitation()
        self.user = FakeUser()
        self.pending_factor: FakeFactor | None = None
        self.active_factor: FakeFactor | None = None
        self.recovery_hashes: tuple[str, ...] = ()

    async def invitation_by_id(self, *, invitation_id: uuid.UUID):
        return self.invitation if invitation_id == self.invitation.id else None

    async def invitation_for_update(self, *, invitation_id: uuid.UUID):
        return await self.invitation_by_id(invitation_id=invitation_id)

    async def onboarding_user_for_update(self, *, user_id: uuid.UUID):
        return self.user if user_id == self.user.id else None

    async def active_mfa_factor_for_update(self, *, user_id: uuid.UUID):
        del user_id
        return self.active_factor

    async def pending_mfa_factor_for_update(self, *, user_id: uuid.UUID):
        del user_id
        return self.pending_factor

    async def disable_pending_mfa_factors(self, *, user_id: uuid.UUID, disabled_at: datetime) -> None:
        del user_id, disabled_at
        self.pending_factor = None

    def add_pending_mfa_factor(
        self,
        *,
        factor_id: uuid.UUID,
        user_id: uuid.UUID,
        label: str,
        ciphertext: bytes,
        key_version: str,
    ) -> None:
        assert label == "Security Key"
        self.pending_factor = FakeFactor(
            id=factor_id,
            user_id=user_id,
            status="pending",
            secret_ciphertext=ciphertext,
            secret_key_version=key_version,
        )

    async def replace_mfa_recovery_codes(
        self,
        *,
        factor_id: uuid.UUID,
        code_hashes: tuple[str, ...],
    ) -> None:
        assert factor_id == FACTOR_ID
        self.recovery_hashes = code_hashes

    def complete_mfa_onboarding(self, invitation, *, completed_at: datetime) -> None:
        invitation.status = "accepted"
        invitation.onboarding_mfa_proof_hash = None
        invitation.onboarding_mfa_proof_expires_at = None
        invitation.completed_at = completed_at


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _service(repository: FakeRepository) -> tuple[AdministratorOnboardingMfaService, FakeUnitOfWork]:
    unit = FakeUnitOfWork(repository)
    service = AdministratorOnboardingMfaService(
        unit_of_work_factory=lambda: unit,
        cipher=FakeCipher(),
        token_digester=FakeDigester(),
        clock=lambda: NOW,
        factor_id_factory=lambda: FACTOR_ID,
    )
    return service, unit


@pytest.mark.asyncio
async def test_enroll_uses_onboarding_proof_without_creating_session() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    enrollment = await service.enroll(
        invitation_id=INVITATION_ID,
        user_id=USER_ID,
        mfa_proof=PROOF,
        label="  Security Key  ",
    )

    assert unit.committed is True
    assert repository.pending_factor is not None
    assert repository.pending_factor.secret_ciphertext == SECRET or len(enrollment.secret) > 20
    assert enrollment.provisioning_uri.startswith("otpauth://totp/")
    assert enrollment.next_action == "confirm_mfa"
    assert repository.user.status == "pending_verification"


@pytest.mark.asyncio
async def test_confirm_activates_mfa_consumes_proof_but_does_not_activate_identity() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)
    await service.enroll(
        invitation_id=INVITATION_ID,
        user_id=USER_ID,
        mfa_proof=PROOF,
        label="Security Key",
    )
    unit.committed = False
    assert repository.pending_factor is not None
    secret = repository.pending_factor.secret_ciphertext
    code = totp_code_for_step(secret, int(NOW.timestamp() // 30))

    completion, recovery_codes = await service.confirm(
        invitation_id=INVITATION_ID,
        user_id=USER_ID,
        mfa_proof=PROOF,
        code=code,
    )

    assert unit.committed is True
    assert repository.pending_factor.status == "active"
    assert repository.pending_factor.verified_at == NOW
    assert len(recovery_codes) == 10
    assert len(repository.recovery_hashes) == 10
    assert repository.invitation.status == "accepted"
    assert repository.invitation.onboarding_mfa_proof_hash is None
    assert repository.invitation.onboarding_mfa_proof_expires_at is None
    assert repository.user.status == "pending_verification"
    assert completion.status == "mfa_complete_pending_activation"
    assert completion.next_action == "activate_permissions"
    assert completion.supervision_level == "operations_supervisor"


@pytest.mark.asyncio
async def test_confirm_rejects_invalid_totp_without_consuming_proof() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)
    await service.enroll(
        invitation_id=INVITATION_ID,
        user_id=USER_ID,
        mfa_proof=PROOF,
        label="Security Key",
    )
    unit.committed = False

    with pytest.raises(AdministratorOnboardingMfaError, match="credential is invalid"):
        await service.confirm(
            invitation_id=INVITATION_ID,
            user_id=USER_ID,
            mfa_proof=PROOF,
            code="000000",
        )

    assert unit.committed is False
    assert repository.invitation.status == "pending"
    assert repository.invitation.onboarding_mfa_proof_hash is not None
    assert repository.user.status == "pending_verification"
