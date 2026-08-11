from pathlib import Path


WORKFLOW = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")


def test_public_tag_push_builds_public_target() -> None:
    assert 'tags: ["v*"]' in WORKFLOW
    assert "|| fromJSON('[\"public\"]')" in WORKFLOW


def test_public_ghcr_publish_has_explicit_auth_and_permission() -> None:
    assert "packages: write" in WORKFLOW
    assert "Log in to GitHub Container Registry" in WORKFLOW
    assert "docker/login-action@65b78e6e13532edd9afa3aa52ac7964289d1a9c1" in WORKFLOW
    assert "registry: ghcr.io" in WORKFLOW
    assert "username: ${{ github.actor }}" in WORKFLOW
    assert "password: ${{ secrets.GITHUB_TOKEN }}" in WORKFLOW


def test_manual_target_choice_remains_available() -> None:
    assert 'default: "private"' in WORKFLOW
    assert "options: [public, private]" in WORKFLOW
    assert "github.event_name == 'workflow_dispatch'" in WORKFLOW
