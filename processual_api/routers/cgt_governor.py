"""CGT Governor routes - adapter comparison, auto-repair, analysis, gateway management, and simulations."""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel

from ..auth.security import get_current_user, require_scope, require_quota
from ..cgt_governor.adapters.registry import adapter_registry
from ..cgt_governor.data.storage import eval_store
from ..cgt_governor.policy import PolicyContext, policy_engine as runtime_policy_engine
from ..cgt_governor.security import decrypt_log_entry, encrypt_log_entry, get_crypto_key, sign_response

logger = logging.getLogger("processual_api.routers.cgt_governor")

router = APIRouter(tags=["cgt-governor"])

# In-memory state (for standalone mode, no DB)
_gov_state = {
    "enabled": os.environ.get("CGT_GOVERNOR_ENABLED", "true").lower() == "true",
    "auto_repair": os.environ.get("CGT_GOVERNOR_AUTO_REPAIR", "true").lower() == "true",
    "max_repair_rounds": int(os.environ.get("CGT_GOVERNOR_MAX_REPAIR_ROUNDS", "2")),
}

# Simulation log (in-memory, ephemeral)
_simulation_log: deque[dict] = deque(maxlen=500)
_crypto_key = get_crypto_key()

# -- Encrypted adapter config storage --
try:
    from processual_kernel.security.crypto import encrypt_aes256_gcm

    _adapter_crypto_available = True
except ImportError:
    _adapter_crypto_available = False

_ADAPTER_CRYPTO_KEY = os.environ.get("PROCESSUAL_CRYPTO_KEY_B64", "")
_ADAPTER_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _adapter_config_path() -> Path:
    _ADAPTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _ADAPTER_DATA_DIR / "adapter_config.json"


def _save_adapter_config(provider: str, api_key: str, model: str = "", base_url: str = "") -> None:
    config: dict[str, str] = {"provider": provider, "model": model, "base_url": base_url}
    if _adapter_crypto_available and _ADAPTER_CRYPTO_KEY and api_key:
        try:
            envelope = encrypt_aes256_gcm(api_key.encode("utf-8"), _ADAPTER_CRYPTO_KEY, key_id=provider)
            config["encrypted_key"] = json.dumps({
                "algorithm": envelope.algorithm,
                "key_id": envelope.key_id,
                "nonce_b64": envelope.nonce_b64,
                "aad_b64": envelope.aad_b64,
                "ciphertext_b64": envelope.ciphertext_b64,
                "plaintext_sha3_256": envelope.plaintext_sha3_256,
                "ciphertext_sha3_256": envelope.ciphertext_sha3_256,
                "schema_version": envelope.schema_version,
                "created_at": envelope.created_at,
            })
        except Exception:
            pass
    path = _adapter_config_path()
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), "utf-8")


# -- Pydantic Schemas --


class ContextMetadata(BaseModel):
    run_id: str = ""
    agent_id: str = ""
    model: str = ""
    provider: str = ""
    scenario_id: str = ""
    dataset_id: str = ""
    tags: list[str] = []
    environment: str = ""
    policy_version: str = ""
    repair_round: int = 0
    parent_eval_id: str = ""
    created_by: str = ""


class GovernRequest(BaseModel):
    answer: str
    client_query: str = ""
    language: str = "en"
    context: ContextMetadata | None = None
    compatibility: float | None = None
    coherence: float | None = None
    structural_support: float | None = None
    usefulness: float | None = None
    complexity: float | None = None
    fatigue: float | None = None
    shock: float | None = None
    lift: float | None = None
    novelty: float | None = None
    no_answer: float | None = None
    hallucination: float | None = None
    constraint_failure: float | None = None
    speed: float | None = None


class BatchGovernRequest(BaseModel):
    answers: list[GovernRequest]


