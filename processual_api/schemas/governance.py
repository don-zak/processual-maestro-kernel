from pydantic import BaseModel


class GovernanceReport(BaseModel):
    workflow_id: str
    runtime_mode: str
    policy: str


class FateReport(BaseModel):
    workflow_id: str
    fate_vector: dict[str, float]
    existence_rank: str
