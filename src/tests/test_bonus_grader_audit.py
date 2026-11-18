"""Comprehensive unit and metamorphic tests for Bonus B7: Grader Audit.

Tests metamorphic relations across grader_a, grader_b, and grader_c,
verifying business rule consistency and metamorphic invariants.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from bonus.grader_audit import (
    evaluate_claim_delay_mr,
    evaluate_cross_shape_isolation_mr,
    evaluate_duplicate_mr,
    evaluate_infra_mr,
    evaluate_order_invariance_mr,
    load_fixture,
    run_full_audit,
)


@pytest.fixture(scope="module")
def fixture_claim_delay():
    return load_fixture("metamorphic_claim_delay.json")


@pytest.fixture(scope="module")
def fixture_infra():
    return load_fixture("metamorphic_infra.json")


@pytest.fixture(scope="module")
def fixture_duplicate():
    return load_fixture("metamorphic_duplicate.json")


def test_metamorphic_claim_delay_business_rule(fixture_claim_delay):
    """Business rule verification: delay_days 2 vs 3 under POL-2026-11 SHIP-LATE-03.

    - 2 days: below min_delay_days (3) -> Quote 0 VND (reason: no_entitlement).
    - 3 days: meets threshold -> Quote 35,000 VND shipping fee (reason: entitled).
    """
    res = evaluate_claim_delay_mr(fixture_claim_delay)
    assert res["status"] == "PASS"
    assert res["quote_a_vnd"] == 0, "Delay 2 days must not be entitled to refund"
    assert res["quote_b_vnd"] == 35000, "Delay 3 days must entitle full shipping fee"
    assert res["quote_b_reason"] == "entitled"


@pytest.mark.parametrize("grader_name", ["grader_a", "grader_b", "grader_c"])
def test_metamorphic_infra_errors_relation(grader_name, fixture_infra):
    """MR: Infrastructure errors (timeouts, host crashes) must not decrease pass rate.

    - grader_b: PASS (passed=None ignores infra errors in graded pass rate).
    - grader_a: PASS (passed=None ignores infra errors in graded pass rate).
    - grader_c: FAILS because it marks infra_error as passed=False, unfairly
      penalizing agent shapes for platform/timeout errors (pass rate drops from 0.75 to 0.5625).
    """
    mod = importlib.import_module(f"grader_audit.{grader_name}")
    res = evaluate_infra_mr(mod, fixture_infra)

    if grader_name == "grader_c":
        assert res["status"] == "FAIL", "grader_c must be caught failing infra error invariance"
        assert res["diff_pass_rate"] == pytest.approx(-0.1875, abs=1e-4)
    else:
        assert res["status"] == "PASS", f"{grader_name} must preserve pass rate under infra errors"
        assert res["diff_pass_rate"] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("grader_name", ["grader_a", "grader_b", "grader_c"])
def test_metamorphic_duplicate_relation(grader_name, fixture_duplicate):
    """MR: Duplicating input trials must keep rates identical and double totals.

    - grader_b: PASS (rates stay identical, totals exactly double: ratio = 2.0).
    - grader_c: PASS (rates stay identical, totals exactly double: ratio = 2.0).
    - grader_a: FAILS because it accumulates 'extra' costs for unique claim_ids,
      breaking linear scaling (cost ratio is 1.6684 instead of 2.0, cost/success drops by 5.22).
    """
    mod = importlib.import_module(f"grader_audit.{grader_name}")
    res = evaluate_duplicate_mr(mod, fixture_duplicate)

    if grader_name == "grader_a":
        assert res["status"] == "FAIL", "grader_a must be caught failing duplicate scaling"
        assert res["ratio_total_cost"] != pytest.approx(2.0, abs=1e-3)
        assert res["diff_cost_per_success"] != pytest.approx(0.0, abs=1e-3)
    else:
        assert res["status"] == "PASS", f"{grader_name} must satisfy duplicate invariance"
        assert res["ratio_total_cost"] == pytest.approx(2.0, abs=1e-4)
        assert res["diff_cost_per_success"] == pytest.approx(0.0, abs=1e-4)


@pytest.mark.parametrize("grader_name", ["grader_a", "grader_b", "grader_c"])
def test_metamorphic_new_relation_cross_shape_isolation(grader_name, fixture_infra):
    """MR 4 (NEW): Cross-Shape Data Isolation.

    Adding trials from a different shape ('single') must not modify or pollute
    the summary statistics of the target shape ('workflow').
    All 3 candidate graders pass this partition isolation test.
    """
    mod = importlib.import_module(f"grader_audit.{grader_name}")
    res = evaluate_cross_shape_isolation_mr(mod, fixture_infra["a"])
    assert res["status"] == "PASS", f"{grader_name} must maintain cross-shape data isolation"
    assert len(res["mismatches"]) == 0


@pytest.mark.parametrize("grader_name", ["grader_a", "grader_b", "grader_c"])
def test_metamorphic_new_relation_permutation_invariance(grader_name, fixture_duplicate):
    """MR 5 (NEW): Permutation / Trial Order Invariance.

    Shuffling the order of trials must produce identical statistical aggregates.
    - grader_b: PASS (order-independent).
    - grader_c: PASS (order-independent).
    - grader_a: FAILS because its 'extra' cost accumulation depends on which
      seed trial of a given claim_id is encountered first in the list.
    """
    mod = importlib.import_module(f"grader_audit.{grader_name}")
    res = evaluate_order_invariance_mr(mod, fixture_duplicate["a"], seed=42)

    if grader_name == "grader_a":
        assert res["status"] == "FAIL", "grader_a must fail order invariance due to first-seen claim dependency"
    else:
        assert res["status"] == "PASS", f"{grader_name} must be invariant under trial permutations"


def test_bonus_audit_report_generation(tmp_path):
    """Verify that run_full_audit generates a valid, complete audit report."""
    report_file = tmp_path / "bonus_grader_audit.json"
    data = run_full_audit(report_file)

    assert report_file.is_file()
    assert data["sound_grader"] == "grader_b"
    assert set(data["defective_graders"]) == {"grader_a", "grader_c"}
    assert data["graders"]["grader_b"]["verdict"] == "SOUND / CORRECT"
    assert data["graders"]["grader_a"]["verdict"] == "DEFECTIVE"
    assert data["graders"]["grader_c"]["verdict"] == "DEFECTIVE"
