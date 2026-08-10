from processual_api.api_readiness_gate import (
    audit_mounted_routes,
    validate_mounted_route_readiness,
)
from processual_api.main import app


def test_all_mounted_relevant_routes_are_readiness_classified() -> None:
    audit = audit_mounted_routes(app)
    assert audit.duplicate_route_keys == (), audit.to_dict()
    assert audit.unknown_records == (), audit.to_dict()
    validate_mounted_route_readiness(app)
