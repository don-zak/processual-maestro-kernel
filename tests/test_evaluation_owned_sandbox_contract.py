from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "deployment" / "evaluation-owned-sandbox" / "app.py"
DOCKERFILE_PATH = ROOT / "deployment" / "evaluation-owned-sandbox" / "Dockerfile"
README_PATH = ROOT / "deployment" / "evaluation-owned-sandbox" / "README.md"


def _load_sandbox_module():
    spec = importlib.util.spec_from_file_location("evaluation_owned_sandbox", APP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request(url: str, *, method: str = "GET") -> tuple[int, dict]:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_owned_sandbox_serves_deterministic_read_only_http_contract() -> None:
    sandbox = _load_sandbox_module()
    server = sandbox.ThreadingHTTPServer(("127.0.0.1", 0), sandbox.EvaluationSandboxHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, health = _request(f"{base}/health/live")
        assert status == 200
        assert health == {
            "production_allowed": False,
            "service": "processual-maestro-evaluation-sandbox",
            "status": "live",
        }

        status, customer = _request(f"{base}/users/1")
        assert status == 200
        assert customer["id"] == 1
        assert customer["username"] == "maestro-evaluation"
        assert customer["company"]["name"] == "Processual Maestro Evaluation Sandbox"

        status, rejected = _request(f"{base}/users/1", method="POST")
        assert status == 405
        assert rejected == {
            "detail": "read_only_sandbox",
            "production_allowed": False,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_owned_sandbox_container_and_deployment_contract_are_explicit() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")

    assert "FROM python:3.14-slim" in dockerfile
    assert "USER sandbox" in dockerfile
    assert 'CMD ["python", "/app/app.py"]' in dockerfile
    assert "--allow-unauthenticated" in readme
    assert "--port 8080" in readme
    assert "project-owned URL" in readme
    assert "third-party endpoint is not sufficient" in readme
