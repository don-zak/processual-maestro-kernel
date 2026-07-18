import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

import processual_api.routers.cgt_governor as cgt_router

ROOT = Path(__file__).resolve().parents[1]
ROUTER_SOURCE = ROOT / "processual_api" / "routers" / "cgt_governor.py"
GATEWAY_ROOT = ROOT / "processual_api" / "cgt_governor" / "gateway"


def run_async(coro):
    return asyncio.run(coro)


def read_router_source() -> str:
    return ROUTER_SOURCE.read_text(encoding="utf-8")


def assert_markers(source: str, markers: list[str], label: str):
    missing = [marker for marker in markers if marker not in source]
    assert not missing, f"Missing {label} markers: {missing}"


def test_governance_heavy_routes_are_declared():
    source = read_router_source()

    required_routes = [
        '@router.post("/cgt/govern/batch")',
        '@router.get("/cgt/govern/metrics")',
        '@router.post("/cgt/govern/repair")',
        '@router.post("/cgt/govern/auto-repair")',
        '@router.post("/cgt/govern/compare")',
        '@router.post("/cgt/govern/simulate")',
        '@router.get("/cgt/govern/simulate/reports")',
        '@router.get("/cgt/govern/simulate/reports/{sim_id}/pdf")',
        '@router.post("/cgt/govern/gateway/evaluate")',
        '@router.get("/cgt/govern/gateway/agents")',
        '@router.post("/cgt/govern/gateway/agents")',
        '@router.get("/cgt/govern/gateway/agents/{agent_id}")',
        '@router.post("/cgt/govern/gateway/agents/{agent_id}/action")',
        '@router.get("/cgt/govern/gateway/agents/{agent_id}/trend")',
        '@router.get("/cgt/govern/gateway/dashboard")',
        '@router.get("/cgt/govern/gateway/reports/pdf")',
    ]

    assert_markers(source, required_routes, "CGT governance heavy route")


def test_governance_heavy_request_models_are_declared():
    source = read_router_source()

    required_models = [
        "class GovernRequest(BaseModel):",
        "class BatchGovernRequest(BaseModel):",
        "class ToggleRequest(BaseModel):",
        "class RepairRequest(BaseModel):",
        "class AutoRepairRound(BaseModel):",
        "class AutoRepairRequest(BaseModel):",
        "class CompareAdaptersRequest(BaseModel):",
        "class ReportRequest(GovernRequest):",
        "class RegisterAgentRequest(BaseModel):",
        "class GatewayEvaluateRequest(BaseModel):",
        "class AgentActionRequest(BaseModel):",
    ]

    assert_markers(source, required_models, "CGT governance request model")


def test_shared_evaluation_pipeline_keeps_policy_recording_and_signing_markers():
    source = read_router_source()

    required_markers = [
        "def _resolve_scores(",
        "def _build_response(",
        "def _evaluate_and_record(",
        "runtime_policy_engine.decide(",
        "runtime_policy_engine.record(",
        "PolicyContext(",
        "sign_response(",
        "encrypt_log_entry(",
        "eval_store.append(",
        "policy_version",
        "repair_round",
    ]

    assert_markers(source, required_markers, "shared evaluation pipeline")


def test_repair_endpoint_keeps_expected_policy_mapping_markers():
    source = read_router_source()

    required_markers = [
        "async def generate_repair(",
        "build_hybrid_repair_prompt",
        "build_distortion_repair_prompt",
        '"repair_scaffold"',
        '"restructure"',
        "No repair prompt for policy",
    ]

    assert_markers(source, required_markers, "repair endpoint")


def test_auto_repair_loop_keeps_rounding_and_signature_markers():
    source = read_router_source()

    required_markers = [
        "async def auto_repair(",
        "max_rounds must be >= 1",
        "repair_policies",
        '"repair_scaffold"',
        '"restructure"',
        '"deepen_or_clarify"',
        "repair_prompt",
        "adapter.generate(",
        'sign_response({"auto_repair": True',
        'reason="auto_repair"',
    ]

    assert_markers(source, required_markers, "auto-repair loop")


def test_compare_adapters_keeps_safe_execution_and_signature_markers():
    source = read_router_source()

    required_markers = [
        "async def compare_adapters(",
        "adapter_registry.configured()",
        '"results": []',
        "async def _run_one",
        "adapter.generate(",
        '"results"',
        '"signature"',
        "sign_response(",
    ]

    assert_markers(source, required_markers, "compare adapters route")