class ConfigureAdapterRequest(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""
    base_url: str = ""


class TestAdapterRequest(BaseModel):
    provider: str


class ToggleRequest(BaseModel):
    enabled: bool


class RepairRequest(BaseModel):
    answer: str
    policy: str
    language: str = "en"


class AutoRepairRound(BaseModel):
    round: int
    answer: str
    rank: str
    reward: float
    policy: str
    repair_prompt: str | None = None
    fate_vector: dict[str, float] | None = None


class AutoRepairRequest(BaseModel):
    client_query: str
    answer: str
    language: str = "en"
    provider: str | None = None
    max_rounds: int = 3


class CompareAdaptersRequest(BaseModel):
    client_query: str
    system_prompt: str | None = None
    providers: list[str] | None = None
    language: str = "en"
    max_tokens: int = 512
    temperature: float = 0.7


class ReportRequest(GovernRequest):
    answer: str
    client_query: str = ""
    language: str = "en"
    compatibility: float | None = None
    coherence: float | None = None
    structural_support: float | None = None
    usefulness: float | None = None
    complexity: float | None = None
    fatigue: float | None = None
    shock: float | None = None
    lift: float | None = None
    novelty: float | None = None
    no_answer: float | None = None
    hallucination: float | None = None
    constraint_failure: float | None = None
    speed: float | None = None


# -- Gateway Schemas --


class RegisterAgentRequest(BaseModel):
    agent_id: str
    name: str
    role: str
    adapter_name: str = "opencode"
    model: str = ""
    system_prompt: str = ""
    language: str = "en"
    tags: list[str] = []
    priority: int = 1
    risk_level: str = "medium"
    owner: str = ""
    policy_profile: str = "default"


class GatewayEvaluateRequest(BaseModel):
    agent_id: str
    client_query: str
    agent_response: str
    language: str = "en"
    run_id: str = ""
    scenario_id: str = ""
    tags: list[str] = []
    repair_round: int = 0
    parent_eval_id: str = ""


class AgentActionRequest(BaseModel):
    action: str  # freeze | activate | escalate | rehabilitate | deactivate
    reason: str = ""


# -- Helpers --

_SCORE_FALLBACKS: dict[str, float] = {
    "compatibility": 0.5,
    "coherence": 0.5,
    "structural_support": 0.5,
    "usefulness": 0.5,
    "complexity": 0.3,
    "fatigue": 0.15,
    "shock": 0.1,
    "lift": 0.5,
    "novelty": 0.3,
    "no_answer": 0.0,
    "hallucination": 0.0,
    "constraint_failure": 0.0,
    "speed": 0.5,
}


def _resolve_scores(
    req: GovernRequest,
) -> dict[str, float]:
    """Resolve CGT scores: explicit > auto-analyzed > fallback."""
    from ..cgt_governor.analyzer import analyze_cgt

    auto: dict[str, float] = {}
    if req.client_query:
        auto = analyze_cgt(req.client_query, req.answer, language=req.language)
    else:
        logger.warning(
            "client_query is empty - falling back to default scores. "
            "Send 'client_query' for real CGT analysis."
        )

    raw = {
        "compatibility": req.compatibility,
        "coherence": req.coherence,
        "structural_support": req.structural_support,
        "usefulness": req.usefulness,
        "complexity": req.complexity,
        "fatigue": req.fatigue,
        "shock": req.shock,
        "lift": req.lift,
        "novelty": req.novelty,
        "no_answer": req.no_answer,
        "hallucination": req.hallucination,
        "constraint_failure": req.constraint_failure,
        "speed": req.speed,
    }
    resolved: dict[str, float] = {}
    for key in _SCORE_FALLBACKS:
        explicit = raw[key]
        if explicit is not None:
            resolved[key] = explicit
        elif key in auto:
            resolved[key] = auto[key]
        else:
            resolved[key] = _SCORE_FALLBACKS[key]
    return resolved


def _build_response(result, language: str) -> dict:
    return {
        "fate_vector": {
            "stability": result.fate.stability,
            "hybridity": result.fate.hybridity,
            "distortion": result.fate.distortion,
            "extinction": result.fate.extinction,
            "collapse": result.fate.collapse,
            "flourishing": result.fate.flourishing,
            "transient": result.fate.transient,
        },
        "rank": result.rank.value,
        "reward": result.reward,
        "policy": result.policy,
        "policy_label": getattr(result, "policy_label", ""),
        "policy_description": getattr(result, "policy_description", ""),
        "repair_prompt": result.repair_prompt,
    }


# -- Endpoints --


def _evaluate_and_record(
    answer: str,
    language: str,
    scores: dict[str, float],
    context: ContextMetadata | None = None,
    reason: str = "govern",
) -> dict:
    """Shared evaluation pipeline: CGT score -> govern -> policy -> Prometheus -> store -> return."""
    from ..cgt_governor import govern_answer

    result = govern_answer(
        answer=answer,
        compatibility=scores["compatibility"],
        coherence=scores["coherence"],
        structural_support=scores["structural_support"],
        usefulness=scores["usefulness"],
        complexity=scores["complexity"],
        fatigue=scores["fatigue"],
        shock=scores["shock"],
        lift=scores["lift"],
        novelty=scores["novelty"],
        no_answer=scores["no_answer"],
        hallucination=scores["hallucination"],
        constraint_failure=scores["constraint_failure"],
        speed=scores["speed"],
        language=language,
    )

    response_data = _build_response(result, language)
    signature = sign_response(response_data)

    ctx = PolicyContext(avg_reward=result.reward, history_count=1)
    pd = runtime_policy_engine.decide(
        rank=result.rank.value,
        reward=result.reward,
        policy=result.policy,
        policy_label=result.policy_label,
        context=ctx,
    )
    runtime_policy_engine.record(pd, reason=reason)

    try:
        from processual_kernel.observability.metrics import (
            increment_cgt_evaluations,
            increment_fate_rank,
            increment_governance_action,
            increment_pdf_report,
        )
        increment_cgt_evaluations()
        increment_fate_rank(result.rank.value)
        increment_governance_action(pd.action.value)
        increment_pdf_report("governance")
    except ImportError:
        pass

    entry: dict = {
        **response_data,
        "ts": datetime.now(UTC).isoformat(),
        "governance_action": pd.action.value,
        "action_label": pd.action_label,
    }
    if context:
        entry["run_id"] = context.run_id
        entry["agent_id"] = context.agent_id
        entry["model"] = context.model
        entry["provider"] = context.provider
        entry["scenario_id"] = context.scenario_id
        entry["tags"] = context.tags
        entry["environment"] = context.environment
        entry["policy_version"] = context.policy_version
        entry["repair_round"] = context.repair_round
        entry["parent_eval_id"] = context.parent_eval_id
    from ..cgt_governor.data.storage import JsonlEvaluationStore
    entry["eval_id"] = JsonlEvaluationStore._generate_eval_id()
    encrypted = encrypt_log_entry(entry, _crypto_key)
    eval_store.append(json.loads(encrypted) if isinstance(encrypted, str) else encrypted)

    return {
        "result": result,
        "response_data": response_data,
        "signature": signature,
        "governance_action": pd.action.value,
        "action_label": pd.action_label,
        "entry": entry,
    }


@router.post("/cgt/govern")
async def govern(req: GovernRequest, current_user: dict = Depends(require_quota("evaluation"))):
    scores = _resolve_scores(req)
    ev = _evaluate_and_record(
        answer=req.answer,
        language=req.language,
        scores=scores,
        context=req.context,
        reason="govern",
    )
    em = "auto" if req.client_query else "explicit" if any(v is not None for v in (
        req.compatibility, req.coherence, req.structural_support, req.usefulness,
        req.complexity, req.fatigue, req.shock, req.lift, req.novelty,
        req.no_answer, req.hallucination, req.constraint_failure, req.speed,
    )) else "fallback"
    return {
        **ev["response_data"],
        "signature": ev["signature"],
        "scores": scores,
        "governance_action": ev["governance_action"],
        "action_label": ev["action_label"],
        "eval_id": ev["entry"].get("eval_id", ""),
        "analysis_mode": em,
    }


@router.post("/cgt/govern/batch")
async def govern_batch(req: BatchGovernRequest, current_user: dict = Depends(get_current_user)):
    results = []
    for ans in req.answers:
        scores = _resolve_scores(ans)
        ev = _evaluate_and_record(
            answer=ans.answer,
            language=ans.language,
            scores=scores,
            context=ans.context,
            reason="batch",
        )
        em = "auto" if ans.client_query else "explicit" if any(v is not None for v in (
            ans.compatibility, ans.coherence, ans.structural_support, ans.usefulness,
            ans.complexity, ans.fatigue, ans.shock, ans.lift, ans.novelty,
            ans.no_answer, ans.hallucination, ans.constraint_failure, ans.speed,
        )) else "fallback"
        results.append(
            {
                **ev["response_data"],
                "scores": scores,
                "governance_action": ev["governance_action"],
                "action_label": ev["action_label"],
                "eval_id": ev["entry"].get("eval_id", ""),
                "analysis_mode": em,
            }
        )

    results.sort(key=lambda r: r["reward"], reverse=True)  # type: ignore[arg-type, return-value]
    return {"results": results, "count": len(results)}


@router.get("/cgt/govern/status")
async def governor_status(current_user: dict = Depends(get_current_user)):
    return {
        "enabled": _gov_state["enabled"],
        "auto_repair": _gov_state["auto_repair"],
        "max_repair_rounds": _gov_state["max_repair_rounds"],
        "providers": adapter_registry.list_providers(),
        "default_provider": (lambda a: a.provider_name if a else None)(adapter_registry.default()),
        "evaluation_count": len(eval_store),
    }


@router.post("/cgt/govern/toggle")
async def governor_toggle(req: ToggleRequest, current_user: dict = Depends(get_current_user)):
    _gov_state["enabled"] = req.enabled
    return {"enabled": _gov_state["enabled"]}


@router.get("/cgt/govern/metrics")
async def governor_metrics(current_user: dict = Depends(get_current_user)):
    """Real operational metrics for the Overview dashboard.

    Returns governance stats, PSI history, agent performance, and action distribution.
    """
    from ..cgt_governor.gateway import gateway_registry

    entries = [decrypt_log_entry(e, _crypto_key) for e in eval_store.entries] if eval_store else []

    total = len(entries)
    reward_sum = 0.0
    dist: dict[str, int] = {}
    psi_history: list[dict] = []
    for i, entry in enumerate(entries):
        rank = entry.get("rank", "?")
        dist[rank] = dist.get(rank, 0) + 1
        reward = entry.get("reward", 0)
        reward_sum += reward
        psi_history.append({
            "index": i,
            "reward": reward,
            "rank": rank,
        })

    agents = gateway_registry.list()
    agent_total = len(agents)
    agent_active = sum(1 for a in agents if a.state.value == "active")
    agent_avg_reward = (
        sum(a.average_reward for a in agents) / agent_total
        if agent_total
        else 0
    )

    # Action distribution from runtime policy engine
    action_dist = runtime_policy_engine.action_distribution

    return {
        "total_evaluations": total,
        "avg_reward": round(reward_sum / total, 4) if total else 0,
        "rank_distribution": dist,
        "psi_history": psi_history[-100:],
        "total_agents": agent_total,
        "active_agents": agent_active,
        "agent_avg_reward": round(agent_avg_reward, 4),
        "action_distribution": action_dist,
        "policy_action_count": len(runtime_policy_engine.history),
    }


@router.get("/cgt/govern/reports")
async def governor_reports(
    rank: str | None = Query(None, description="Filter by existence rank"),
    date_from: str | None = Query(None, description="ISO date start"),
    date_to: str | None = Query(None, description="ISO date end"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    current_user: dict = Depends(get_current_user),
):
    if not eval_store:
        return {"total": 0, "rank_distribution": {}, "avg_reward": 0}

    entries = [decrypt_log_entry(e, _crypto_key) for e in eval_store.entries]

    if rank:
        entries = [e for e in entries if e.get("rank") == rank]
    if date_from:
        entries = [e for e in entries if e.get("ts", "") >= date_from]
    if date_to:
        entries = [e for e in entries if e.get("ts", "") <= date_to]

    total = len(entries)
    dist: dict[str, int] = {}
    reward_sum = 0.0
    for entry in entries:
        dist[entry.get("rank", "?")] = dist.get(entry.get("rank", "?"), 0) + 1
        reward_sum += entry.get("reward", 0)

    start = (page - 1) * page_size
    end = start + page_size
    page_entries = entries[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "rank_distribution": dist,
        "avg_reward": round(reward_sum / total, 4) if total > 0 else 0,
        "entries": page_entries,
    }


@router.get("/cgt/govern/reports/export")
async def export_reports_json(
    rank: str | None = Query(None, description="Filter by existence rank"),
    date_from: str | None = Query(None, description="ISO date start"),
    date_to: str | None = Query(None, description="ISO date end"),
    current_user: dict = Depends(get_current_user),
):
    if not eval_store:
        return Response(
            content="[]",
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=reports.json"},
        )

    entries = [decrypt_log_entry(e, _crypto_key) for e in eval_store.entries]

    if rank:
        entries = [e for e in entries if e.get("rank") == rank]
    if date_from:
        entries = [e for e in entries if e.get("ts", "") >= date_from]
    if date_to:
        entries = [e for e in entries if e.get("ts", "") <= date_to]

    json_bytes = json.dumps(entries, indent=2, ensure_ascii=False, default=str).encode("utf-8")
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=reports.json"},
    )


@router.post("/cgt/govern/repair")
async def generate_repair(req: RepairRequest, current_user: dict = Depends(get_current_user)):
    from ..cgt_governor.repair import (
        build_distortion_repair_prompt,
        build_hybrid_repair_prompt,
        build_transient_deepen_prompt,
    )

    prompt_map = {
        "repair_scaffold": build_hybrid_repair_prompt,
        "restructure": build_distortion_repair_prompt,
        "deepen_or_clarify": build_transient_deepen_prompt,
    }

    builder = prompt_map.get(req.policy)
    if not builder:
        raise HTTPException(status_code=400, detail=f"No repair prompt for policy: {req.policy}")

    return {"repair_prompt": builder(req.answer, language=req.language)}


# -- Auto-Repair Loop --


@router.post("/cgt/govern/auto-repair")
async def auto_repair(req: AutoRepairRequest, current_user: dict = Depends(get_current_user)):
    """Run the full CGT governance + auto-repair loop.

    Analyzes the answer, runs governance, and if the response is rejected
    (hybrid, distorted, transient, extinct), automatically sends the repair
    prompt to an LLM and re-evaluates. Loops until accepted or max_rounds.
    """
    if req.max_rounds < 1:
        raise HTTPException(status_code=400, detail="max_rounds must be >= 1")
    from ..cgt_governor import govern_answer
    from ..cgt_governor.adapters.registry import adapter_registry
    from ..cgt_governor.analyzer import analyze_cgt

    accepted_ranks = {"flourishing", "stable"}
    repair_policies = {"repair_scaffold", "restructure", "deepen_or_clarify"}

    current_answer = req.answer
    history: list[dict] = []

    for round_num in range(1, req.max_rounds + 1):
        scores = analyze_cgt(req.client_query, current_answer, language=req.language)
        result = govern_answer(
            answer=current_answer,
            compatibility=scores["compatibility"],
            coherence=scores["coherence"],
            structural_support=scores["structural_support"],
            usefulness=scores["usefulness"],
            complexity=scores["complexity"],
            fatigue=scores["fatigue"],
            shock=scores["shock"],
            lift=scores["lift"],
            novelty=scores["novelty"],
            no_answer=scores["no_answer"],
            hallucination=scores["hallucination"],
            constraint_failure=scores["constraint_failure"],
            speed=scores["speed"],
            language=req.language,
        )

        round_entry = {
            "round": round_num,
            "answer": current_answer,
            "rank": result.rank.value,
            "reward": result.reward,
            "policy": result.policy,
            "repair_prompt": result.repair_prompt,
            "fate_vector": {
                "stability": result.fate.stability,
                "hybridity": result.fate.hybridity,
                "distortion": result.fate.distortion,
                "extinction": result.fate.extinction,
                "collapse": result.fate.collapse,
                "flourishing": result.fate.flourishing,
                "transient": result.fate.transient,
            },
        }
        history.append(round_entry)

        if result.rank.value in accepted_ranks:
            break

        if round_num == req.max_rounds or not result.repair_prompt:
            break

        if result.policy in repair_policies:
            adapter = adapter_registry.default() if not req.provider else adapter_registry.get(req.provider)
            if adapter and adapter.is_configured():
                system = (
                    "Ã˜Â£Ã˜Â¹Ã˜Â¯ Ã™Æ’Ã˜ÂªÃ˜Â§Ã˜Â¨Ã˜Â© Ã˜Â§Ã™â€žÃ˜Â¬Ã™Ë†Ã˜Â§Ã˜Â¨ Ã˜Â§Ã™â€žÃ˜ÂªÃ˜Â§Ã™â€žÃ™Å  "
                    f"Ã˜Â¨Ã™â€žÃ˜ÂºÃ˜Â© {req.language} Ã™Ë†Ã™ÂÃ™â€š Ã˜Â§Ã™â€žÃ˜ÂªÃ˜Â¹Ã™â€žÃ™Å Ã™â€¦Ã˜Â§Ã˜Âª.\n\n"
                    f"Ã˜Â§Ã™â€žÃ˜Â³Ã˜Â¤Ã˜Â§Ã™â€ž Ã˜Â§Ã™â€žÃ˜Â£Ã˜ÂµÃ™â€žÃ™Å : {req.client_query}"
                    if req.language == "ar"
                    else (
                        "Rewrite the following answer following the instructions.\n\n"
                        f"Original question: {req.client_query}"
                    )
                )
                try:
                    new_answer = await adapter.generate(
                        prompt=result.repair_prompt,
                        system_prompt=system,
                    )
                    if new_answer and new_answer.strip():
                        current_answer = new_answer.strip()
                        continue
                except Exception as exc:
                    logger.error("Auto-repair round %d failed: %s", round_num, exc)
            break

    final = history[-1]
    sig = sign_response({"auto_repair": True, "rounds": len(history), "rank": final["rank"], "reward": final["reward"]})

    ev = _evaluate_and_record(
        answer=final["answer"],
        language=req.language,
        scores=scores,
        reason="auto_repair",
    )

    return {
        "final_rank": final["rank"],
        "final_reward": final["reward"],
        "final_answer": final["answer"],
        "total_rounds": len(history),
        "history": history,
        "signature": sig,
        "governance_action": ev["governance_action"],
        "action_label": ev["action_label"],
    }


# -- Adapter Comparison --


@router.post("/cgt/govern/compare")
async def compare_adapters(req: CompareAdaptersRequest, current_user: dict = Depends(get_current_user)):
    """Send the same query to all (or selected) configured LLM adapters
    and compare their CGT governance results side-by-side.

    Returns CGT scores, rank, reward, latency, and response text for each adapter.
    """
    from ..cgt_governor import govern_answer
    from ..cgt_governor.adapters.registry import adapter_registry
    from ..cgt_governor.analyzer import analyze_cgt

    adapters = adapter_registry.configured()
    if req.providers:
        adapters = {k: v for k, v in adapters.items() if k in req.providers}

    if not adapters:
        return {
            "client_query": req.client_query,
            "total_adapters": 0,
            "configured_adapters": 0,
            "results": [],
            "error": "No configured adapters available",
            "signature": sign_response({"compare": True, "query": req.client_query[:100], "adapters": 0}),
        }

    import asyncio

    async def _run_one(name: str, adapter) -> dict:
        t0 = __import__("time").monotonic()
        try:
            response = await adapter.generate(
                prompt=req.client_query,
                system_prompt=req.system_prompt or "",
            )
            latency = round((__import__("time").monotonic() - t0) * 1000)
            answer = response.strip() if response else ""
            scores = analyze_cgt(req.client_query, answer, language=req.language)
            result = govern_answer(
                answer=answer,
                **scores,
                language=req.language,
            )

            return {
                "provider": name,
                "provider_name": adapter.provider_name,
                "model": adapter.default_model,
                "latency_ms": latency,
                "response_text": answer[:500],
                "response_preview": answer[:500],
                "response_text_full": answer,
                "response_preview_length": min(len(answer), 500),
                "response_truncated_for_response": len(answer) > 500,
                "response_length": len(answer),
                "scores": scores,
                "rank": result.rank.value,
                "reward": result.reward,
                "policy": result.policy,
                "fate_vector": {
                    "stability": result.fate.stability,
                    "hybridity": result.fate.hybridity,
                    "distortion": result.fate.distortion,
                    "extinction": result.fate.extinction,
                    "collapse": result.fate.collapse,
                    "flourishing": result.fate.flourishing,
                    "transient": result.fate.transient,
                },
                "error": None,
            }
        except Exception as exc:
            latency = round((__import__("time").monotonic() - t0) * 1000)
            return {
                "provider": name,
                "provider_name": adapter.provider_name,
                "model": adapter.default_model,
                "latency_ms": latency,
                "response_text": "",
                "response_length": 0,
                "scores": {},
                "rank": None,
                "reward": None,
                "policy": None,
                "fate_vector": {},
                "error": f"Adapter error: {type(exc).__name__}: {str(exc)}",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

    tasks = [_run_one(name, a) for name, a in adapters.items()]
    results = await asyncio.gather(*tasks)

    # Sort by reward descending (successful results first)
    results.sort(key=lambda r: r["reward"] if r["reward"] is not None else -999, reverse=True)

    sig = sign_response(
        {
            "compare": True,
            "query": req.client_query[:100],
            "adapters": len(results),
        }
    )

    return {
        "client_query": req.client_query,
        "total_adapters": len(results),
        "configured_adapters": len(adapters),
        "results": results,
        "signature": sig,
    }


# -- PDF Report Endpoints --


@router.post("/cgt/govern/report")
async def govern_report(req: ReportRequest, current_user: dict = Depends(get_current_user)):
    """Evaluate and return JSON + PDF + signature in one call."""
    from ..cgt_governor.reports import generate_governance_pdf

    scores = _resolve_scores(req)
    ev = _evaluate_and_record(
        answer=req.answer,
        language=req.language,
        scores=scores,
        context=req.context,
        reason="report",
    )

    pdf_bytes = generate_governance_pdf(
        ev["entry"],
        language=req.language,
        signature=ev["signature"],
    )

    import base64

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    em = "auto" if req.client_query else "explicit" if any(v is not None for v in (
        req.compatibility, req.coherence, req.structural_support, req.usefulness,
        req.complexity, req.fatigue, req.shock, req.lift, req.novelty,
        req.no_answer, req.hallucination, req.constraint_failure, req.speed,
    )) else "fallback"
    return {
        **ev["response_data"],
        "scores": scores,
        "signature": ev["signature"],
        "governance_action": ev["governance_action"],
        "action_label": ev["action_label"],
        "pdf_base64": pdf_b64,
        "ts": ev["entry"]["ts"],
        "eval_id": ev["entry"].get("eval_id", ""),
        "analysis_mode": em,
    }


@router.get("/cgt/govern/reports/pdf")
async def governor_reports_pdf(
    lang: str = Query("en", description="Language: en or ar"),
    current_user: dict = Depends(get_current_user),
):
    if lang not in ("en", "ar"):
        raise HTTPException(status_code=400, detail="Language must be 'en' or 'ar'")
    """Download a PDF summary of all evaluations in the log."""
    from ..cgt_governor.reports import generate_governance_pdf

    if not eval_store:
        raise HTTPException(status_code=404, detail="No evaluations found")

    # Decrypt all entries for the summary
    entries = [decrypt_log_entry(e, _crypto_key) for e in eval_store.entries]

    total = len(entries)
    dist: dict[str, int] = {}
    reward_sum = 0.0
    for e in entries:
        dist[e.get("rank", "?")] = dist.get(e.get("rank", "?"), 0) + 1
        reward_sum += e.get("reward", 0)

    summary = {
        "total": total,
        "rank_distribution": dist,
        "avg_reward": round(reward_sum / total, 4) if total else 0,
        "recent": entries[-5:],
    }
    summary_sig = sign_response(summary)

    pdf_bytes = generate_governance_pdf(
        {
            "rank": f"Summary - {total} evaluations",
            "reward": summary["avg_reward"],
            "policy": f"{len(dist)} ranks",
            "policy_label": f"Total: {total}",
            "fate_vector": dist,
            "ts": datetime.now(UTC).isoformat(),
        },
        language=lang,
        signature=summary_sig,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=governance-report-{lang}.pdf",
            "X-Signature": summary_sig,
        },
    )


@router.get("/cgt/govern/reports/{eval_id}/pdf")
async def governor_eval_pdf(
    eval_id: str,
    lang: str = Query("en", description="Language: en or ar"),
    current_user: dict = Depends(get_current_user),
):
    if lang not in ("en", "ar"):
        raise HTTPException(status_code=400, detail="Language must be 'en' or 'ar'")
    """Download a PDF for a specific evaluation by eval_id."""
    from ..cgt_governor.reports import generate_governance_pdf

    for stored in reversed(eval_store.entries):
        entry = decrypt_log_entry(stored, _crypto_key)
        if entry.get("eval_id") == eval_id:
            sig = sign_response(entry)
            pdf_bytes = generate_governance_pdf(entry, language=lang, signature=sig)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=governance-eval-{eval_id}-{lang}.pdf",
                    "X-Signature": sig,
                },
            )

    raise HTTPException(status_code=404, detail=f"Evaluation eval_id='{eval_id}' not found")


