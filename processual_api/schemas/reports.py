from pydantic import BaseModel


class EncryptedReportResponse(BaseModel):
    report_id: str
    workflow_id: str
    algorithm: str
    key_id: str
    schema_version: str


class ReportIndex(BaseModel):
    workflow_id: str
    reports: list[EncryptedReportResponse]
    count: int


class LLMReportRequest(BaseModel):
    fate_vector: dict[str, float]
    existence_rank: str = "stable"
    provider: str = ""
    model: str = ""
    language: str = "en"
    style: str = "executive_summary"
    robustness: float | None = None
    sensitivity: float | None = None
    compatibility: float | None = None
    lift: float | None = None
    possibility: float | None = None
    aftermath: float | None = None


class LLMReportResponse(BaseModel):
    report: str
    provider_used: str
    model_used: str
    latency_ms: float | None = None
    tokens_used: dict | None = None
    error: str | None = None
    generated_at: str | None = None
