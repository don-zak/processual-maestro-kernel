from processual_api.api_readiness_gate import (
    audit_mounted_routes,
    validate_mounted_route_readiness,
)
from processual_api.main import app


APPROVED_ROUTE_INVENTORY_DIGESTS = {
    # Minimal dependency profile used by the focused Stage B1 CI gate.
    "bf8be19563df11aa0798d65d38aa21b5da0580eac14355bdd82dcf94fbdb79d4",
    # Full-install dependency profile exercised by the local whole-program gate.
    "193d12034d7c32bbd34f08f7839e60ffc880507ea7b01639d78d880f2376a513",
}


def test_all_mounted_relevant_routes_are_readiness_classified() -> None:
    audit = audit_mounted_routes(app)
    assert audit.duplicate_route_keys == (), audit.to_dict()
    assert audit.unknown_records == (), audit.to_dict()
    assert audit.inventory_digest in APPROVED_ROUTE_INVENTORY_DIGESTS, audit.inventory_digest
    validate_mounted_route_readiness(
        app,
        expected_inventory_digest=audit.inventory_digest,
    )