# -- Simulation / Supervision Endpoints --


@router.post("/cgt/govern/simulate")
async def run_simulation(current_user: dict = Depends(get_current_user)):
    """Run a full supervision simulation across all virtual LLM agents.

    Returns JSON evaluation per agent + aggregate statistics + signature.
    """
    from ..cgt_governor.simulation import SimulationEngine, generate_supervision_pdf

    result = SimulationEngine.run()
    sim_sig = sign_response(
        {
            "simulation_id": result.simulation_id,
            "avg_reward": result.avg_reward,
            "rank_distribution": result.rank_distribution,
        }
    )

    # Generate PDF
    pdf_bytes = generate_supervision_pdf(result, signature=sim_sig)

    import base64

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    # Build agent cards for JSON response
    agent_cards = []
    for ev in result.evaluations:
        agent_cards.append(
            {
                "agent_id": ev.agent.agent_id,
                "name": ev.agent.name,
                "role": ev.agent.role,
                "language": ev.agent.language,
                "quality": ev.agent.quality,
                "scenario": ev.scenario_title,
                "rank": ev.rank,
                "reward": ev.reward,
                "policy": ev.policy,
                "policy_label": ev.policy_label,
                "fate_vector": ev.fate_vector,
                "repair_prompt": ev.repair_prompt,
            }
        )

    payload = {
        "simulation_id": result.simulation_id,
        "ts": result.ts,
        "total_agents": len(result.evaluations),
        "rank_distribution": result.rank_distribution,
        "avg_reward": result.avg_reward,
        "highest_agent": result.highest_agent,
        "lowest_agent": result.lowest_agent,
        "risk_count": result.risk_count,
        "agents": agent_cards,
        "signature": sim_sig,
        "pdf_base64": pdf_b64,
    }

    _simulation_log.append(payload)
    return payload


