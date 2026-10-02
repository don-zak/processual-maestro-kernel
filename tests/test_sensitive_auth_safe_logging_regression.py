from __future__ import annotations

from pathlib import Path


SENSITIVE_AUTH_FILES = (
    Path("processual_api/auth/delivery_operations_router.py"),
    Path("processual_api/auth/recovery_email_router.py"),
    Path("processual_api/auth/account_recovery_router.py"),
)


def test_sensitive_auth_failure_logs_do_not_emit_tracebacks_or_exception_text() -> None:
    for path in SENSITIVE_AUTH_FILES:
        source = path.read_text(encoding="utf-8")
        assert "logger.exception(" not in source, path
        assert "str(exc)" not in source, path
        assert '"exception_type": type(exc).__name__' in source, path


def test_sensitive_auth_http_errors_remain_generic() -> None:
    delivery = Path("processual_api/auth/delivery_operations_router.py").read_text(encoding="utf-8")
    recovery_email = Path("processual_api/auth/recovery_email_router.py").read_text(encoding="utf-8")
    account_recovery = Path("processual_api/auth/account_recovery_router.py").read_text(encoding="utf-8")

    assert "Delivery operations temporarily unavailable." in delivery
    assert "Recovery-email service temporarily unavailable." in recovery_email
    assert "Account recovery service temporarily unavailable." in account_recovery
