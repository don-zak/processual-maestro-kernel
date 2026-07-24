from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from processual_api.auth.account_recovery_repository import (
    SqlAlchemyAccountRecoveryRepository,
    SqlAlchemyAccountRecoveryUnitOfWork,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


class RecordingSession:
    def __init__(self) -> None:
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def add(self, value) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


def test_repository_adds_request_and_outbox_atomically() -> None:
    session = RecordingSession()
    repository = SqlAlchemyAccountRecoveryRepository(session)

    request_id = uuid.uuid4()
    outbox_id = uuid.uuid4()
    user_id = uuid.uuid4()
    recovery_email_id = uuid.uuid4()

    request, outbox = repository.add_request_with_delivery(
        request_id=request_id,
        outbox_id=outbox_id,
        user_id=user_id,
        recovery_email_id=recovery_email_id,
        purpose="platform_account_recovery",
        state="pending",
        verification_token_hash="digest-only",
        completion_token_hash=None,
        attempt_count=0,
        expires_at=NOW,
        verified_at=None,
        completed_at=None,
        revoked_at=None,
        created_at=NOW,
        updated_at=NOW,
        payload_ciphertext=b"ciphertext-only",
        payload_key_version="delivery-v1",
        available_at=NOW,
    )

    assert session.added == [request, outbox]
    assert request.id == request_id
    assert request.verification_token_hash == ("digest-only")
    assert outbox.id == outbox_id
    assert outbox.action_token_id is None
    assert outbox.account_recovery_request_id == request_id
    assert outbox.event_type == ("account_recovery_verification")
    assert outbox.payload_ciphertext == (b"ciphertext-only")


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_without_commit() -> None:
    session = RecordingSession()

    unit = SqlAlchemyAccountRecoveryUnitOfWork(lambda: session)

    async with unit:
        assert isinstance(
            unit.repository,
            SqlAlchemyAccountRecoveryRepository,
        )

    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


@pytest.mark.asyncio
async def test_unit_of_work_commit_preserves_transaction() -> None:
    session = RecordingSession()

    unit = SqlAlchemyAccountRecoveryUnitOfWork(lambda: session)

    async with unit:
        await unit.commit()

    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


class RowCountResult:
    def __init__(
        self,
        rowcount: int,
    ) -> None:
        self.rowcount = rowcount


class CompletionRecordingSession:
    def __init__(
        self,
        rowcounts: list[int],
    ) -> None:
        self.rowcounts = list(rowcounts)
        self.statements = []

    async def execute(
        self,
        statement,
    ):
        self.statements.append(statement)

        return RowCountResult(self.rowcounts.pop(0))


@pytest.mark.asyncio
async def test_repository_completion_mutations_return_counts() -> None:
    session = CompletionRecordingSession(
        [
            4,
            2,
            3,
            1,
            6,
        ]
    )
    repository = SqlAlchemyAccountRecoveryRepository(session)
    user_id = uuid.uuid4()

    refresh_count = await repository.revoke_refresh_tokens(
        user_id=user_id,
        revoked_at=NOW,
    )
    session_count = await repository.revoke_sessions(
        user_id=user_id,
        revoked_at=NOW,
        reason="account_recovery_completed",
    )
    action_count = await repository.invalidate_action_tokens(
        user_id=user_id,
        invalidated_at=NOW,
    )
    factor_count = await repository.disable_mfa_factors(
        user_id=user_id,
        disabled_at=NOW,
    )
    recovery_code_count = await repository.delete_mfa_recovery_codes(
        user_id=user_id,
    )

    assert refresh_count == 4
    assert session_count == 2
    assert action_count == 3
    assert factor_count == 1
    assert recovery_code_count == 6
    assert len(session.statements) == 5

    rendered = [str(statement) for statement in session.statements]

    assert "auth_refresh_tokens" in rendered[0]
    assert "auth_sessions" in rendered[1]
    assert "auth_action_tokens" in rendered[2]
    assert "auth_mfa_factors" in rendered[3]
    assert "auth_mfa_recovery_codes" in rendered[4]