@router.get("/cgt/govern/simulate/reports")
async def list_simulations(current_user: dict = Depends(get_current_user)):
    """List all completed simulation runs."""
    return {
        "total": len(_simulation_log),
        "simulations": [
            {
                "simulation_id": s["simulation_id"],
                "ts": s["ts"],
                "total_agents": s["total_agents"],
                "avg_reward": s["avg_reward"],
                "risk_count": s["risk_count"],
            }
            for s in _simulation_log
        ],
    }


@router.get("/cgt/govern/simulate/reports/{sim_id}/pdf")
async def simulation_pdf(sim_id: str, current_user: dict = Depends(get_current_user)):
    """Download the supervision PDF for a past simulation."""
    matched = [s for s in _simulation_log if s["simulation_id"] == sim_id]
    if not matched:
        raise HTTPException(status_code=404, detail=f"Simulation '{sim_id}' not found")

    import base64

    pdf_bytes = base64.b64decode(matched[0]["pdf_base64"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={sim_id}.pdf",
            "X-Signature": matched[0]["signature"],
        },
    )


# -- Analyze Endpoint --


class AnalyzeRequest(BaseModel):
    answer: str
    client_query: str = ""
    language: str = "en"


@router.post("/cgt/analyze")
async def analyze(req: AnalyzeRequest, current_user: dict = Depends(get_current_user)):
    """Run the heuristic CGT analyzer and return raw scores without governance.

    Accepts answer + optional client_query. Returns all 13 CGT scores.
    """
    if not req.client_query:
        from ..cgt_governor.analyzer import analyze_cgt

        scores = analyze_cgt("", req.answer, language=req.language)
    else:
        from ..cgt_governor.analyzer import analyze_cgt

        scores = analyze_cgt(req.client_query, req.answer, language=req.language)
    return scores


