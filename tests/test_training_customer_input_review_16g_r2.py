from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from types import MappingProxyType

import pytest

from processual_api.integrations.training_connection_request import (
    build_training_customer_input_package,
)
from processual_api.integrations.training_customer_input_review import (
    TrainingCustomerInputReview,
    TrainingCustomerInputReviewStatus,
    TrainingCustomerInputSubmission,
    review_training_customer_input_submission,
)

REQUEST_ID = "telecom_ticketing_training_connection_request"


def _values() -> dict[str, str]:
    package = build_training_customer_input_package(REQUEST_ID)
    values = {
        item.item_id: f"training_{item.item_id.replace('.', '_')}_ref"
        for item in package.items
    }
    values["provider.selected_secret_provider"] = "gcp_secret_manager"
    values["outbound.tls_minimum_version_selection"] = "tls_1_2"
    return values


def _submission(
    values: dict[str, str],
) -> TrainingCustomerInputSubmission:
    return TrainingCustomerInputSubmission(
        submission_id="training_customer_submission",
        request_id=REQUEST_ID,
        values=values,
    )


def test_models_are_frozen_slotted_dataclasses() -> None:
    for model in (
        TrainingCustomerInputSubmission,
        TrainingCustomerInputReview,
    ):
        assert is_dataclass(model)
        assert "__slots__" in model.__dict__


def test_submission_copies_values_to_immutable_mapping() -> None:
    source = _values()
    submission = _submission(source)

    assert isinstance(submission.values, MappingProxyType)
    assert len(submission.values) == 27

    source["provider.provider_reference"] = "changed_after_creation"

    assert submission.values["provider.provider_reference"] != (
        "changed_after_creation"
    )

    with pytest.raises(TypeError):
        submission.values["forged"] = "forged"  # type: ignore[index]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        submission.request_id = "forged"


def test_missing_input_needs_clarification() -> None:
    values = _values()
    values.pop("outbound.kill_switch_reference")

    review = review_training_customer_input_submission(
        _submission(values)
    )

    assert review.status is (
        TrainingCustomerInputReviewStatus.NEEDS_CLARIFICATION
    )
    assert review.missing_input_ids == (
        "outbound.kill_switch_reference",
    )
    assert review.schema_valid is False
    assert review.ready_for_supervisor_review is False


def test_unexpected_input_is_blocked() -> None:
    values = _values()
    values["outbound.forged_reference"] = "training_forged_ref"

    review = review_training_customer_input_submission(
        _submission(values)
    )

    assert review.status is TrainingCustomerInputReviewStatus.BLOCKED
    assert review.unexpected_input_ids == (
        "outbound.forged_reference",
    )
    assert review.ready_for_supervisor_review is False


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("provider.selected_secret_provider", "unsupported_provider"),
        (
            "outbound.tls_minimum_version_selection",
            "unsupported_tls",
        ),
    ),
)
def test_invalid_selection_is_rejected(
    field_name: str,
    value: str,
) -> None:
    values = _values()
    values[field_name] = value

    review = review_training_customer_input_submission(
        _submission(values)
    )

    assert review.status is (
        TrainingCustomerInputReviewStatus.REJECTED_UNSAFE_INPUT
    )
    assert review.ready_for_supervisor_review is False


@pytest.mark.parametrize(
    "value",
    (
        "https://operator.invalid",
        "password=forged",
        "token=forged",
        "secret=forged",
        "private_key=forged",
        "api_key=forged",
        "raw_payload=forged",
    ),
)
def test_raw_material_is_rejected_at_submission_creation(
    value: str,
) -> None:
    values = _values()
    values["provider.provider_reference"] = value

    with pytest.raises(ValueError, match="prohibited raw material"):
        _submission(values)


@pytest.mark.parametrize(
    ("provider", "tls_version"),
    (
        ("gcp_secret_manager", "tls_1_2"),
        ("hashicorp_vault", "tls_1_3"),
        ("aws_secrets_manager", "tls_1_2"),
        ("azure_key_vault", "tls_1_3"),
    ),
)
def test_complete_package_is_ready_for_supervisor_review(
    provider: str,
    tls_version: str,
) -> None:
    values = _values()
    values["provider.selected_secret_provider"] = provider
    values["outbound.tls_minimum_version_selection"] = tls_version

    review = review_training_customer_input_submission(
        _submission(values)
    )

    assert review.status is (
        TrainingCustomerInputReviewStatus.READY_FOR_SUPERVISOR_REVIEW
    )
    assert review.expected_input_count == 27
    assert review.received_input_count == 27
    assert review.missing_input_ids == ()
    assert review.unexpected_input_ids == ()
    assert review.schema_valid is True
    assert review.provider_submission_valid is True
    assert review.outbound_submission_valid is True
    assert review.ready_for_supervisor_review is True
    assert review.customer_submission_persisted is False
    assert review.integration_task_created is False
    assert review.activation_permission_key_issued is False
    assert review.provider_binding_created is False
    assert review.credentials_resolved is False
    assert review.connection_attempted is False
    assert review.fake_transport_invoked is False
    assert review.sandbox_launched is False
    assert review.external_http_enabled is False
    assert review.socket_access_enabled is False
    assert review.runtime_enabled is False
    assert review.production_allowed is False


def test_wrong_submission_type_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="TrainingCustomerInputSubmission",
    ):
        review_training_customer_input_submission(
            "forged"  # type: ignore[arg-type]
        )


def test_review_is_deterministic() -> None:
    submission = _submission(_values())

    first = review_training_customer_input_submission(submission)
    second = review_training_customer_input_submission(submission)

    assert first == second
    assert hash(first) == hash(second)
def test_package_exports_16g_r2_surface() -> None:
    import processual_api.integrations as package

    expected = {
        "TrainingCustomerInputReview",
        "TrainingCustomerInputReviewStatus",
        "TrainingCustomerInputSubmission",
        "review_training_customer_input_submission",
    }

    assert expected.issubset(set(package.__all__))

    for name in expected:
        assert getattr(package, name) is not None


def test_16g_r2_documentation_records_review_boundary() -> None:
    from pathlib import Path

    document = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16G_R2.md"
    ).read_text(encoding="utf-8")
    lowered = document.lower()

    for marker in (
        "ready_for_supervisor_review",
        "needs_clarification",
        "rejected_unsafe_input",
        "27 reference inputs",
        "secretproviderreferencesubmission",
        "outboundallowlisttlsreferencesubmission",
        "customer_submission_persisted",
        "integration_task_created",
        "activation_permission_key_issued",
        "fake_transport_invoked",
        "sandbox_launched",
        "external_http_enabled",
        "socket_access_enabled",
        "runtime_enabled",
        "production_allowed",
        "parallel key system",
    ):
        assert marker in lowered
