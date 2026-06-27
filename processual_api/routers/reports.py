"""Report generation routes — LLM-powered narratives and fate analysis reports."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.security import get_current_user
from ..schemas.reports import LLMReportRequest, LLMReportResponse

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

router = APIRouter(prefix="/reports", tags=["reports"])


class FateReportRequest(BaseModel):
    workflow_id: str
    fate_vector: dict[str, float]
    existence_rank: str


class FateReportResponse(BaseModel):
    workflow_id: str
    report_id: str
    status: str


@router.post("/fate", response_model=FateReportResponse)
async def submit_fate_report(req: FateReportRequest, _user: str = Depends(get_current_user)):
    return FateReportResponse(
        workflow_id=req.workflow_id,
        report_id=f"report-{req.workflow_id}",
        status="recorded",
    )


@router.post("/generate-llm", response_model=LLMReportResponse)
async def generate_llm_report(req: LLMReportRequest, _user: str = Depends(get_current_user)):
    """Generate a natural-language CGT report using the client's LLM provider."""

    from ..cgt_governor.reports.llm_reporter import generate_llm_report as _generate

    api_key = ""
    provider = req.provider
    model = req.model

    if not provider:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        settings_path = _DATA_DIR / "settings_default.json"
        if settings_path.exists():
            try:
                raw = json.loads(settings_path.read_text("utf-8"))
                llm = raw.get("llm_provider", {})
                if llm.get("configured"):
                    provider = llm.get("provider", "opencode")
                    model = model or llm.get("model", "")
                    encrypted = llm.get("encrypted_key", "")
                    if encrypted:
                        try:
                            import os as _os

                            from processual_kernel.security.crypto import CryptoEnvelope, decrypt_aes256_gcm
                            key = _os.environ.get("PROCESSUAL_CRYPTO_KEY_B64", "")
                            if key:
                                data = json.loads(encrypted)
                                envelope = CryptoEnvelope(**{
                                    k: data[k] for k in (
                                        "algorithm", "key_id", "nonce_b64", "aad_b64",
                                        "ciphertext_b64", "plaintext_sha3_256", "ciphertext_sha3_256",
                                    )
                                })
                                plaintext = decrypt_aes256_gcm(envelope, key)
                                api_key = plaintext.decode("utf-8")
                        except Exception:
                            pass
            except (json.JSONDecodeError, OSError):
                pass

    result = await _generate(
        fate_vector=req.fate_vector,
        existence_rank=req.existence_rank,
        provider=provider,
        model=model,
        api_key=api_key,
        language=req.language,
        style=req.style,
        robustness=req.robustness,
        sensitivity=req.sensitivity,
        compatibility=req.compatibility,
        lift=req.lift,
        possibility=req.possibility,
        aftermath=req.aftermath,
    )

    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])

    return LLMReportResponse(
        report=result.get("report", ""),
        provider_used=result.get("provider_used", provider),
        model_used=result.get("model_used", model),
        latency_ms=result.get("latency_ms"),
        tokens_used=result.get("tokens_used"),
        error=result.get("error"),
        generated_at=result.get("generated_at"),
    )