# -- Gateway Endpoints --


@router.post("/cgt/govern/gateway/evaluate")
async def gateway_evaluate(req: GatewayEvaluateRequest, current_user: dict = Depends(get_current_user)):
    """Evaluate an agent's response through the governance gateway.

    Returns a decision: pass / repair / block / escalate + signature.
    """
    from ..cgt_governor.gateway import gateway_engine

    decision = gateway_engine.evaluate(
        agent_id=req.agent_id,
        client_query=req.client_query,
        agent_response=req.agent_response,
        language=req.language,
    )
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {req.agent_id}")

    # Record runtime policy action
    from ..cgt_governor.gateway import gateway_registry
    agent_obj = gateway_registry.get(req.agent_id)
    ctx = PolicyContext(
        avg_reward=getattr(decision, "reward", 0.0),
        consecutive_failures=agent_obj.consecutive_failures if agent_obj else 0,
        agent_state=decision.agent_state.value,
        history_count=len(agent_obj.evaluation_history) if agent_obj else 0,
    )
    pd = runtime_policy_engine.decide(
        rank=decision.rank or "unknown",
        reward=decision.reward,
        policy=decision.policy,
        policy_label=decision.policy_label,
        context=ctx,
    )
    runtime_policy_engine.record(pd, reason=f"gateway_{decision.action.value}")

    # Update Prometheus metrics
    try:
        from processual_kernel.observability.metrics import (
            increment_cgt_evaluations,
            increment_fate_rank,
            increment_governance_action,
            increment_pdf_report,
        )
        increment_cgt_evaluations()
        increment_fate_rank(decision.rank)
        increment_governance_action(pd.action.value)
        increment_pdf_report("gateway")
    except ImportError:
        pass

    # Save to persistent eval_store
    gw_entry: dict = {
        "fate_vector": decision.fate_vector,
        "rank": decision.rank,
        "reward": decision.reward,
        "policy": decision.policy,
        "policy_label": decision.policy_label,
        "repair_prompt": decision.repair_prompt,
        "ts": datetime.now(UTC).isoformat(),
        "governance_action": pd.action.value,
        "action_label": pd.action_label,
        "agent_id": req.agent_id,
        "run_id": req.run_id or f"gateway_{int(time.time())}",
        "scenario_id": req.scenario_id,
        "tags": req.tags,
        "repair_round": req.repair_round,
        "parent_eval_id": req.parent_eval_id,
        "model": agent_obj.model if agent_obj else "",
        "provider": agent_obj.adapter_name if agent_obj else "",
    }
    from ..cgt_governor.data.storage import JsonlEvaluationStore
    gw_entry["eval_id"] = JsonlEvaluationStore._generate_eval_id()
    encrypted = encrypt_log_entry(gw_entry, _crypto_key)
    eval_store.append(json.loads(encrypted) if isinstance(encrypted, str) else encrypted)

    return {
        "action": decision.action.value,
        "rank": decision.rank,
        "reward": decision.reward,
        "policy": decision.policy,
        "policy_label": decision.policy_label,
        "fate_vector": decision.fate_vector,
        "repair_prompt": decision.repair_prompt,
        "agent_state": decision.agent_state.value,
        "message": decision.message,
        "signature": decision.signature,
        "governance_action": pd.action.value,
        "action_label": pd.action_label,
        "eval_id": gw_entry.get("eval_id", ""),
    }


