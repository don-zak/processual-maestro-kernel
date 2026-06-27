from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def _json_default(obj: Any):
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


class AdaptiveJsonStore:
    """Small JSON/JSONL persistence helper for adaptive governance artifacts.

    The store is append-only for histories and reports. It is not a kernel database and it never changes runtime
    decisions by itself; it simply preserves evidence for replay, audits, patch history, and strategy memory.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, artifact: Any) -> Path:
        path = self.root / f"{kind}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(artifact, ensure_ascii=False, default=_json_default) + "\n")
        return path

    def append_many(self, kind: str, artifacts: Iterable[Any]) -> Path:
        path = self.root / f"{kind}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            for artifact in artifacts:
                f.write(json.dumps(artifact, ensure_ascii=False, default=_json_default) + "\n")
        return path

    def list_records(self, kind: str) -> tuple[dict[str, Any], ...]:
        path = self.root / f"{kind}.jsonl"
        if not path.exists():
            return ()
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return tuple(records)

    def save_snapshot(self, name: str, artifact: Any) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        return path

    def load_snapshot(self, name: str) -> dict[str, Any]:
        path = self.root / f"{name}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
