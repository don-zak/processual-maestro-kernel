from __future__ import annotations

from pathlib import Path

ROUTER_PATH = Path(
    "processual_api/routers/"
    "institution_qualification_18.py"
)


def test_client_activation_route_contract() -> None:
    source = ROUTER_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        '"/client/integration-cases/"\n'
        '    "{case_id}/qualification/activate"'
    ) in source

    assert (
        "def activate_client_qualification_18("
    ) in source

    assert (
        "activate_enterprise_qualification("
    ) in source

    assert (
        "owner_user_id != user_id"
    ) in source

    assert (
        "case_client_id != client_id"
    ) in source


def test_client_activation_route_is_default_deny() -> None:
    source = ROUTER_PATH.read_text(
        encoding="utf-8"
    )

    route_start = source.index(
        "def activate_client_qualification_18("
    )

    route_end = source.index(
        '@router.get(\n'
        '    "/client/integration-cases/'
        '{case_id}/task-credentials"',
        route_start,
    )

    route_source = source[
        route_start:route_end
    ]

    assert '"production_allowed": False' in route_source
    assert (
        '"runtime_connector_approved": False'
        in route_source
    )
    assert '"write_allowed": False' in route_source
    assert '"restricted_allowed": False' in route_source
    assert '"external_http_allowed": False' in route_source
    assert '"raw_secret_visible": False' in route_source
    # API-key lifecycle state names are permitted. Raw credential
    # material and positive secret-return flags remain forbidden.
    assert '"raw_qualification_key_returned": True' not in route_source
    assert '"raw_sandbox_api_key_returned": True' not in route_source
    assert '"raw_secret_visible": True' not in route_source
    assert "qualification_key_raw =" not in route_source
    assert "sandbox_api_key_raw =" not in route_source
    assert "secret_value =" not in route_source
    assert "raw_key" not in route_source
