"""Minimal project-owned HTTPS-sandbox workload for Evaluation qualification.

Cloud Run terminates HTTPS at the service edge and forwards HTTP to this
container. The workload is deliberately anonymous, read-only, deterministic,
and independent from Maestro so it can prove real outbound transport without
borrowing a third-party service's ownership.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

_HOST: Final = "0.0.0.0"
_DEFAULT_PORT: Final = 8080

_CUSTOMER = {
    "id": 1,
    "name": "Evaluation Sandbox Customer",
    "username": "maestro-evaluation",
    "email": "sandbox@example.invalid",
    "phone": "+000-000-0000",
    "website": "example.invalid",
    "company": {"name": "Processual Maestro Evaluation Sandbox"},
    "address": {
        "street": "Qualification Lane",
        "suite": "Read Only",
        "city": "Sandbox",
        "zipcode": "00000",
    },
}


class EvaluationSandboxHandler(BaseHTTPRequestHandler):
    server_version = "MaestroEvaluationSandbox/1"

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = self.path.split("?", 1)[0]
        if path == "/health/live":
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "live",
                    "service": "processual-maestro-evaluation-sandbox",
                    "production_allowed": False,
                },
            )
            return
        if path == "/users/1":
            self._write_json(HTTPStatus.OK, dict(_CUSTOMER))
            return
        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"detail": "not_found", "production_allowed": False},
        )

    def do_POST(self) -> None:  # noqa: N802 - explicit fail-closed mutation surface
        self._write_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"detail": "read_only_sandbox", "production_allowed": False},
        )

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, format: str, *args: object) -> None:
        # Avoid request payload/header logging. Cloud Run still captures the
        # standard service/request metadata at the platform edge.
        del format, args


def main() -> None:
    port = int(os.environ.get("PORT", str(_DEFAULT_PORT)))
    server = ThreadingHTTPServer((_HOST, port), EvaluationSandboxHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
