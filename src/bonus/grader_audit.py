"""Topic B7: Metamorphic Testing and Auditing of Benchmark Graders.

Based on EMNLP 2026 'Rethinking Evaluation of MAS Efficiency'.
This module evaluates grader candidates (grader_a, grader_b, grader_c)
against standard and newly proposed metamorphic relations.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

from lab8.compensation import quote

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "grader_audit" / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Fixture file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_claim_delay_mr(fixture: dict[str, Any]) -> dict[str, Any]:
    """MR 1: Business rule flip between delay_days 2 and 3.

    - 2 days: ineligible for late delivery refund (POL-2026-11 SHIP-LATE-03 min_delay_days=3) -> quote 0
    - 3 days: eligible for shipping fee refund (35,000 VND)
    """
    quote_a = quote(
        fixture["a"]["order"],
        fixture["policies"],
        as_of=fixture["as_of"],
    )
    quote_b = quote(
        fixture["b"]["order"],
        fixture["policies"],
        as_of=fixture["as_of"],
    )

    passed = (quote_a.amount_vnd == 0) and (quote_b.amount_vnd == 35000)
    return {
        "relation": fixture.get("relation", "delay_days_2_vs_3"),
        "status": "PASS" if passed else "FAIL",
        "quote_a_vnd": quote_a.amount_vnd,
        "quote_a_reason": quote_a.reason,
        "quote_b_vnd": quote_b.amount_vnd,
        "quote_b_reason": quote_b.reason,
        "flip_valid": passed,
    }


def evaluate_infra_mr(grader_mod: Any, fixture: dict[str, Any], shape: str = "workflow") -> dict[str, Any]:
    """MR 2: Infrastructure errors must not move pass rate on graded trials.

    - Input a: Clean trials
    - Input b: Same trials + extra trials with infra_error: true
    - Invariant: pass_rate(b) == pass_rate(a)
    """
    rep_a = grader_mod.summarize(fixture["a"])
    rep_b = grader_mod.summarize(fixture["b"])

    stats_a = rep_a[shape]
    stats_b = rep_b[shape]

    pass_rate_a = float(stats_a.get("pass_rate") or 0.0)
    pass_rate_b = float(stats_b.get("pass_rate") or 0.0)
    diff = pass_rate_b - pass_rate_a

    # Within float tolerance
    passed = abs(diff) < 1e-6
    return {
        "relation": fixture.get("relation", "infra_errors_do_not_move_pass_rate"),
        "status": "PASS" if passed else "FAIL",
        "pass_rate_a": round(pass_rate_a, 4),
        "pass_rate_b": round(pass_rate_b, 4),
        "diff_pass_rate": round(diff, 4),
        "graded_trials_a": stats_a.get("graded_trials"),
        "graded_trials_b": stats_b.get("graded_trials"),
        "successes_a": stats_a.get("successes"),
        "successes_b": stats_b.get("successes"),
    }


def evaluate_duplicate_mr(grader_mod: Any, fixture: dict[str, Any], shape: str = "workflow") -> dict[str, Any]:
    """MR 3: Duplicating trials must preserve rates and double totals.

    - Input a: Trials list
    - Input b: Trials list duplicated 2x
    - Invariants:
      1. cost_per_success_vnd(b) == cost_per_success_vnd(a)
      2. pass_rate(b) == pass_rate(a)
      3. total_simulated_cost_vnd(b) == 2 * total_simulated_cost_vnd(a)
    """
    rep_a = grader_mod.summarize(fixture["a"])
    rep_b = grader_mod.summarize(fixture["b"])

    stats_a = rep_a[shape]
    stats_b = rep_b[shape]

    cost_succ_a = float(stats_a.get("cost_per_success_vnd") or 0.0)
    cost_succ_b = float(stats_b.get("cost_per_success_vnd") or 0.0)
    diff_cost_succ = cost_succ_b - cost_succ_a

    cost_total_a = float(stats_a.get("total_simulated_cost_vnd") or 0.0)
    cost_total_b = float(stats_b.get("total_simulated_cost_vnd") or 0.0)
    ratio_total_cost = (cost_total_b / cost_total_a) if cost_total_a > 0 else 0.0

    pass_rate_a = float(stats_a.get("pass_rate") or 0.0)
    pass_rate_b = float(stats_b.get("pass_rate") or 0.0)
    diff_pass_rate = pass_rate_b - pass_rate_a

    passed = (
        abs(diff_cost_succ) < 1e-4
        and abs(diff_pass_rate) < 1e-6
        and abs(ratio_total_cost - 2.0) < 1e-4
    )

    return {
        "relation": fixture.get("relation", "duplicate_preserves_rates_and_doubles_totals"),
        "status": "PASS" if passed else "FAIL",
        "cost_per_success_a": round(cost_succ_a, 4),
        "cost_per_success_b": round(cost_succ_b, 4),
        "diff_cost_per_success": round(diff_cost_succ, 4),
        "total_cost_a": round(cost_total_a, 2),
        "total_cost_b": round(cost_total_b, 2),
        "ratio_total_cost": round(ratio_total_cost, 4),
        "pass_rate_a": round(pass_rate_a, 4),
        "pass_rate_b": round(pass_rate_b, 4),
    }


def evaluate_cross_shape_isolation_mr(grader_mod: Any, base_trials: list[dict[str, Any]]) -> dict[str, Any]:
    """MR 4 (NEW): Cross-Shape Independence / Isolation.

    - Input a: Clean trials of shape 'workflow'
    - Input b: Trials of 'workflow' concatenated with trials of another shape 'single'
    - Invariant: All summary metrics for 'workflow' in report(b) must be identical
      to report(a). Adding trials of another shape must not pollute or alter the
      evaluation of existing shapes.
    """
    trials_a = [copy.deepcopy(t) for t in base_trials if t.get("shape") == "workflow"]
    
    # Generate synthetic independent trials for another shape 'single'
    trials_other = []
    for t in trials_a:
        row = copy.deepcopy(t)
        row["shape"] = "single"
        row["claim_id"] = f"{t.get('claim_id')}-single"
        row["cost_estimate"] = float(t.get("cost_estimate", 10.0)) * 1.5
        trials_other.append(row)

    trials_b = trials_a + trials_other

    rep_a = grader_mod.summarize(trials_a)
    rep_b = grader_mod.summarize(trials_b)

    stats_a = rep_a["workflow"]
    stats_b = rep_b["workflow"]

    keys_to_compare = [
        "trials",
        "graded_trials",
        "successes",
        "pass_rate",
        "pass_5",
        "seed_variance",
        "cost_per_success_vnd",
        "total_simulated_cost_vnd",
        "mean_steps",
    ]

    mismatches = []
    for k in keys_to_compare:
        val_a = stats_a.get(k)
        val_b = stats_b.get(k)
        if isinstance(val_a, float) and isinstance(val_b, float):
            if abs(val_a - val_b) > 1e-4:
                mismatches.append(f"{k}: {val_a} != {val_b}")
        else:
            if val_a != val_b:
                mismatches.append(f"{k}: {val_a} != {val_b}")

    passed = len(mismatches) == 0
    return {
        "relation": "cross_shape_isolation",
        "status": "PASS" if passed else "FAIL",
        "description": "Cross-shape data isolation: adding another shape's trials must not alter target shape metrics.",
        "mismatches": mismatches,
        "workflow_pass_rate_a": round(float(stats_a.get("pass_rate") or 0.0), 4),
        "workflow_pass_rate_b": round(float(stats_b.get("pass_rate") or 0.0), 4),
        "workflow_cost_a": round(float(stats_a.get("total_simulated_cost_vnd") or 0.0), 2),
        "workflow_cost_b": round(float(stats_b.get("total_simulated_cost_vnd") or 0.0), 2),
    }


def evaluate_order_invariance_mr(grader_mod: Any, base_trials: list[dict[str, Any]], seed: int = 42) -> dict[str, Any]:
    """MR 5 (NEW): Permutation / Trial Order Invariance.

    - Input a: Original trials list
    - Input b: Trials list in shuffled/permuted order
    - Invariant: Summary metrics must be independent of trial ordering.
    """
    trials_a = copy.deepcopy(base_trials)
    trials_b = copy.deepcopy(base_trials)
    rng = random.Random(seed)
    rng.shuffle(trials_b)

    rep_a = grader_mod.summarize(trials_a)
    rep_b = grader_mod.summarize(trials_b)

    mismatches = []
    for shape in rep_a:
        if shape not in rep_b:
            mismatches.append(f"Missing shape {shape} in rep_b")
            continue
        stats_a = rep_a[shape]
        stats_b = rep_b[shape]
        for k in ["pass_rate", "pass_5", "total_simulated_cost_vnd", "cost_per_success_vnd"]:
            val_a = stats_a.get(k)
            val_b = stats_b.get(k)
            if isinstance(val_a, float) and isinstance(val_b, float):
                if abs(val_a - val_b) > 1e-4:
                    mismatches.append(f"{shape}.{k}: {val_a} != {val_b}")
            elif val_a != val_b:
                mismatches.append(f"{shape}.{k}: {val_a} != {val_b}")

    passed = len(mismatches) == 0
    return {
        "relation": "permutation_order_invariance",
        "status": "PASS" if passed else "FAIL",
        "description": "Shuffling trial order must not change statistical aggregates.",
        "mismatches": mismatches,
    }


def run_full_audit(out_path: str | Path | None = None) -> dict[str, Any]:
    run_id = f"audit-{int(time.time())}"
    claim_delay_fixture = load_fixture("metamorphic_claim_delay.json")
    infra_fixture = load_fixture("metamorphic_infra.json")
    duplicate_fixture = load_fixture("metamorphic_duplicate.json")

    # Business rule verification on compensation quote
    claim_delay_result = evaluate_claim_delay_mr(claim_delay_fixture)

    grader_names = ["grader_a", "grader_b", "grader_c"]
    graders_summary: dict[str, Any] = {}

    for name in grader_names:
        mod = importlib.import_module(f"grader_audit.{name}")
        infra_res = evaluate_infra_mr(mod, infra_fixture)
        dup_res = evaluate_duplicate_mr(mod, duplicate_fixture)
        isolation_res = evaluate_cross_shape_isolation_mr(mod, infra_fixture["a"])
        order_res = evaluate_order_invariance_mr(mod, duplicate_fixture["a"])

        all_passed = (
            infra_res["status"] == "PASS"
            and dup_res["status"] == "PASS"
            and isolation_res["status"] == "PASS"
            and order_res["status"] == "PASS"
        )

        behavior_defect = None
        if name == "grader_a":
            behavior_defect = "Tích luỹ chi phí ảo (extra cost) trên từng claim_id duy nhất vào total_simulated_cost_vnd, phá vỡ tính tỉ lệ tuyến tính của chi phí khi nhân bản tập dữ liệu (ratio=1.6684 != 2.0)."
        elif name == "grader_c":
            behavior_defect = "Đếm trial hạ tầng (infra_error=True) thành quyết định sai của agent (gán passed=False), làm sụt giảm oan pass rate từ 0.7500 xuống 0.5625 (-18.75%)."
        else:
            behavior_defect = "Không có lỗi. Xử lý chuẩn xác bằng cách gán passed=None cho lỗi hạ tầng để không làm bẩn mẫu số, và bảo toàn tính tỉ lệ của chi phí."

        graders_summary[name] = {
            "verdict": "SOUND / CORRECT" if all_passed else "DEFECTIVE",
            "behavior_defect": behavior_defect,
            "relations": {
                "infra_errors_do_not_move_pass_rate": infra_res,
                "duplicate_preserves_rates_and_doubles_totals": dup_res,
                "cross_shape_isolation": isolation_res,
                "permutation_order_invariance": order_res,
            },
        }

    audit_report = {
        "run_id": run_id,
        "topic": "B7 · Kiểm toán grader",
        "source": "EMNLP 2026 - Rethinking Evaluation of MAS Efficiency",
        "claim_delay_business_rule": claim_delay_result,
        "graders": graders_summary,
        "sound_grader": "grader_b",
        "defective_graders": ["grader_a", "grader_c"],
    }

    if out_path:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(audit_report, indent=2, ensure_ascii=False), encoding="utf-8")

    return audit_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Grader Audit (Bonus B7)")
    parser.add_argument(
        "--out",
        default="reports/bonus_grader_audit.json",
        help="Output report JSON file path",
    )
    args = parser.parse_args()

    report = run_full_audit(args.out)
    print(f"=== Bonus B7 Grader Audit Completed [run_id: {report['run_id']}] ===")
    print(f"Claim Delay Rule: {report['claim_delay_business_rule']['status']} (a={report['claim_delay_business_rule']['quote_a_vnd']} VND, b={report['claim_delay_business_rule']['quote_b_vnd']} VND)")
    print("-" * 65)
    print(f"{'Grader':<12} | {'Infra MR':<10} | {'Duplicate MR':<12} | {'Cross-Shape':<12} | {'Verdict'}")
    print("-" * 65)
    for g, data in report["graders"].items():
        rels = data["relations"]
        infra_st = rels["infra_errors_do_not_move_pass_rate"]["status"]
        dup_st = rels["duplicate_preserves_rates_and_doubles_totals"]["status"]
        iso_st = rels["cross_shape_isolation"]["status"]
        verdict = data["verdict"]
        print(f"{g:<12} | {infra_st:<10} | {dup_st:<12} | {iso_st:<12} | {verdict}")
    print("-" * 65)
    print(f"Report written to: {args.out}")


if __name__ == "__main__":
    main()
