# Decision Explanation Examples

## Example 1: Happy Path (`APPROVED`)
**Endpoint:** `POST /api/v1/workflows/loan_approval/execute`

**Input:**
```json
{
  "request_id": "REQ-2026-101",
  "payload": {
    "applicant_name": "Dev Shrivas",
    "age": 24,
    "monthly_income": 65000,
    "loan_amount": 200000,
    "pan_number": "ABCDE1234F",
    "mock_credit_score": 790
  }
}