def test_simulation_routes_keep_log_pdf_and_listing_markers():
    source = read_router_source()

    required_markers = [
        "_simulation_log",
        "async def run_simulation(",
        "SimulationEngine.run()",
        "generate_supervision_pdf",
        "_simulation_log.append(payload)",
        "async def list_simulations(",
        "async def simulation_pdf(",
        "application/pdf",
    ]

    assert_markers(source, required_markers, "simulation route")


def test_gateway_routes_keep_registry_engine_policy_markers():
    source = read_router_source()

    required_markers = [
        "async def gateway_evaluate(",
        "gateway_engine.evaluate(",
        "Agent not found",
        "gateway_registry.get(",
        "gateway_registry.register(",
        "gateway_registry.change_state(",
        "gateway_registry.count_by_state()",
        "gateway_registry.agents_at_risk()",
        "runtime_policy_engine.decide(",
        "runtime_policy_engine.record(",
        'reason=f"gateway_{decision.action.value}"',
        "decision.action.value",
        "decision.agent_state.value",
        "decision.signature",
    ]

    assert_markers(source, required_markers, "gateway route behavior")


def test_gateway_module_files_keep_core_behavior_markers():
    expected_files = {
        "engine.py": [
            "class GatewayEngine:",
            "def evaluate(",
            "analyze_cgt(",
            "policy_engine.decide(",
            "sign_response(",
            "gateway_registry.add_evaluation(",
            "gateway_registry.change_state(",
        ],
        "models.py": [
            "class AgentState",
            "class GatewayAction",
            "REPAIR",
            "BLOCK",
            "ESCALATE",
            "class EvaluationRecord",
            "class GatewayDecision",
            "class Agent",
            "def average_reward(",
            "def trend(",
        ],
        "policies.py": [
            "class PolicyEngine:",
            "def decide(",
            "GatewayAction.BLOCK",
            "GatewayAction.ESCALATE",
            "GatewayAction.REPAIR",
            "GatewayAction.PASS",
            "repair_prompt",
        ],
        "lifecycle.py": [
            "class LifecycleEngine:",
            "UPGRADE_REWARD_THRESHOLD",
            "FREEZE_REWARD_THRESHOLD",
            "REHAB_REWARD_THRESHOLD",
            "def evaluate_agent(",
        ],
        "registry.py": [
            "def register(",
            "def get(",
            "def list(",
            "def change_state(",
            "def add_evaluation(",
            "def count_by_state(",
            "def agents_at_risk(",
        ],
        "storage.py": [
            "json",
            "gateway",
            "agent",
        ],
    }

    missing_files = []
    missing_markers = {}

    for filename, markers in expected_files.items():
        path = GATEWAY_ROOT / filename
        if not path.is_file():
            missing_files.append(filename)
            continue

        source = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in source]
        if missing:
            missing_markers[filename] = missing

    assert not missing_files, f"Missing gateway module files: {missing_files}"
    assert not missing_markers, f"Missing gateway module markers: {missing_markers}"


def test_governor_status_exposes_runtime_state_without_external_services():
    response = run_async(cgt_router.governor_status(current_user={"sub": "tester"}))

    assert response["enabled"] == cgt_router._gov_state["enabled"]
    assert response["auto_repair"] == cgt_router._gov_state["auto_repair"]
    assert response["max_repair_rounds"] == cgt_router._gov_state["max_repair_rounds"]


def test_generate_repair_returns_prompt_for_known_repair_policies():
    scaffold = run_async(
        cgt_router.generate_repair(
            cgt_router.RepairRequest(
                answer="The answer has useful pieces but needs clearer structure.",
                policy="repair_scaffold",
                language="en",
            ),
            current_user={"sub": "tester"},
        )
    )

    restructure = run_async(
        cgt_router.generate_repair(
            cgt_router.RepairRequest(
                answer="The answer is distorted and should be rebuilt.",
                policy="restructure",
                language="en",
            ),
            current_user={"sub": "tester"},
        )
    )

    assert isinstance(scaffold["repair_prompt"], str)
    assert scaffold["repair_prompt"].strip()
    assert isinstance(restructure["repair_prompt"], str)
    assert restructure["repair_prompt"].strip()


def test_generate_repair_rejects_unknown_policy_without_external_services():
    with pytest.raises(HTTPException) as exc:
        run_async(
            cgt_router.generate_repair(
                cgt_router.RepairRequest(
                    answer="A response that cannot be repaired with this policy.",
                    policy="unknown_policy",
                    language="en",
                ),
                current_user={"sub": "tester"},
            )
        )

    assert exc.value.status_code == 400
    assert "No repair prompt for policy" in exc.value.detail
