import time
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


class ExternalDependencyError(Exception):
    pass


class ExternalServiceSimulator:
    def __init__(self):
        self._attempt_tracker: Dict[str, int] = {}

    def _call_remote_api(self, service_name: str, request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = f"{service_name}:{request_id}"
        current_attempt = self._attempt_tracker.get(key, 0) + 1
        self._attempt_tracker[key] = current_attempt

        failures_to_simulate = int(payload.get("simulate_flaky_failures", 0))
        if current_attempt <= failures_to_simulate:
            raise ExternalDependencyError(
                f"{service_name} timeout/503 error on attempt {current_attempt}"
            )

        if service_name == "credit_bureau_service":
            return {
                "kyc_verified": payload.get("mock_kyc_verified", True),
                "credit_score": payload.get("mock_credit_score", 780),
                "bureau_reference_id": f"BUR-{request_id[-6:].upper()}"
            }
        elif service_name == "gst_compliance_service":
            return {
                "is_blacklisted": payload.get("mock_is_blacklisted", False),
                "gst_status": "ACTIVE",
                "compliance_ref_id": f"GST-{request_id[-6:].upper()}"
            }

        return {"status": "OK"}

    def fetch_with_retry(
        self,
        service_name: str,
        request_id: str,
        payload: Dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 0.2
    ) -> Tuple[Dict[str, Any], int]:
        retries_used = 0
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                data = self._call_remote_api(service_name, request_id, payload)
                return data, retries_used
            except ExternalDependencyError as exc:
                last_error = exc
                logger.warning(f"[{request_id}] Attempt {attempt}/{max_retries} failed: {exc}")
                if attempt < max_retries:
                    retries_used += 1
                    time.sleep(base_delay * (2 ** (attempt - 1)))

        raise ExternalDependencyError(
            f"External dependency '{service_name}' failed after {max_retries} attempts: {last_error}"
        )


external_simulator = ExternalServiceSimulator()