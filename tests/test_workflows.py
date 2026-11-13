import json
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.workflow_runner import run_workflow

TEST_DB_URL = "sqlite:///./test_decision_system.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_1_happy_path_loan_approved():
    response = client.post(
        "/api/v1/workflows/loan_approval/execute",
        json={
            "request_id": "REQ-HAPPY-001",
            "payload": {
                "applicant_name": "Dev Shrivas",
                "age": 24,
                "monthly_income": 65000,
                "loan_amount": 200000,
                "pan_number": "ABCDE1234F",
                "mock_credit_score": 790
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["final_decision"] == "APPROVED"
    assert data["current_state"] == "APPROVED"
    assert len(data["audit_logs"]) > 0
    assert len(data["state_history"]) == 4


def test_2_invalid_input_missing_required_field():
    response = client.post(
        "/api/v1/workflows/loan_approval/execute",
        json={
            "request_id": "REQ-INVALID-001",
            "payload": {
                "applicant_name": "Test User",
                "age": 25
            }
        }
    )
    assert response.status_code == 422
    assert "Missing required payload fields" in response.json()["detail"]


def test_3_idempotency_duplicate_request():
    payload = {
        "request_id": "REQ-IDEMP-001",
        "payload": {
            "applicant_name": "Rohan Verma",
            "age": 28,
            "monthly_income": 50000,
            "loan_amount": 150000,
            "pan_number": "PQRSX5678K",
            "mock_credit_score": 760
        }
    }
    first = client.post("/api/v1/workflows/loan_approval/execute", json=payload)
    second = client.post("/api/v1/workflows/loan_approval/execute", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    assert first.json()["final_decision"] == second.json()["final_decision"]


def test_4_dependency_transient_failure_and_retry_success():
    response = client.post(
        "/api/v1/workflows/loan_approval/execute",
        json={
            "request_id": "REQ-RETRY-001",
            "payload": {
                "applicant_name": "Ankit Sharma",
                "age": 30,
                "monthly_income": 70000,
                "loan_amount": 300000,
                "pan_number": "LMNOP9876Q",
                "simulate_flaky_failures": 2,
                "mock_credit_score": 785
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["retry_count"] == 2
    assert data["final_decision"] == "APPROVED"


def test_5_dependency_permanent_failure_handling():
    response = client.post(
        "/api/v1/workflows/loan_approval/execute",
        json={
            "request_id": "REQ-FAIL-001",
            "payload": {
                "applicant_name": "Suresh Kumar",
                "age": 32,
                "monthly_income": 55000,
                "loan_amount": 250000,
                "pan_number": "WXYZB4321M",
                "simulate_flaky_failures": 5
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "DEPENDENCY_FAILED"
    assert data["final_decision"] == "RETRY_LATER"


def test_6_partial_save_failure_rollback():
    response = client.post(
        "/api/v1/workflows/loan_approval/execute",
        json={
            "request_id": "REQ-ROLLBACK-001",
            "payload": {
                "applicant_name": "Neha Gupta",
                "age": 27,
                "monthly_income": 60000,
                "loan_amount": 180000,
                "pan_number": "GHJKL1122N",
                "simulate_partial_save_error": True
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "FAILED"
    assert data["final_decision"] == "FAILED"
    assert len(data["audit_logs"]) == 0


def test_7_rule_change_via_configuration(tmp_path):
    orig_cfg = Path(__file__).resolve().parent.parent / "configs" / "workflows.json"
    custom_cfg = tmp_path / "custom_workflows.json"
    shutil.copy(orig_cfg, custom_cfg)

    with open(custom_cfg, "r", encoding="utf-8") as f:
        cfg_data = json.load(f)

    # Change minimum income requirement from 25000 to 100000 without touching Python code
    cfg_data["workflows"]["loan_approval"]["stages"][1]["rules"][0]["value"] = 100000
    with open(custom_cfg, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f)

    db = TestingSessionLocal()
    try:
        record, _ = run_workflow(
            db=db,
            workflow_name="loan_approval",
            request_id="REQ-CFG-CHANGE-001",
            payload={
                "applicant_name": "Aman Singh",
                "age": 26,
                "monthly_income": 60000,
                "loan_amount": 100000,
                "pan_number": "QRSTU3344P",
                "mock_credit_score": 800
            },
            config_path=custom_cfg
        )
        assert record.final_decision == "REJECTED"
        assert "R4_MIN_INCOME" in record.decision_reason
    finally:
        db.close()