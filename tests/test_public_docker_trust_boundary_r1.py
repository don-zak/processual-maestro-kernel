from __future__ import annotations

from pathlib import Path


def _dockerfile() -> str:
    return Path("Dockerfile").read_text("utf-8")


def _docker_workflow() -> str:
    return Path(".github/workflows/docker.yml").read_text("utf-8")


def test_public_dockerfile_has_no_private_build_target() -> None:
    dockerfile = _dockerfile().lower()
    assert " as private" not in dockerfile
    assert "--target private" not in dockerfile
    assert "cgtlib/private" in dockerfile
    assert "processual_api/private_integrations" in dockerfile
    assert "test ! -d cgtlib/private" in dockerfile
    assert "test ! -d processual_api/private_integrations" in dockerfile


def test_public_dockerfile_copies_complete_public_cgtlib_tree() -> None:
    dockerfile = _dockerfile()
    assert "COPY cgtlib ./cgtlib" in dockerfile
    assert "COPY processual_kernel ./processual_kernel" in dockerfile
    assert "COPY processual_api ./processual_api" in dockerfile


def test_public_docker_workflow_exposes_only_public_image_build() -> None:
    workflow = _docker_workflow().lower()
    assert "public docker build" in workflow
    assert "target: public" in workflow
    assert "private" not in workflow
    assert "processual-maestro-public" in workflow


def test_public_docker_workflow_smokes_private_exclusion_and_fail_closed_behavior() -> None:
    workflow = _docker_workflow()
    assert 'find_spec("cgtlib.private") is None' in workflow
    assert 'find_spec("processual_api.private_integrations") is None' in workflow
    assert "assert cgtlib._HAS_PRIVATE is False" in workflow
    assert "PrivateEvaluationUnavailableError" in workflow
    assert 'assert str(exc) == "private_evaluation_unavailable"' in workflow
    assert "docker image inspect pmk-public-qualification:${{ github.sha }}" in workflow
