from __future__ import annotations

import json
import logging
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("processual_api.cgt_governor.data.telemetry")


class JsonlTelemetryStore:
    """Persistent telemetry log backed by a JSONL file.

    Appends each telemetry point to a JSONL file for durability.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        maxlen: int = 50000,
    ) -> None:
        if path is None:
            base = Path(__file__).resolve().parent.parent.parent / "data"
            base.mkdir(parents=True, exist_ok=True)
            path = base / "telemetry.jsonl"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._maxlen = maxlen
        self._buffer: deque[dict] = deque(maxlen=maxlen)
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._path.exists():
            logger.info("No existing telemetry log at %s, starting fresh", self._path)
            return
        count = 0
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._buffer.append(json.loads(line))
                            count += 1
                        except json.JSONDecodeError:
                            pass
        except Exception as exc:
            logger.warning("Failed to load telemetry log: %s", exc)
        logger.info("Loaded %d existing telemetry points from %s", count, self._path)

    def ingest(self, metric: str, value: float, labels: dict[str, str] | None = None) -> None:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "metric": metric,
            "value": value,
            "labels": labels or {},
        }
        self._buffer.append(entry)
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            logger.error("Failed to persist telemetry point: %s", exc)

    @property
    def entries(self) -> list[dict]:
        return list(self._buffer)

    def query(
        self,
        metric: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        results = self._buffer
        if metric:
            results = deque((e for e in results if e.get("metric") == metric), maxlen=self._maxlen)
        if since:
            results = deque((e for e in results if e.get("ts", "") >= since), maxlen=self._maxlen)
        return list(results)[-limit:]

    def clear(self) -> None:
        self._buffer.clear()
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass

    @property
    def path(self) -> Path:
        return self._path

    def __len__(self) -> int:
        return len(self._buffer)


telemetry_store = JsonlTelemetryStore()
