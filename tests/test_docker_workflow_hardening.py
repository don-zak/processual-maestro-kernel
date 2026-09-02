from pathlib import Path


def test_docker_workflow_verifies_public_image_on_pull_requests() -> None:
    workflow = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")

    required_markers = (
        "pull_request:\n    branches: [main]",
        "verify-public-image:",
        "if: github.event_name == 'pull_request'",
        "permissions:\n      contents: read",
        "persist-credentials: false",
        "target: public",
        "push: false",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f",
        "docker/build-push-action@ca052bb54ab0790a636c9b5f226502c73d547a25",
    )

    for marker in required_markers:
        assert marker in workflow


def test_docker_publish_credentials_are_not_available_to_pull_request_job() -> None:
    workflow = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")
    verify_block, publish_block = workflow.split("  publish:", 1)

    assert "packages: write" not in verify_block
    assert "docker/login-action" not in verify_block
    assert "packages: write" in publish_block
    assert "if: github.event_name != 'pull_request'" in publish_block
