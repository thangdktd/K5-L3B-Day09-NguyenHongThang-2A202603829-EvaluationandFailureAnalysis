import copy

from lab9 import gate


SPEC = {
    "eval_set_version": "v1",
    "metrics": [
        {"id": "pass_rate", "grader": "lab8.metrics.trial_pass", "level": "outcome"},
        {"id": "pass_5", "grader": "lab8.metrics.summarize", "level": "outcome"},
    ],
}


def _report():
    rows = [
        {"item_id": f"E-{item}", "seed": 11, "pass_rate": True, "slices": []}
        for item in range(2)
    ]
    return {
        "manifest": {"eval_set_sha": "same", "items": 2, "seeds": [11]},
        "rows": rows,
        "metrics": {"pass_rate": 1.0, "pass_5": 1.0},
        "evaluator_failures": [],
    }


def test_integrity_accepts_summary_metric_at_report_level():
    report = _report()

    assert gate.integrity_check(report, report, SPEC) == []


def test_integrity_rejects_missing_row_level_evaluator_value():
    baseline = _report()
    pr = copy.deepcopy(baseline)
    del pr["rows"][0]["pass_rate"]

    problems = gate.integrity_check(pr, baseline, SPEC)

    assert any("row E-0@11 has missing pass_rate" in problem for problem in problems)
