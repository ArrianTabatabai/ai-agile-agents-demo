import json
from pathlib import Path

from app.rules import evaluate, load_policy

ROOT = Path(__file__).resolve().parents[1]

def test_golden_cases_match_expected():
    policy = load_policy(ROOT / "docs" / "policy.json")

    cases_path = ROOT / "docs" / "golden_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    for case in cases:
        out = evaluate(case["input"], policy=policy)
        assert out.decision == case["expected"]["decision"], f"Case {case['name']} decision mismatch"
        assert out.reason_ids == case["expected"]["reason_ids"], f"Case {case['name']} reasons mismatch"