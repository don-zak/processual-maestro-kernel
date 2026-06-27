from pydantic import BaseModel


class WorkflowCreateRequest(BaseModel):
    workflow_id: str
    goal: str
    steps: list[dict] = []


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    step_count: int


class WorkflowDetailResponse(BaseModel):
    workflow_id: str
    status: str
    steps: dict
    agents: list
