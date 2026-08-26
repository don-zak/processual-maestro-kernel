from __future__ import annotations

import hashlib

from tools import release_evidence_inventory as inventory


def test_release_inventory_binds_source_artifacts_and_license_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "processual_maestro_kernel-2.0.0-py3-none-any.whl"
    artifact.write_bytes(b"wheel-artifact")

    monkeypatch.setattr(inventory, "_source_sha", lambda: "a" * 40)
    monkeypatch.setattr(
        inventory,
        "_installed_packages",
        lambda: [
            {
                "name": "example",
                "version": "1.0",
                "license_expression": "MIT",
                "license": None,
            }
        ],
    )

    result = inventory.build_inventory(tmp_path)

    assert result["schema_version"] == "pmk-release-evidence-inventory-v1"
    assert result["source_sha"] == "a" * 40
    assert result["artifacts"] == [
        {
            "filename": artifact.name,
            "sha256": hashlib.sha256(b"wheel-artifact").hexdigest(),
            "size_bytes": len(b"wheel-artifact"),
        }
    ]
    assert result["installed_packages"][0]["license_expression"] == "MIT"
    assert "not a CycloneDX/SPDX SBOM" in result["inventory_scope"]
