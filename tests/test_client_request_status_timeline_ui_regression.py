from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _requests_html() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    start = html.index("set-client-request-latest-summary")
    end = html.index("set-client-request-history")
    return html[start:end]


def test_client_request_status_timeline_markup_is_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "set-client-request-latest-summary" in html
    assert "set-client-request-timeline" in html
    assert "set-client-request-next-action" in html
    assert "Latest request summary will appear" in html
    assert "Request status timeline will appear" in html
    assert "Next safe client action will appear" in html


def test_client_request_status_timeline_runtime_is_bound() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    required = (
        "function clientRequestStatusLabel",
        "function clientRequestStatusRank",
        "function clientRequestStatusStages",
        "function latestClientRequest",
        "function clientRequestSummaryLine",
        "function renderClientRequestStatusTimeline",
        "function clientRequestNextSafeAction",
        "set-client-request-latest-summary",
        "set-client-request-timeline",
        "set-client-request-next-action",
    )
    for marker in required:
        assert marker in js


def test_client_request_status_timeline_supports_statuses() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    for status in ("pending", "reviewed", "approved", "rejected", "completed"):
        assert status in js

    assert "Pending admin review" in js
    assert "Admin review started" in js
    assert "Approved for follow-up" in js
    assert "Rejected or needs revision" in js
    assert "Completed" in js


def test_client_request_status_timeline_stays_client_safe() -> None:
    requests_html = _requests_html()

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/admin",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in requests_html

    js = SETTINGS_JS.read_text(encoding="utf-8")
    assert "/settings/client-request" in js
    assert "/settings/client-requests" in js

def test_client_request_status_timeline_updates_on_successful_load() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "clientRequestSummaryLine(latestClientRequest(latest))" in js
    assert "renderClientRequestStatusTimeline(latest)" in js
    assert "clientRequestNextSafeAction(latest)" in js
    assert "renderClientRequests(latest)" in js

    success_summary_index = js.index("clientRequestSummaryLine(latestClientRequest(latest))")
    history_index = js.index("renderClientRequests(latest)")
    assert success_summary_index < history_index
