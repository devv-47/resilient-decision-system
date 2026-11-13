from pathlib import Path
from typing import Any, Dict, Tuple
from sqlalchemy.orm import Session

from app.models import WorkflowRequest, StateHistory, AuditLog
from app.rule_engine import load_workflow_config, execute_stages, CONFIG_PATH
from app.external_service import external_simulator, ExternalDependencyError


class ValidationError(Exception):
    pass


def _record_transition(db: Session, request_obj: WorkflowRequest, to_state: str, note: str):
    from_state = request_obj.current_state
    request_obj.current_state = to_state
    db.add(StateHistory(
        request_id=request_obj.request_id,
        from_state=from_state,
        to_state=to_state,
        note=note
    ))


def run_workflow(
    db: Session,
    workflow_name: str,
    request_id: str,
    payload: Dict[str, Any],
    config_path: Path = CONFIG_PATH
) -> Tuple[WorkflowRequest, bool]:
    existing = db.query(WorkflowRequest).filter(WorkflowRequest.request_id == request_id).first()
    if existing:
        return existing, True

    workflow_cfg = load_workflow_config(workflow_name, config_path=config_path)

    missing = [f for f in workflow_cfg.get("required_fields", []) if f not in payload or payload[f] is None]
    if missing:
        raise ValidationError(f"Missing required payload fields: {', '.join(missing)}")

    req_record = WorkflowRequest(
        request_id=request_id,
        workflow_name=workflow_name,
        workflow_version=workflow_cfg.get("version", "1.0"),
        payload=payload,
        current_state="RECEIVED"
    )
    db.add(req_record)
    db.add(StateHistory(
        request_id=request_id,
        from_state=None,
        to_state="RECEIVED",
        note="Request accepted and validated"
    ))
    db.commit()
    db.refresh(req_record)

    ext_cfg = workflow_cfg.get("external_dependency")
    external_data: Dict[str, Any] = {}
    if ext_cfg:
        try:
            _record_transition(db, req_record, "FETCHING_EXTERNAL_DATA", f"Calling {ext_cfg['name']}")
            db.commit()

            external_data, retries_used = external_simulator.fetch_with_retry(
                service_name=ext_cfg["name"],
                request_id=request_id,
                payload=payload,
                max_retries=ext_cfg.get("max_retries", 3),
                base_delay=ext_cfg.get("retry_delay_seconds", 0.2)
            )
            req_record.external_data = external_data
            req_record.retry_count = retries_used
            _record_transition(
                db,
                req_record,
                "EXTERNAL_DATA_VERIFIED",
                f"Fetched data from {ext_cfg['name']} (retries={retries_used})"
            )
            db.commit()
        except ExternalDependencyError as exc:
            req_record.retry_count = ext_cfg.get("max_retries", 3)
            req_record.final_decision = "RETRY_LATER"
            req_record.decision_reason = str(exc)
            _record_transition(db, req_record, "DEPENDENCY_FAILED", str(exc))
            db.commit()
            db.refresh(req_record)
            return req_record, False

    try:
        if payload.get("simulate_partial_save_error"):
            raise RuntimeError("Simulated database write failure during decision commit")

        decision, reason, audit_entries = execute_stages(workflow_cfg, payload, external_data)

        for entry in audit_entries:
            db.add(AuditLog(request_id=request_id, **entry))

        req_record.final_decision = decision
        req_record.decision_reason = reason
        _record_transition(db, req_record, decision, reason)

        db.commit()
        db.refresh(req_record)
        return req_record, False

    except Exception as exc:
        db.rollback()
        req_record = db.query(WorkflowRequest).filter(WorkflowRequest.request_id == request_id).first()
        req_record.final_decision = "FAILED"
        req_record.decision_reason = f"Internal processing/persistence error: {exc}"
        _record_transition(db, req_record, "FAILED", f"Rolled back partial save: {exc}")
        db.commit()
        db.refresh(req_record)
        return req_record, False