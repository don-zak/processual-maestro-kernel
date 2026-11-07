from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "processual_api" / "cgt_governor" / "adapters" / "registry.py"


def test_adapter_discovery_does_not_log_raw_exception_text():
    text = REGISTRY.read_text(encoding="utf-8")

    assert 'logger.warning("Failed to register %s: %s", adapter_cls.__name__, exc)' not in text
    assert '"Adapter registration failed: provider=%s reason=%s"' in text
    assert "type(exc).__name__" in text
