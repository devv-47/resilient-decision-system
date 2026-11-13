import json
import operator
from pathlib import Path
from typing import Any, Dict, List, Tuple

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "workflows.json"

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def load_workflow_config(workflow_name: str, config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    workflows = data.get("workflows", {})
    if workflow_name not in workflows:
        raise ValueError(f"Workflow '{workflow_name}' not found in configuration.")
    return workflows[workflow_name]


def resolve_field_value(field_path: str, payload: Dict[str, Any], external_data: Dict[str, Any]) -> Any:
    if field_path.startswith("external."):
        key = field_path.split(".", 1)[1]
        return external_data.get(key)
    return payload.get(field_path)


def evaluate_single_rule(
    rule: Dict[str, Any],
    payload: Dict[str, Any],
    external_data: Dict[str, Any]
) -> Tuple[bool, Any]:
    field = rule["field"]
    op_symbol = rule["operator"]
    expected = rule["value"]

    actual = resolve_field_value(field, payload, external_data)
    if actual is None:
        return False, None

    op_func = OPERATORS.get(op_symbol)
    if not op_func:
        raise ValueError(f"Unsupported operator: {op_symbol}")

    try:
        return bool(op_func(actual, expected)), actual
    except TypeError:
        return False, actual


def execute_stages(
    workflow_cfg: Dict[str, Any],
    payload: Dict[str, Any],
    external_data: Dict[str, Any]
) -> Tuple[str, str, List[Dict[str, Any]]]:
    audit_entries: List[Dict[str, Any]] = []

    for stage in workflow_cfg.get("stages", []):
        stage_name = stage["stage_name"]
        stage_type = stage["type"]

        if stage_type == "rule_group":
            stage_failed = False
            fail_reason = ""

            for rule in stage.get("rules", []):
                passed, actual = evaluate_single_rule(rule, payload, external_data)
                audit_entries.append({
                    "stage_name": stage_name,
                    "rule_id": rule["rule_id"],
                    "field_evaluated": rule["field"],
                    "actual_value": str(actual),
                    "expected_condition": f"{rule['operator']} {rule['value']}",
                    "passed": "TRUE" if passed else "FALSE",
                    "reason": rule["reason"]
                })
                if not passed and not stage_failed:
                    stage_failed = True
                    fail_reason = f"[{rule['rule_id']}] {rule['reason']} (actual={actual})"

            if stage_failed:
                decision = stage.get("on_fail", "REJECTED")
                return decision, fail_reason, audit_entries

        elif stage_type == "conditional_branch":
            for cond in stage.get("conditions", []):
                matched, actual = evaluate_single_rule(cond, payload, external_data)
                audit_entries.append({
                    "stage_name": stage_name,
                    "rule_id": cond["rule_id"],
                    "field_evaluated": cond["field"],
                    "actual_value": str(actual),
                    "expected_condition": f"{cond['operator']} {cond['value']}",
                    "passed": "TRUE" if matched else "FALSE",
                    "reason": cond["reason"]
                })
                if matched:
                    action = cond["action"]
                    reason = f"[{cond['rule_id']}] {cond['reason']} (actual={actual})"
                    return action, reason, audit_entries

            default_action = stage.get("default_action", "APPROVED")
            return default_action, "All mandatory, threshold, and risk checks passed.", audit_entries

    return "APPROVED", "Workflow completed successfully.", audit_entries