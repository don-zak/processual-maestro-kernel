from datetime import UTC, datetime
from decimal import Decimal

from processual_api.billing.maestro_calibration_contracts import (
    CalibrationQuantities,
    MaestroBillingDisposition,
    MaestroFailureOwner,
    MaestroResourceBand,
    MaestroTaskFamily,
)
from processual_api.billing.maestro_shadow_measurements import (
    MaestroShadowMeasurement,
    ShadowMeasurementOutcome,
)
from processual_api.billing.maestro_shadow_store import (
    MaestroShadowMeasurementStore,
)


def make_measurement(
    measurement_id: str = "measure-001",
) -> MaestroShadowMeasurement:
    return MaestroShadowMeasurement(
        measurement_id=measurement_id,
        execution_id="execution-001",
        attempt_id="attempt-001",
        observed_at=datetime(2026, 7, 28, tzinfo=UTC),
        task_family=MaestroTaskFamily.AUTOMATION_EXECUTION,
        outcome=ShadowMeasurementOutcome.COMPLETED,
        quantities=CalibrationQuantities(base_executions=Decimal("1")),
        resource_band=MaestroResourceBand.NORMAL,
        failure_owner=MaestroFailureOwner.NONE,
        disposition=MaestroBillingDisposition.SETTLED,
        duration_ms=Decimal("10"),
    )


def test_store_is_append_only_and_idempotent(tmp_path):
    store = MaestroShadowMeasurementStore(tmp_path / "measurements.jsonl")
    measurement = make_measurement()

    assert store.append(measurement) is True
    assert store.append(measurement) is False

    records = store.records()

    assert len(records) == 1
    assert records[0]["measurement_id"] == "measure-001"


def test_store_reloads_existing_measurement_ids(tmp_path):
    path = tmp_path / "measurements.jsonl"

    first_store = MaestroShadowMeasurementStore(path)
    assert first_store.append(make_measurement()) is True

    second_store = MaestroShadowMeasurementStore(path)
    assert second_store.append(make_measurement()) is False


def test_best_effort_does_not_propagate_storage_error(
    tmp_path,
):
    directory = tmp_path / "directory"
    directory.mkdir()

    store = MaestroShadowMeasurementStore(directory)

    assert store.append_best_effort(make_measurement()) is False


def test_store_ignores_malformed_json_lines(tmp_path):
    path = tmp_path / "measurements.jsonl"
    path.write_text(
        '{"measurement_id":"existing"}\nnot-valid-json\n',
        encoding="utf-8",
    )

    store = MaestroShadowMeasurementStore(path)

    records = store.records()

    assert len(records) == 1
    assert records[0]["measurement_id"] == "existing"
    assert store.append(make_measurement("measure-002")) is True
