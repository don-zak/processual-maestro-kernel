from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from processual_api.billing.maestro_shadow_measurements import (
    MaestroShadowMeasurement,
)

logger = logging.getLogger("processual_api.billing.maestro_shadow_store")


class MaestroShadowMeasurementStore:
    """Append-only, idempotent shadow measurement store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._measurement_ids: set[str] = set()
        self._load_measurement_ids()

    @property
    def path(self) -> Path:
        return self._path

    def append(
        self,
        measurement: MaestroShadowMeasurement,
    ) -> bool:
        """Append once.

        Returns True when written and False when the measurement id
        already exists.
        """

        record = measurement.to_dict()

        with self._lock:
            if measurement.measurement_id in self._measurement_ids:
                return False

            self._path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self._path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )
                handle.flush()

            self._measurement_ids.add(measurement.measurement_id)
            return True

    def append_best_effort(
        self,
        measurement: MaestroShadowMeasurement,
    ) -> bool:
        """Record without propagating storage failures to runtime."""

        try:
            return self.append(measurement)
        except OSError:
            logger.exception("Failed to persist Maestro shadow measurement.")
            return False

    def records(self) -> tuple[dict[str, Any], ...]:
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.exception("Failed to read Maestro shadow measurements.")
            return ()

        records: list[dict[str, Any]] = []

        for line in lines:
            if not line.strip():
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(value, dict):
                records.append(value)

        return tuple(records)

    def _load_measurement_ids(self) -> None:
        for record in self.records():
            measurement_id = record.get("measurement_id")

            if isinstance(measurement_id, str):
                self._measurement_ids.add(measurement_id)
