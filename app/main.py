import json
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import WorkflowRequest
from app.schemas import ExecuteWorkflowRequest, WorkflowExecutionResponse
from app.workflow_runner import run_workflow, ValidationError
from app.rule_engine import CONFIG_PATH

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Resilient Configurable Workflow Decision System",
    description="Config-driven decision engine with state lifecycle, retries, idempotency, and audit trails.",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/workflows")
def list_workflows():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "available_workflows": {
            name: {
                "version": cfg.get("version"),
                "description": cfg.get("description"),
                "required_fields": cfg.get("required_fields")
            }
            for name, cfg in data.get("workflows", {}).items()
        }
    }


@app.post("/api/v1/workflows/{workflow_name}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow_endpoint(
    workflow_name: str,
    body: ExecuteWorkflowRequest,
    db: Session = Depends(get_db)
):
    try:
        record, replayed = run_workflow(
            db=db,
            workflow_name=workflow_name,
            request_id=body.request_id,
            payload=body.payload
        )
        return WorkflowExecutionResponse(
            request_id=record.request_id,
            workflow_name=record.workflow_name,
            workflow_version=record.workflow_version,
            current_state=record.current_state,
            final_decision=record.final_decision,
            decision_reason=record.decision_reason,
            retry_count=record.retry_count,
            idempotent_replay=replayed,
            external_data=record.external_data,
            audit_logs=record.audit_logs,
            state_history=record.state_history
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/v1/requests/{request_id}", response_model=WorkflowExecutionResponse)
def get_request_audit(request_id: str, db: Session = Depends(get_db)):
    record = db.query(WorkflowRequest).filter(WorkflowRequest.request_id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
    return WorkflowExecutionResponse(
        request_id=record.request_id,
        workflow_name=record.workflow_name,
        workflow_version=record.workflow_version,
        current_state=record.current_state,
        final_decision=record.final_decision,
        decision_reason=record.decision_reason,
        retry_count=record.retry_count,
        idempotent_replay=False,
        external_data=record.external_data,
        audit_logs=record.audit_logs,
        state_history=record.state_history
    )