from __future__ import annotations

from tools.dependency_license_review import (
    SCHEMA_VERSION,
    build_dependency_license_review,
)


def test_dependency_license_review_is_deterministic_and_non_authoritative() -> None:
    review = build_dependency_license_review()

    assert review["schema_version"] == SCHEMA_VERSION
    assert review["summary"]["package_count"] == len(review["packages"])
    assert review["summary"]["packages_missing_license_metadata"] == len(
        review["missing_license_metadata"]
    )
    assert "does not make a legal compatibility determination" in review["review_scope"]

    identities = [(item["name"].lower(), item["version"]) for item in review["packages"]]
    assert identities == sorted(identities)
    for package in review["packages"]:
        assert set(package) == {
            "name",
            "version",
            "license_expression",
            "license",
            "license_classifiers",
            "metadata_declared",
        }
        assert isinstance(package["metadata_declared"], bool)
