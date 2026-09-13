from __future__ import annotations

import logging

from processual_api.cgt_governor.adapters import registry as registry_module


def test_adapter_discovery_logs_exception_type_without_exception_text(monkeypatch, caplog):
    secret_marker = "provider-secret-should-not-appear"

    class FailingAdapter:
        def __init__(self):
            raise RuntimeError(secret_marker)

    monkeypatch.setattr(registry_module, "OpenAIAdapter", FailingAdapter, raising=False)

    # discover imports adapter classes inside the method, so intercept the register path
    # by replacing one imported class through a temporary module-level import shim.
    original_import = __import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        module = original_import(name, globals, locals, fromlist, level)
        if name.endswith("openai_adapter") and hasattr(module, "OpenAIAdapter"):
            monkeypatch.setattr(module, "OpenAIAdapter", FailingAdapter)
        return module

    monkeypatch.setattr("builtins.__import__", guarded_import)

    registry = registry_module.LLMAdapterRegistry()
    with caplog.at_level(logging.WARNING, logger="maestro.adapters"):
        registry.discover()

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "OpenAIAdapter" not in rendered or "FailingAdapter" in rendered
    assert "RuntimeError" in rendered
    assert secret_marker not in rendered
