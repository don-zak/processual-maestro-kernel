from processual_api.api_readiness_gate import (
    audit_mounted_routes,
    validate_mounted_route_readiness,
)
from processual_api.main import app


APPROVED_ROUTE_INVENTORY_DIGEST = "capture-from-ci"


def test_all_mounted_relevant_routes_are_readiness_classified() -> None:
    audit = audit_mounted_routes(app)
    assert audit.duplicate_route_keys == (), audit.to_dict()
    assert audit.unknown_records == (), audit.to_dict()
    assert audit.inventory_digest == APPROVED_ROUTE_INVENTORY_DIGEST, audit.inventory_digest
    validate_mounted_route_readiness(
        app,
        expected_inventory_digest=APPROVED_ROUTE_INVENTORY_DIGEST,
    )
