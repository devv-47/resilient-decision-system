from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ExecuteWorkflowRequest(BaseModel):
    request_id: str = Field(..., min_length=3, description="Unique idempotency key for the request")
    payload: Dict[str, Any] = Field(..., description="Business data for workflow evaluation")


class AuditLogResponse(BaseModel):
    stage_name: str
    rule_id: str
    field_evaluated: str
    actual_value: Optional[str]
    expected_condition: str
    passed: str
    reason: str
    timestamp: datetime

    class Config:
        from_attributes = True


class StateHistoryResponse(BaseModel):
    from_state: Optional[str]
    to_state: str
    note: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class WorkflowExecutionResponse(BaseModel):
    request_id: str
    workflow_name: str
    workflow_version: str
    current_state: str
    final_decision: Optional[str]
    decision_reason: Optional[str]
    retry_count: int
    idempotent_replay: bool = False
    external_data: Optional[Dict[str, Any]] = None
    audit_logs: List[AuditLogResponse] = []
    state_history: List[StateHistoryResponse] = []