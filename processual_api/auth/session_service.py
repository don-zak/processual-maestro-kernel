from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from processual_api.auth.normalization import normalize_email
from processual_api.auth.passwords import PasswordService
from processual_api.auth.security import create_access_token
from processual_api.auth.session_contracts import IssuedSession, SessionView
from processual_api.auth.session_repository import SqlAlchemySessionUnitOfWork
from processual_api.auth.token_material import TokenDigester


class InvalidSessionCredentialsError(RuntimeError):
    """The supplied login or refresh credentials are not usable."""


class RefreshTokenReuseError(InvalidSessionCredentialsError):
    """A consumed refresh token was replayed and its family was revoked."""


class SessionAuthorityUnavailableError(RuntimeError):
    """The authoritative session store could not complete the operation."""


class SessionService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], SqlAlchemySessionUnitOfWork],
        password_service: PasswordService,
        token_digester: TokenDigester,
        dummy_password_hash: str,
        access_token_seconds: int = 15 * 60,
        refresh_token_ttl: timedelta = timedelta(days=30),
        failed_login_limit: int = 5,
        lockout_duration: timedelta = timedelta(minutes=15),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if access_token_seconds < 60 or access_token_seconds > 60 * 60:
            raise ValueError("Access-token lifetime is outside its safe range.")
        if refresh_token_ttl < timedelta(hours=1) or refresh_token_ttl > timedelta(days=90):
            raise ValueError("Refresh-token lifetime is outside its safe range.")
        if failed_login_limit < 2 or failed_login_limit > 20:
            raise ValueError("Failed-login limit is outside its safe range.")
        if lockout_duration < timedelta(minutes=1) or lockout_duration > timedelta(days=1):
            raise ValueError("Login lockout duration is outside its safe range.")
        self._unit_of_work_factory = unit_of_work_factory
        self._password_service = password_service
        self._token_digester = token_digester
        self._dummy_password_hash = dummy_password_hash
        self._access_token_seconds = access_token_seconds
        self._refresh_token_ttl = refresh_token_ttl
        self._failed_login_limit = failed_login_limit
        self._lockout_duration = lockout_duration
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Session clock must be timezone-aware.")
        return now

    def _issue_access_token(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        organization_id: uuid.UUID | None,
        session_expires_at: datetime,
        mfa_required: bool = False,
        platform_authorities: tuple[str, ...] = (),
    ) -> tuple[str, int]:
        remaining = int((session_expires_at - self._now()).total_seconds())
        expires_in = min(self._access_token_seconds, remaining)
        if expires_in < 1:
            raise InvalidSessionCredentialsError("Session credentials are invalid.")
        return (
            create_access_token(
                subject=str(user_id),
                expires_delta=timedelta(seconds=expires_in),
                role="client",
                client_id=str(organization_id or user_id),
                session_type="identity_user",
                scopes=["auth:mfa"] if mfa_required else ["evaluation"],
                session_id=str(session_id),
                organization_id=str(organization_id) if organization_id else None,
                platform_authorities=platform_authorities,
            ),
            expires_in,
        )

    @staticmethod
    def _csrf_token() -> str:
        return secrets.token_urlsafe(32)

    async def login(self, *, email: str, password: str) -> IssuedSession:
        try:
            normalized_email = normalize_email(email)
        except ValueError as exc:
            self._password_service.verify_password(self._dummy_password_hash, password)
            raise InvalidSessionCredentialsError("Session credentials are invalid.") from exc

        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise SessionAuthorityUnavailableError("Session repository is unavailable.")
            user = await repository.user_for_login(normalized_email)
            if user is None:
                self._password_service.verify_password(self._dummy_password_hash, password)
                raise InvalidSessionCredentialsError("Session credentials are invalid.")

            verification = self._password_service.verify_password(user.password_hash, password)
            locked = user.locked_until is not None and user.locked_until > now
            eligible = user.status == "active" and not locked
            if not verification.valid or not eligible:
                if not verification.valid and not locked:
                    user.failed_login_count += 1
                    if user.failed_login_count >= self._failed_login_limit:
                        user.locked_until = now + self._lockout_duration
                await uow.commit()
                raise InvalidSessionCredentialsError("Session credentials are invalid.")

            if verification.needs_rehash:
                user.password_hash = self._password_service.hash_password(password)
                user.password_changed_at = now
            user.failed_login_count = 0
            user.locked_until = None
            organization_id = await repository.active_organization_id(user.id)
            platform_authorities = (
                await repository.active_platform_authorities(user.id)
            )
            mfa_required = await repository.requires_mfa(user.id)
            session_id = uuid.uuid4()
            family_id = uuid.uuid4()
            refresh_id = uuid.uuid4()
            refresh = self._token_digester.generate_token(purpose="refresh_token")
            session_expires_at = now + self._refresh_token_ttl
            repository.add_session(
                session_id=session_id,
                user_id=user.id,
                organization_id=organization_id,
                refresh_family_id=family_id,
                refresh_token_id=refresh_id,
                refresh_token_hash=refresh.digest,
                authenticated_at=now,
                expires_at=session_expires_at,
                mfa_satisfied_at=None,
            )
            await uow.commit()

        access_token, expires_in = self._issue_access_token(
            user_id=user.id,
            session_id=session_id,
            organization_id=organization_id,
            session_expires_at=session_expires_at,
            mfa_required=mfa_required,
            platform_authorities=platform_authorities,
        )
        return IssuedSession(
            access_token=access_token,
            access_expires_in=expires_in,
            refresh_token=refresh.raw,
            refresh_expires_in=int(self._refresh_token_ttl.total_seconds()),
            csrf_token=self._csrf_token(),
            session_id=session_id,
            mfa_required=mfa_required,
        )

    async def refresh(self, raw_refresh_token: str) -> IssuedSession:
        token_hash = self._token_digester.digest(raw_refresh_token, purpose="refresh_token")
        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise SessionAuthorityUnavailableError("Session repository is unavailable.")
            principals = await repository.refresh_principals_for_update(token_hash)
            if principals is None:
                raise InvalidSessionCredentialsError("Session credentials are invalid.")
            previous, auth_session, user = principals
            if previous.consumed_at is not None:
                await repository.revoke_family(
                    auth_session,
                    revoked_at=now,
                    reason="refresh_token_reuse",
                    reuse_token=previous,
                )
                await uow.commit()
                raise RefreshTokenReuseError("Session credentials are invalid.")
            invalid = (
                previous.revoked_at is not None
                or previous.expires_at <= now
                or auth_session.revoked_at is not None
                or auth_session.expires_at <= now
                or user.status != "active"
            )
            if invalid:
                if auth_session.revoked_at is None:
                    await repository.revoke_family(
                        auth_session,
                        revoked_at=now,
                        reason="refresh_credentials_invalid",
                    )
                    await uow.commit()
                raise InvalidSessionCredentialsError("Session credentials are invalid.")

            replacement = self._token_digester.generate_token(purpose="refresh_token")
            repository.rotate_refresh_token(
                previous=previous,
                token_id=uuid.uuid4(),
                token_hash=replacement.digest,
                rotated_at=now,
                expires_at=auth_session.expires_at,
            )
            auth_session.last_seen_at = now
            platform_authorities = (
                await repository.active_platform_authorities(user.id)
            )
            await uow.commit()

        access_token, expires_in = self._issue_access_token(
            user_id=user.id,
            session_id=auth_session.id,
            organization_id=auth_session.organization_id,
            session_expires_at=auth_session.expires_at,
            platform_authorities=platform_authorities,
        )
        return IssuedSession(
            access_token=access_token,
            access_expires_in=expires_in,
            refresh_token=replacement.raw,
            refresh_expires_in=max(1, int((auth_session.expires_at - self._now()).total_seconds())),
            csrf_token=self._csrf_token(),
            session_id=auth_session.id,
        )

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = self._token_digester.digest(raw_refresh_token, purpose="refresh_token")
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise SessionAuthorityUnavailableError("Session repository is unavailable.")
            principals = await repository.refresh_principals_for_update(token_hash)
            if principals is not None:
                _, auth_session, _ = principals
                await repository.revoke_family(
                    auth_session,
                    revoked_at=self._now(),
                    reason="user_logout",
                )
                await uow.commit()

    async def logout_all(self, raw_refresh_token: str) -> None:
        token_hash = self._token_digester.digest(raw_refresh_token, purpose="refresh_token")
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise SessionAuthorityUnavailableError("Session repository is unavailable.")
            principals = await repository.refresh_principals_for_update(token_hash)
            if principals is not None:
                _, _, user = principals
                await repository.revoke_all_for_user(
                    user.id,
                    revoked_at=self._now(),
                    reason="user_logout_all",
                )
                await uow.commit()

    async def list_sessions(self, user_id: uuid.UUID) -> tuple[SessionView, ...]:
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise SessionAuthorityUnavailableError("Session repository is unavailable.")
            sessions = await repository.sessions_for_user(user_id)
        now = self._now()
        return tuple(session for session in sessions if session.expires_at > now)

    async def revoke_session(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise SessionAuthorityUnavailableError("Session repository is unavailable.")
            auth_session = await repository.owned_session_for_update(
                session_id=session_id,
                user_id=user_id,
            )
            if auth_session is not None and auth_session.revoked_at is None:
                await repository.revoke_family(
                    auth_session,
                    revoked_at=self._now(),
                    reason="user_session_revoked",
                )
                await uow.commit()


__all__ = [
    "InvalidSessionCredentialsError",
    "RefreshTokenReuseError",
    "SessionAuthorityUnavailableError",
    "SessionService",
]
