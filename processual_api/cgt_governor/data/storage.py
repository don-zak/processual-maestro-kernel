from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from collections import deque
from pathlib import Path
from typing import Any

logger = logging.getLogger("processual_api.cgt_governor.data.storage")


class JsonlEvaluationStore:
    """Persistent evaluation log backed by a JSONL file.

    Maintains an in-memory deque (maxlen) for fast access and appends
    each new entry to a JSONL file for durability across restarts.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        maxlen: int = 10000,
    ) -> None:
        if path is None:
            base = Path(__file__).resolve().parent.parent.parent / "data"
            base.mkdir(parents=True, exist_ok=True)
            path = base / "governance_runs.jsonl"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._maxlen = maxlen
        self._buffer: deque[dict] = deque(maxlen=maxlen)
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._path.exists():
            logger.info("No existing evaluation log at %s, starting fresh", self._path)
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
                            logger.warning("Skipping malformed JSONL line")
        except Exception as exc:
            logger.warning("Failed to load evaluation log: %s", exc)
        logger.info("Loaded %d existing evaluations from %s", count, self._path)

    @staticmethod
    def _generate_eval_id() -> str:
        now = datetime.datetime.now(datetime.UTC)
        ts = now.strftime("%Y%m%d_%H%M%S")
        seed = f"{now.timestamp()}-{id(now)}"
        suffix = hashlib.md5(seed.encode()).hexdigest()[:6]
        return f"eval_{ts}_{suffix}"

    def append(self, entry: dict | str) -> None:
        if isinstance(entry, str):
            entry = json.loads(entry)
        if "eval_id" not in entry:
            entry["eval_id"] = self._generate_eval_id()
        self._buffer.append(entry)
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            logger.error("Failed to persist evaluation: %s", exc)

    def extend(self, entries: list[dict]) -> None:
        for entry in entries:
            self.append(entry)

    @property
    def entries(self) -> list[dict]:
        return list(self._buffer)

    def __len__(self) -> int:
        return len(self._buffer)

    def __getitem__(self, index: int) -> dict:
        return self._buffer[index]

    def clear(self) -> None:
        self._buffer.clear()
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass

    @property
    def path(self) -> Path:
        return self._path


# Global instance — imported and used by the router
eval_store = JsonlEvaluationStore()
