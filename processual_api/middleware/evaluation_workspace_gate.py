"""Fail-closed access gate for the standalone External Evaluation workspace."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from processual_api.services.evaluation_launch_gate import (
    EVALUATION_LAUNCH_COOKIE,
    EVALUATION_LAUNCH_QUERY_PARAM,
    EVALUATION_WORKSPACE_SESSION_TTL_SECONDS,
    EvaluationLaunchGateError,
    redeem_evaluation_launch_ticket,
    validate_evaluation_workspace_session,
)

_EXTERNAL_EVALUATION_WORKSPACE_PATH = "/console/evaluation.html"


class EvaluationWorkspaceGateMiddleware(BaseHTTPMiddleware):
    """Require a zaxam.net iframe context plus a valid launch session.

    The launch ticket is one-time. Redemption creates only a workspace-access
    cookie; Evaluation API execution still requires the separately issued
    supervisor Evaluation API key.
    """

    @staticmethod
    def _is_iframe_navigation(request: Request) -> bool:
        return request.headers.get("sec-fetch-dest", "").strip().lower() == "iframe"

    async def dispatch(self, request: Request, call_next):
        if request.url.path != _EXTERNAL_EVALUATION_WORKSPACE_PATH:
            return await call_next(request)

        if request.method.upper() != "GET":
            return PlainTextResponse("External Evaluation workspace access denied.", status_code=405)

        # A workspace session is intentionally not sufficient for top-level
        # navigation. The surface remains a zaxam.net-embedded workspace; CSP
        # frame-ancestors provides the browser-enforced ancestor allow-list.
        if not self._is_iframe_navigation(request):
            return PlainTextResponse("External Evaluation workspace access denied.", status_code=403)

        launch_ticket = str(request.query_params.get(EVALUATION_LAUNCH_QUERY_PARAM) or "").strip()
        if launch_ticket:
            try:
                session_token, _session = await redeem_evaluation_launch_ticket(launch_ticket)
            except EvaluationLaunchGateError:
                return PlainTextResponse("External Evaluation launch expired or invalid.", status_code=403)

            # Remove the one-time ticket from the visible URL immediately.
            response = RedirectResponse(url=_EXTERNAL_EVALUATION_WORKSPACE_PATH, status_code=303)
            response.set_cookie(
                EVALUATION_LAUNCH_COOKIE,
                session_token,
                max_age=EVALUATION_WORKSPACE_SESSION_TTL_SECONDS,
                httponly=True,
                secure=True,
                samesite="none",
                path=_EXTERNAL_EVALUATION_WORKSPACE_PATH,
            )
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        session_token = str(request.cookies.get(EVALUATION_LAUNCH_COOKIE) or "").strip()
        if not session_token:
            return PlainTextResponse("External Evaluation workspace launch required.", status_code=403)
        try:
            await validate_evaluation_workspace_session(session_token)
        except EvaluationLaunchGateError:
            response = PlainTextResponse("External Evaluation workspace session expired.", status_code=403)
            response.delete_cookie(EVALUATION_LAUNCH_COOKIE, path=_EXTERNAL_EVALUATION_WORKSPACE_PATH)
            return response

        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


__all__ = ["EvaluationWorkspaceGateMiddleware"]
