from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class WorkflowRequest(Base):
    __tablename__ = "workflow_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    workflow_name = Column(String, index=True, nullable=False)
    workflow_version = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    external_data = Column(JSON, nullable=True)
    current_state = Column(String, default="RECEIVED", nullable=False)
    final_decision = Column(String, nullable=True)
    decision_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    state_history = relationship("StateHistory", back_populates="request", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="request", cascade="all, delete-orphan")


class StateHistory(Base):
    __tablename__ = "state_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("workflow_requests.request_id"), nullable=False)
    from_state = Column(String, nullable=True)
    to_state = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utc_now)

    request = relationship("WorkflowRequest", back_populates="state_history")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("workflow_requests.request_id"), nullable=False)
    stage_name = Column(String, nullable=False)
    rule_id = Column(String, nullable=False)
    field_evaluated = Column(String, nullable=False)
    actual_value = Column(String, nullable=True)
    expected_condition = Column(String, nullable=False)
    passed = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utc_now)

    request = relationship("WorkflowRequest", back_populates="audit_logs")



