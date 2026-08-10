from __future__ import annotations

import re

from processual_api.api_readiness_gate import (
    audit_mounted_routes,
    route_inventory_digest,
    validate_mounted_route_readiness,
)
from processual_api.main import app


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def test_all_mounted_relevant_routes_are_readiness_classified() -> None:
    audit = audit_mounted_routes(app)

    assert audit.duplicate_route_keys == (), audit.to_dict()
    assert audit.unknown_records == (), audit.to_dict()

    # Optional/full-install dependency profiles can legitimately mount different
    # route inventories. The safety boundary is that every mounted relevant route
    # is classified exactly once; the digest remains evidence, not an allow-list.
    assert _SHA256_HEX.fullmatch(audit.inventory_digest), audit.inventory_digest
    assert route_inventory_digest(app) == audit.inventory_digest

    validate_mounted_route_readiness(
        app,
        expected_inventory_digest=audit.inventory_digest,
    )
