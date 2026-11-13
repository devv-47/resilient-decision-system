# System Architecture & Engineering Tradeoffs

## 1. High-Level Architecture
The system is designed around strict separation of concerns across four layers:
1. **API & Schema Layer (`app/main.py`, `app/schemas.py`):** Exposes REST endpoints, validates payload structure, and maps domain exceptions to HTTP status codes (`404`, `422`).
2. **Workflow Orchestrator (`app/workflow_runner.py`):** Acts as the state-machine coordinator. Enforces idempotency, manages external dependency retries, records state transitions, and wraps decision persistence in atomic database transactions.
3. **Rule Evaluation Engine (`app/rule_engine.py`):** Pure, stateless logic that reads `configs/workflows.json` at runtime, evaluates operators (`>=`, `<=`, `==`, `!=`, `in`, etc.), executes multi-step `rule_group` checks, and routes `conditional_branch` rules.
4. **Persistence & Audit Layer (`app/models.py`, `app/database.py`):** Stores three normalized entities: `WorkflowRequest`, `StateHistory`, and `AuditLog`.

## 2. Data Flow & State Lifecycle
```text
Client Request (request_id + payload)
       │
       ▼
[1. Idempotency Lookup] ──(Exists)──► Return Cached Decision + Audit Trail
       │ (New Request)
       ▼
[2. Config & Required Field Validation] ──(Invalid)──► HTTP 422 Reject
       │ (Valid)
       ▼
[3. Persist State: RECEIVED]
       │
       ▼
[4. External Dependency Call + Exponential Backoff Retries]
       ├──(Exhausted)──► State: DEPENDENCY_FAILED / Decision: RETRY_LATER
       ▼ (Success)
[5. State: EXTERNAL_DATA_VERIFIED]
       │
       ▼
[6. Multi-Stage Rule Engine & Conditional Branching]
       │
       ▼
[7. Atomic DB Commit: AuditLogs + Final Decision + StateHistory]
       └──(DB Error)──► Rollback & Transition to State: FAILED