# Resilient Configurable Workflow Decision System

A config-driven, fault-tolerant workflow decision engine built with **Python, FastAPI, and SQLAlchemy**. It evaluates incoming business requests across multi-step stages, integrates external dependencies with retry/backoff resilience, enforces idempotency, tracks full state transitions, and records explainable rule-level audit trails.

## Key Features
- **Zero-Code Rule & Workflow Configurability:** Define multiple workflows (`loan_approval`, `vendor_approval`), mandatory rules, thresholds, and conditional branches inside `configs/workflows.json`.
- **Multi-Stage Evaluation & Conditional Routing:** Supports sequential `rule_group` stages and `conditional_branch` routing (`APPROVED`, `REJECTED`, `MANUAL_REVIEW`).
- **Idempotency Protection:** Duplicate `request_id` submissions return the persisted outcome without re-triggering external dependencies or duplicating audit entries.
- **Resilient External Dependencies:** Exponential backoff retry mechanism (`ExternalServiceSimulator`) for transient external service failures, plus graceful degradation (`RETRY_LATER`) when retries are exhausted.
- **Atomic Persistence & Rollback:** Guards against partial save failures using transactional commits and rollback recovery.
- **Full State Lifecycle & Explainable Audit Logs:** Every state transition (`RECEIVED` -> `FETCHING_EXTERNAL_DATA` -> `EXTERNAL_DATA_VERIFIED` -> `APPROVED/REJECTED/MANUAL_REVIEW`) and rule check is persisted and queryable.

## Project Structure
```text
resilient-decision-system/
├── app/
│   ├── main.py              # FastAPI REST endpoints
│   ├── database.py          # SQLite database engine & session setup
│   ├── models.py            # ORM models (WorkflowRequest, StateHistory, AuditLog)
│   ├── schemas.py           # Pydantic request/response contracts
│   ├── rule_engine.py       # Dynamic config parser, operator evaluator, stage runner
│   ├── external_service.py  # External API simulator with exponential backoff retries
│   └── workflow_runner.py   # Orchestrator (idempotency, state machine, DB transactions)
├── configs/
│   └── workflows.json       # Declarative workflow and rule definitions
├── tests/
│   └── test_workflows.py    # Automated pytest coverage for all edge cases
├── ARCHITECTURE.md          # System design, data flow, tradeoffs & scaling plan
├── EXAMPLES.md              # Sample inputs, rule traces, and decision explanations
└── requirements.txt