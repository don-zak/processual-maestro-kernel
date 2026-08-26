from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def describe(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        item_keys = sorted(
            {
                str(key)
                for item in value
                if isinstance(item, dict)
                for key in item.keys()
            }
        )
        return {
            "ok": True,
            "root": "ARRAY",
            "count": len(value),
            "item_keys": item_keys,
            "top_keys": [],
        }
    if isinstance(value, dict):
        return {
            "ok": True,
            "root": "OBJECT",
            "count": None,
            "item_keys": [],
            "top_keys": sorted(str(key) for key in value.keys()),
        }
    return {
        "ok": True,
        "root": "SCALAR",
        "count": None,
        "item_keys": [],
        "top_keys": [],
    }


def validate(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except Exception as exc:  # evidence tool must report, not crash
        return {"ok": False, "error": str(exc)}
    return describe(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate JSON and report root metadata.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    results = []
    for path in args.paths:
        result = validate(path)
        result["path"] = str(path)
        results.append(result)

    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(item.get("ok") for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
