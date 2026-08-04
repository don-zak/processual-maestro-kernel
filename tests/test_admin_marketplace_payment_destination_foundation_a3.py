import pytest

from processual_api.admin_marketplace.authority import (
    PLATFORM_ADMIN_AUTHORITY,
    AdminMarketplaceAction,
    authority_context,
    evaluate_admin_marketplace_authority,
)
from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationType,
    mask_payment_identifier,
    normalize_payment_identifier,
    validate_payment_destination_identifier,
)
from processual_api.admin_marketplace.payment_destination_crypto import (
    EncryptedPaymentDestinationIdentifier,
    PaymentDestinationCipher,
)


def _cipher() -> PaymentDestinationCipher:
    return PaymentDestinationCipher(
        current_key_version="payment-v1",
        keys={"payment-v1": b"p" * 32},
    )


def test_normalize_payment_identifier_removes_formatting() -> None:
    assert (
        normalize_payment_identifier("tn59 1000-6035 1835 9847 8831")
        == "TN5910006035183598478831"
    )


def test_mask_payment_identifier_exposes_suffix_only() -> None:
    masked = mask_payment_identifier("TN5910006035183598478831")

    assert masked.endswith("8831")
    assert "TN59100060351835" not in masked


def test_bank_destination_requires_sufficient_length() -> None:
    result = validate_payment_destination_identifier(
        value="12345678",
        destination_type=PaymentDestinationType.BANK_ACCOUNT,
    )

    assert result.valid is False
    assert result.reason_code == "identifier_length_invalid"


def test_postal_destination_can_validate_structurally() -> None:
    result = validate_payment_destination_identifier(
        value="POST123456789",
        destination_type=PaymentDestinationType.POSTAL_ACCOUNT,
    )

    assert result.valid is True
    assert result.reason_code == "structurally_validated"
    assert result.masked_identifier is not None


def test_payment_destination_cipher_round_trip() -> None:
    cipher = _cipher()

    encrypted = cipher.encrypt(
        "TN5910006035183598478831",
        payment_destination_id="destination-1",
        destination_ref="main-bank",
    )

    assert b"TN5910006035183598478831" not in encrypted.ciphertext
    assert (
        cipher.decrypt(
            encrypted,
            payment_destination_id="destination-1",
            destination_ref="main-bank",
        )
        == "TN5910006035183598478831"
    )


def test_payment_destination_cipher_rejects_authority_substitution() -> None:
    cipher = _cipher()
    encrypted = cipher.encrypt(
        "TN5910006035183598478831",
        payment_destination_id="destination-1",
        destination_ref="main-bank",
    )

    with pytest.raises(
        ValueError,
        match="ciphertext authentication failed",
    ):
        cipher.decrypt(
            encrypted,
            payment_destination_id="destination-2",
            destination_ref="main-bank",
        )


def test_payment_destination_cipher_rejects_unknown_key_version() -> None:
    cipher = _cipher()

    with pytest.raises(ValueError, match="key is unavailable"):
        cipher.decrypt(
            EncryptedPaymentDestinationIdentifier(
                ciphertext=b"x" * 32,
                key_version="missing",
            ),
            payment_destination_id="destination-1",
            destination_ref="main-bank",
        )


@pytest.mark.parametrize(
    "action",
    [
        AdminMarketplaceAction.CREATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.VALIDATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.ACTIVATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.DEACTIVATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.SET_DEFAULT_PAYMENT_DESTINATION,
    ],
)
def test_payment_destination_actions_require_recent_mfa(action) -> None:
    context = authority_context(
        user_id="user-1",
        session_id="session-1",
        platform_authorities={PLATFORM_ADMIN_AUTHORITY},
        active_platform_admin=True,
        recent_mfa_step_up=False,
    )

    decision = evaluate_admin_marketplace_authority(
        context=context,
        action=action,
    )

    assert decision.allowed is False
    assert decision.step_up_required is True
    assert decision.reason_code == "recent_mfa_step_up_required"


@pytest.mark.parametrize(
    "action",
    [
        AdminMarketplaceAction.CREATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.VALIDATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.ACTIVATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.DEACTIVATE_PAYMENT_DESTINATION,
        AdminMarketplaceAction.SET_DEFAULT_PAYMENT_DESTINATION,
    ],
)
def test_payment_destination_actions_allow_recent_platform_admin_mfa(
    action,
) -> None:
    context = authority_context(
        user_id="user-1",
        session_id="session-1",
        platform_authorities={PLATFORM_ADMIN_AUTHORITY},
        active_platform_admin=True,
        recent_mfa_step_up=True,
    )

    decision = evaluate_admin_marketplace_authority(
        context=context,
        action=action,
    )

    assert decision.allowed is True
    assert decision.step_up_required is True
    assert decision.reason_code == "super_administrator_authorized"
