from pathlib import Path


WORKFLOW = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")


def test_public_tag_push_builds_and_publishes_public_target() -> None:
    assert 'tags: ["v*"]' in WORKFLOW
    assert "target: public" in WORKFLOW
    assert "Build and push tagged public Docker image" in WORKFLOW
    assert "processual-maestro-public:${{ github.ref_name }}" in WORKFLOW
    assert "processual-maestro-public:latest" in WORKFLOW


def test_public_ghcr_publish_has_explicit_auth_and_permission() -> None:
    assert "packages: write" in WORKFLOW
    assert "Log in to GitHub Container Registry" in WORKFLOW
    assert "docker/login-action@65b78e6e13532edd9afa3aa52ac7964289d1a9c1" in WORKFLOW
    assert "registry: ghcr.io" in WORKFLOW
    assert "username: ${{ github.actor }}" in WORKFLOW
    assert "password: ${{ secrets.GITHUB_TOKEN }}" in WORKFLOW


def test_manual_dispatch_remains_public_only_and_fail_closed() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "target: public" in WORKFLOW
    assert "target: private" not in WORKFLOW
    assert "cgtlib._HAS_PRIVATE is False" in WORKFLOW
    assert 'find_spec("cgtlib.private") is None' in WORKFLOW
    assert 'find_spec("processual_api.private_integrations") is None' in WORKFLOW
    assert "PrivateEvaluationUnavailableError" in WORKFLOW


def test_workflow_records_sbom_and_immutable_release_evidence() -> None:
    assert "Record immutable published image digest" in WORKFLOW
    assert "Generate public container SBOM" in WORKFLOW
    assert "public-container.cdx.json" in WORKFLOW
    assert "public-container.spdx.json" in WORKFLOW
    assert "Verify public container SBOM trust boundary" in WORKFLOW
    assert "Upload public container evidence" in WORKFLOW
