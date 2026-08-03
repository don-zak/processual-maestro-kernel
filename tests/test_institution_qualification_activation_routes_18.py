from __future__ import annotations

import re
from pathlib import Path

ROUTER_PATH = Path("processual_api/routers/institution_qualification_18.py")


def _activation_route_source(source: str) -> str:
    route_start = source.index("def activate_client_qualification_18(")

    next_route = re.search(
        r"\n@router\.",
        source[route_start:],
    )

    if next_route is None:
        return source[route_start:]

    route_end = route_start + next_route.start()
    return source[route_start:route_end]


def test_client_activation_route_contract() -> None:
    source = ROUTER_PATH.read_text(encoding="utf-8")

    route_pattern = re.compile(
        r"""
        @router\.post\(
        \s*
        "/client/integration-cases/
        (?:"\s*")?
        \{case_id\}/qualification/activate"
        \s*
        \)
        """,
        re.VERBOSE,
    )

    assert route_pattern.search(source) is not None
    assert "def activate_client_qualification_18(" in source
    assert "activate_enterprise_qualification(" in source
    assert "owner_user_id != user_id" in source
    assert "case_client_id != client_id" in source


def test_client_activation_route_is_default_deny() -> None:
    source = ROUTER_PATH.read_text(encoding="utf-8")
    route_source = _activation_route_source(source)

    assert '"production_allowed": False' in route_source
    assert '"runtime_connector_approved": False' in route_source
    assert '"write_allowed": False' in route_source
    assert '"restricted_allowed": False' in route_source
    assert '"external_http_allowed": False' in route_source
    assert '"raw_secret_visible": False' in route_source

    # API-key lifecycle names are permitted, but raw credential
    # material and positive secret-return flags remain forbidden.
    assert '"raw_qualification_key_returned": True' not in route_source
    assert '"raw_sandbox_api_key_returned": True' not in route_source
    assert '"raw_secret_visible": True' not in route_source
    assert "qualification_key_raw =" not in route_source
    assert "sandbox_api_key_raw =" not in route_source
    assert "secret_value =" not in route_source
    assert "raw_key" not in route_source