@router.get("/cgt/govern/gateway/agents")
async def gateway_list_agents(
    state: str | None = Query(None, description="Filter by state"),
    current_user: dict = Depends(get_current_user),
):
    """List all registered agents with optional state filter."""
    from ..cgt_governor.gateway import AgentState, gateway_registry

    filter_state = AgentState(state) if state else None
    agents = gateway_registry.list(state=filter_state)

    return {
        "total": len(agents),
        "agents": [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "role": a.role,
                "state": a.state.value,
                "adapter": a.adapter_name,
                "model": a.model,
                "evaluations": len(a.evaluation_history),
                "avg_reward": a.average_reward,
                "trend": a.trend,
                "consecutive_failures": a.consecutive_failures,
                "created_at": a.created_at,
                "last_state_change": a.last_state_change,
                "last_state_reason": a.last_state_reason,
                "tags": a.tags,
                "priority": a.priority,
                "risk_level": a.risk_level,
                "owner": a.owner,
                "policy_profile": a.policy_profile,
            }
            for a in agents
        ],
    }


@router.post("/cgt/govern/gateway/agents")
async def gateway_register_agent(req: RegisterAgentRequest, current_user: dict = Depends(get_current_user)):
    """Register a new agent for governance."""
    from ..cgt_governor.gateway import Agent, AgentState, gateway_registry

    existing = gateway_registry.get(req.agent_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent already exists: {req.agent_id}")

    from datetime import datetime

    now = datetime.now(UTC).isoformat()

    agent = Agent(
        agent_id=req.agent_id,
        name=req.name,
        role=req.role,
        adapter_name=req.adapter_name,
        model=req.model or req.adapter_name,
        system_prompt=req.system_prompt,
        language=req.language,
        state=AgentState.PENDING,
        created_at=now,
        last_state_change=now,
        last_state_reason="Registered",
        tags=req.tags,
        priority=req.priority,
        risk_level=req.risk_level,
        owner=req.owner,
        policy_profile=req.policy_profile,
    )
    gateway_registry.register(agent)

    return {
        "agent_id": agent.agent_id,
        "state": agent.state.value,
        "created_at": agent.created_at,
    }


@router.get("/cgt/govern/gateway/agents/{agent_id}")
async def gateway_get_agent(agent_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed status and evaluation history for an agent."""
    from ..cgt_governor.gateway import gateway_registry

    agent = gateway_registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "role": agent.role,
        "state": agent.state.value,
        "adapter": agent.adapter_name,
        "model": agent.model,
        "system_prompt": agent.system_prompt,
        "language": agent.language,
        "created_at": agent.created_at,
        "last_state_change": agent.last_state_change,
        "last_state_reason": agent.last_state_reason,
        "avg_reward": agent.average_reward,
        "trend": agent.trend,
        "consecutive_failures": agent.consecutive_failures,
        "evaluations": [  # last 20
            {
                "ts": e.timestamp,
                "rank": e.rank,
                "reward": e.reward,
                "policy": e.policy_label,
                "action": e.action_taken.value,
            }
            for e in agent.evaluation_history[-20:]
        ],
    }


@router.post("/cgt/govern/gateway/agents/{agent_id}/action")
async def gateway_agent_action(agent_id: str, req: AgentActionRequest, current_user: dict = Depends(get_current_user)):
    """Execute a lifecycle action: freeze, activate, escalate, rehabilitate, deactivate."""
    from ..cgt_governor.gateway import AgentState, gateway_registry

    agent = gateway_registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    state_map = {
        "freeze": AgentState.FROZEN,
        "activate": AgentState.ACTIVE,
        "escalate": AgentState.ESCALATED,
        "rehabilitate": AgentState.REHABILITATING,
        "deactivate": AgentState.DEACTIVATED,
    }

    new_state = state_map.get(req.action)
    if new_state is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    old_state = agent.state.value
    gateway_registry.change_state(agent_id, new_state, req.reason)

    return {
        "agent_id": agent_id,
        "previous_state": old_state,
        "new_state": new_state.value,
        "reason": req.reason,
    }


@router.get("/cgt/govern/gateway/agents/{agent_id}/trend")
async def gateway_agent_trend(agent_id: str, current_user: dict = Depends(get_current_user)):
    """Get performance trend data for an agent."""
    from ..cgt_governor.gateway import gateway_registry

    agent = gateway_registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "agent_id": agent_id,
        "current_avg": agent.average_reward,
        "trend": agent.trend,
        "consecutive_failures": agent.consecutive_failures,
        "rewards": agent.performance_window[-50:],
    }


@router.get("/cgt/govern/gateway/dashboard")
async def gateway_dashboard(current_user: dict = Depends(get_current_user)):
    """JSON dashboard of the governance gateway status."""
    from ..cgt_governor.gateway import gateway_registry

    counts = gateway_registry.count_by_state()
    total = sum(counts.values())
    at_risk = gateway_registry.agents_at_risk()

    return {
        "total_agents": total,
        "state_distribution": counts,
        "agents_at_risk": len(at_risk),
        "at_risk_list": [a.agent_id for a in at_risk],  # type: ignore[attr-defined]
    }


@router.get("/cgt/govern/gateway/reports/pdf")
async def gateway_report_pdf(current_user: dict = Depends(get_current_user)):
    """Download a PDF summary of the current gateway state."""
    from datetime import datetime

    from ..cgt_governor.gateway import gateway_registry
    from ..cgt_governor.reports import generate_governance_pdf
    from ..cgt_governor.security import sign_response

    agents = gateway_registry.list()
    total = len(agents)
    counts = gateway_registry.count_by_state()
    at_risk = gateway_registry.agents_at_risk()
    ts = datetime.now(UTC).isoformat()

    summary = {
        "rank": f"Gateway - {total} agents",
        "reward": sum(a.average_reward for a in agents) / max(total, 1),
        "policy": f"{len(counts)} states",
        "policy_label": f"At risk: {len(at_risk)}",
        "fate_vector": counts,
        "ts": ts,
    }
    sig = sign_response(summary)

    pdf_bytes = generate_governance_pdf(summary, language="en", signature=sig)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=gateway-report.pdf",
            "X-Signature": sig,
        },
    )


@router.get("/adapters/status")
async def adapters_status(current_user: dict = Depends(require_scope("read:adapters"))):
    providers = []
    for name, adapter in adapter_registry.all().items():
        providers.append(
            {
                "name": adapter.provider_name,
                "configured": adapter.is_configured(),
                "default_model": adapter.default_model,
            }
        )

    return {
        "providers": providers,
        "default": (lambda a: a.provider_name if a else None)(adapter_registry.default()),
    }


@router.post("/adapters/configure")
async def configure_adapter(req: ConfigureAdapterRequest, _current_user: dict = Depends(require_scope("admin:settings"))):
    env_map = {
        "openai": ("OPENAI_API_KEY", "OPENAI_DEFAULT_MODEL", ""),
        "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_DEFAULT_MODEL", ""),
        "gemini": ("GEMINI_API_KEY", "GEMINI_DEFAULT_MODEL", ""),
        "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_DEFAULT_MODEL", ""),
        "opencode": ("OPENCODE_API_KEY", "OPENCODE_DEFAULT_MODEL", "OPENCODE_API_URL"),
        "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_DEFAULT_MODEL", "OPENROUTER_API_URL"),
    }

    key = req.provider.lower()
    if key not in env_map:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    api_key_env, model_env, url_env = env_map[key]

    # Persist to encrypted storage for durability
    _save_adapter_config(req.provider, req.api_key, req.model, req.base_url)

    # Also apply to process environment for immediate availability
    os.environ[api_key_env] = req.api_key
    if req.model:
        os.environ[model_env] = req.model
    if url_env and req.base_url:
        os.environ[url_env] = req.base_url

    logger.info("Adapter configured: %s", req.provider)
    return {"provider": req.provider, "configured": True}


@router.post("/adapters/test")
async def test_adapter(req: TestAdapterRequest, current_user: dict = Depends(get_current_user)):
    adapter = adapter_registry.get(req.provider)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Adapter not found: {req.provider}")

    import time

    start = time.monotonic()
    try:
        available = await adapter.is_available()
        latency = round((time.monotonic() - start) * 1000)
        return {
            "provider": req.provider,
            "ok": available,
            "latency_ms": latency,
            "model": adapter.default_model,
            "message": "Connected" if available else "Unreachable",
        }
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000)
        return {
            "provider": req.provider,
            "ok": False,
            "latency_ms": latency,
            "model": adapter.default_model,
            "message": f"Adapter error: {type(exc).__name__}",
        }


