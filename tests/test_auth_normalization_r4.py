from __future__ import annotations

import pytest

from processual_api.auth.normalization import (
    normalize_display_name,
    normalize_email,
    organization_slug,
)


def test_email_normalization_is_casefolded_and_idna_safe() -> None:
    assert normalize_email("  User@EXAMPLE.com ") == "user@example.com"
    assert normalize_email("User@bücher.example") == "user@xn--bcher-kva.example"


@pytest.mark.parametrize("value", ("missing-at", "a@@example.com", "@example.com", "a@localhost"))
def test_invalid_email_structures_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_email(value)


def test_display_names_and_organization_slugs_are_bounded() -> None:
    assert normalize_display_name("  Example   Owner  ") == "Example Owner"
    assert organization_slug("Example Telecom", suffix="A1B2C3D4") == "example-telecom-a1b2c3d4"
    assert organization_slug("شركة اتصالات", suffix="abcdef12") == "organization-abcdef12"


def test_short_slug_suffix_is_rejected() -> None:
    with pytest.raises(ValueError):
        organization_slug("Example", suffix="123")
