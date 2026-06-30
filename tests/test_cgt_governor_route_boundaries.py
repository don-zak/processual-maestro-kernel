from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CGT_GOVERNOR_PATH = ROOT / "processual_api" / "routers" / "cgt_governor.py"

SOURCE = CGT_GOVERNOR_PATH.read_text(encoding="utf-8")


def _function_block(function_name: str) -> str:
    marker = f"async def {function_name}"
    start = SOURCE.index(marker)
    next_route = SOURCE.find("\n@router.", start + len(marker))
    if next_route == -1:
        return SOURCE[start:]
    return SOURCE[start:next_route]


def test_primary_govern_route_requires_evaluation_quota():
    assert '@router.post("/cgt/govern")' in SOURCE

    block = _function_block("govern")

    assert 'Depends(require_quota("evaluation"))' in block
    assert "Depends(get_current_user)" not in block


def test_governor_core_routes_remain_authenticated():
    expectations = [
        ('@router.post("/cgt/govern/batch")', "govern_batch"),
        ('@router.get("/cgt/govern/status")', "governor_status"),
        ('@router.post("/cgt/govern/toggle")', "governor_toggle"),
        ('@router.get("/cgt/govern/metrics")', "governor_metrics"),
        ('@router.get("/cgt/govern/reports")', "governor_reports"),
        ('@router.get("/cgt/govern/reports/export")', "export_reports_json"),
        ('@router.post("/cgt/govern/repair")', "generate_repair"),
        ('@router.post("/cgt/govern/auto-repair")', "auto_repair"),
        ('@router.post("/cgt/govern/compare")', "compare_adapters"),
        ('@router.post("/cgt/govern/report")', "govern_report"),
        ('@router.post("/cgt/analyze")', "analyze"),
    ]

    for route_marker, function_name in expectations:
        assert route_marker in SOURCE
        assert "Depends(get_current_user)" in _function_block(function_name)


def test_report_and_pdf_routes_remain_authenticated():
    expectations = [
        ('@router.get("/cgt/govern/reports/pdf")', "governor_reports_pdf"),
        ('@router.get("/cgt/govern/reports/{eval_id}/pdf")', "governor_eval_pdf"),
        ('@router.post("/cgt/govern/simulate")', "run_simulation"),
        ('@router.get("/cgt/govern/simulate/reports")', "list_simulations"),
        ('@router.get("/cgt/govern/simulate/reports/{sim_id}/pdf")', "simulation_pdf"),
    ]

    for route_marker, function_name in expectations:
        assert route_marker in SOURCE
        assert "Depends(get_current_user)" in _function_block(function_name)


def test_gateway_routes_remain_authenticated():
    expectations = [
        ('@router.post("/cgt/govern/gateway/evaluate")', "gateway_evaluate"),
        ('@router.get("/cgt/govern/gateway/agents")', "gateway_list_agents"),
        ('@router.post("/cgt/govern/gateway/agents")', "gateway_register_agent"),
        ('@router.get("/cgt/govern/gateway/agents/{agent_id}")', "gateway_get_agent"),
        ('@router.post("/cgt/govern/gateway/agents/{agent_id}/action")', "gateway_agent_action"),
        ('@router.get("/cgt/govern/gateway/agents/{agent_id}/trend")', "gateway_agent_trend"),
        ('@router.get("/cgt/govern/gateway/dashboard")', "gateway_dashboard"),
        ('@router.get("/cgt/govern/gateway/reports/pdf")', "gateway_report_pdf"),
    ]

    for route_marker, function_name in expectations:
        assert route_marker in SOURCE
        assert "Depends(get_current_user)" in _function_block(function_name)


def test_governor_runtime_integrations_remain_wired():
    assert "from ..cgt_governor.data.storage import eval_store" in SOURCE
    assert "from ..cgt_governor.policy import PolicyContext" in SOURCE
    assert "policy_engine as runtime_policy_engine" in SOURCE
    assert "from ..cgt_governor.security import decrypt_log_entry" in SOURCE
    assert "encrypt_log_entry" in SOURCE
    assert "sign_response" in SOURCE


def test_evaluate_and_record_keeps_policy_signature_and_encrypted_storage_hooks():
    block = SOURCE[
        SOURCE.index("def _evaluate_and_record") :
        SOURCE.index("\n\n@router.post", SOURCE.index("def _evaluate_and_record"))
    ]

    assert "sign_response(response_data)" in block
    assert "runtime_policy_engine.decide" in block
    assert "runtime_policy_engine.record" in block
    assert "encrypt_log_entry(entry, _crypto_key)" in block
    assert "eval_store.append" in block