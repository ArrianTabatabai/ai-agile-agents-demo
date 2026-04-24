import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "docs" / "policy.json"


@dataclass
class Decision:
    decision: str                 # "approve" | "reject" | "refer"
    reason_ids: List[str]
    reasons: List[str]


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        policy = json.load(f)

    # sort by priority ascending (lower runs first)
    rules = policy.get("rules", [])
    rules.sort(key=lambda r: r.get("priority", 999999))
    policy["rules"] = rules
    return policy


def _matches(conditions: Dict[str, Any], applicant: Dict[str, Any]) -> bool:
    # Supported condition operators (minimal set for now)
    for key, value in conditions.items():
        if key.endswith("_lt"):
            field = key[:-3]
            if applicant.get(field) is None or float(applicant[field]) >= float(value):
                return False
        elif key.endswith("_gt"):
            field = key[:-3]
            if applicant.get(field) is None or float(applicant[field]) <= float(value):
                return False
        elif key.endswith("_eq"):
            field = key[:-3]
            if applicant.get(field) != value:
                return False
        else:
            # direct boolean / equality match
            if applicant.get(key) != value:
                return False
    return True


def evaluate(applicant: Dict[str, Any], policy: Optional[Dict[str, Any]] = None) -> Decision:
    """
    Evaluate an applicant against the policy.

    This version collects all matching rules (in priority order) and then computes
    an overall decision with severity override semantics:
      - reject overrides refer and approve
      - refer overrides approve
      - approve if no higher severity triggered
    """
    if policy is None:
        policy = load_policy()

    reason_ids: List[str] = []
    reasons: List[str] = []
    matched_decisions: List[str] = []

    for rule in policy.get("rules", []):
        rid = rule["id"]
        decision = rule["decision"]
        reason = rule.get("reason", "")
        conditions = rule.get("conditions", {})

        if _matches(conditions, applicant):
            reason_ids.append(rid)
            reasons.append(reason)
            matched_decisions.append(decision)

    if len(reason_ids) == 0:
        return Decision(
            decision=policy.get("default_decision", "approve"),
            reason_ids=[],
            reasons=[]
        )

    # Severity: reject > refer > approve
    overall = "approve"
    if any(d == "reject" for d in matched_decisions):
        overall = "reject"
    elif any(d == "refer" for d in matched_decisions):
        overall = "refer"

    return Decision(decision=overall, reason_ids=reason_ids, reasons=reasons)