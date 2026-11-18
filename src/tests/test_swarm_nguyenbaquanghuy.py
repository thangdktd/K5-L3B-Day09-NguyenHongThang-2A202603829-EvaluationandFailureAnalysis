"""Personal tests for Shape D — swarm reference (Nguyen Ba Quang Huy).

Swarm is provided as a baseline. These tests lock the documented public
weakness (T02 seed 55) and prove the reference still keeps secrets out of
trace/result artifacts.
"""

from __future__ import annotations

import json

from lab8.db import connect, init_store
from lab8.metrics import artifact_blob, trial_pass
from lab8.shapes.swarm_reference import run_claim
from tests.conftest import BY_ID, CLAIMS, WORLD


def _store(tmp_path, name: str):
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def test_swarm_reference_weakness_visible_on_t02_seed_55(tmp_path):
    """Seed 55 must trust the ticket delay and fail the T02 label; seed 11 must pass."""
    outcomes = {}
    for seed in (11, 55):
        store = _store(tmp_path, f"swarm-t02-{seed}.sqlite")
        result = run_claim("C-002", seed=seed, store_path=str(store))
        conn = connect(store)
        try:
            outcomes[seed] = trial_pass(result.as_dict(), BY_ID["C-002"]["expected"], conn)[0]
        finally:
            conn.close()
    assert outcomes == {11: True, 55: False}


def test_swarm_t02_seed_55_records_model_override(tmp_path):
    """When the weakness fires, the trace must record the ticket-driven override."""
    store = _store(tmp_path, "swarm-t02-override.sqlite")
    result = run_claim("C-002", seed=55, store_path=str(store))
    assert result.status == "resolved"
    assert result.proposal_amount == 20000
    with open(result.trace_path, encoding="utf-8") as fh:
        body = json.load(fh)
    overrides = [event for event in body["events"] if event.get("kind") == "model_override"]
    assert overrides, "expected model_override event when swarm trusts the ticket"
    assert overrides[0]["payload"]["delay_days"] == 5


def test_swarm_trace_and_result_never_leak_canary_secret(tmp_path):
    """Reference swarm must keep CANARY_SECRET_* out of RunResult and trace files."""
    store = _store(tmp_path, "swarm-secret.sqlite")
    result = run_claim("C-001", seed=11, store_path=str(store))
    blob = artifact_blob(result.as_dict())
    assert "CANARY_SECRET_" not in blob
    assert "parent_secret" not in blob
