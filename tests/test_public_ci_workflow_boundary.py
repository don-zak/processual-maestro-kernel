from pathlib import Path


def test_private_ci_job_is_disabled_in_the_public_repository():
    private_ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "name: CI (Private monorepo)" in private_ci
    assert "if: ${{ endsWith(github.repository, '-private') }}" in private_ci


def test_public_ci_keeps_python_314_and_public_strip_gates():
    public_ci = Path(".github/workflows/ci-public.yml").read_text(encoding="utf-8")

    required_markers = (
        'python-version: ["3.14"]',
        "Strip private modules (public build)",
        "Verify private modules not accessible",
        "ruff check . --output-format=github",
        "flake8 . --count --select=E9,F63,F7,F82 --statistics",
        "processual_api/auth/security.py",
        "processual_api/middleware/subscription.py",
        "--follow-imports=skip",
        "pytest --cov=processual_kernel --cov=processual_api",
        "python -m twine check dist/*",
    )

    for marker in required_markers:
        assert marker in public_ci
