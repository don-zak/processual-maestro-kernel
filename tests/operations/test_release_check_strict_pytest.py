from __future__ import annotations

import subprocess

from scripts import release_check


def test_release_gate_rejects_failed_tests_even_at_ninety_percent() -> None:
    output = "90 passed, 10 failed in 1.00s"

    assert release_check._evaluate_pytest_result(1, output) == 1


def test_release_gate_rejects_nonzero_exit_without_summary() -> None:
    output = "pytest internal failure before summary"

    assert release_check._evaluate_pytest_result(2, output) == 1


def test_release_gate_rejects_zero_tests() -> None:
    output = "collected 0 items\nno tests ran in 0.01s"

    assert release_check._evaluate_pytest_result(0, output) == 1


def test_release_gate_rejects_timeout(monkeypatch) -> None:
    def _timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=300)

    monkeypatch.setattr(release_check.subprocess, "run", _timeout)

    assert release_check.run_pytest() == 1


def test_release_gate_accepts_clean_success() -> None:
    output = "100 passed in 1.00s"

    assert release_check._evaluate_pytest_result(0, output) == 0
