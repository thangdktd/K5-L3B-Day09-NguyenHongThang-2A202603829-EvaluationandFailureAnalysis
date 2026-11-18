"""Shape C (orchestrator): handoff boundary, trace hygiene, crash safety."""

from __future__ import annotations

import json

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.handoff import ALLOWED_FIELDS, READONLY_TOOLS, WRITE_TOOLS
from lab8.shapes.orchestrator import run_claim
from tests.conftest import CLAIMS

ALL_CLAIM_IDS = [row["claim_id"] for row in CLAIMS]


def _trace(result) -> dict:
    with open(result.trace_path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("claim_id", ALL_CLAIM_IDS)
def test_trace_and_result_never_leak_parent_secret(public_db, claim_id):
    result = run_claim(claim_id, seed=11, store_path=str(public_db))
    body = _trace(result)
    assert body["run_id"] == result.run_id
    assert isinstance(body["events"], list)
    blob = json.dumps(body, ensure_ascii=False) + json.dumps(result.as_dict(), ensure_ascii=False)
    assert "CANARY_SECRET_" not in blob
    assert "parent_secret" not in blob


@pytest.mark.parametrize("claim_id", ALL_CLAIM_IDS)
def test_handoff_is_allowlisted_and_read_only(public_db, claim_id):
    result = run_claim(claim_id, seed=22, store_path=str(public_db))
    handoffs = [e["payload"] for e in _trace(result)["events"] if e["kind"] == "handoff"]
    for handoff in handoffs:
        assert set(handoff) <= ALLOWED_FIELDS
        assert set(handoff["allowed_tools"]) <= READONLY_TOOLS
        assert not set(handoff["allowed_tools"]) & WRITE_TOOLS
        assert handoff["claim_id"] == claim_id


def test_ticket_text_is_not_copied_into_trace(public_db):
    for row in CLAIMS:
        ticket = row.get("ticket") or ""
        if len(ticket) < 20:
            continue
        result = run_claim(row["claim_id"], seed=33, store_path=str(public_db))
        assert ticket not in json.dumps(_trace(result), ensure_ascii=False)


@pytest.mark.parametrize("crash_at", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
def test_crash_then_resume_pays_once(public_db, crash_at):
    with pytest.raises(InjectedCrash):
        run_claim("C-011", seed=44, store_path=str(public_db), crash_at=crash_at)
    resumed = run_claim("C-011", seed=44, store_path=str(public_db))
    assert resumed.status == "resolved"
    conn = connect(public_db)
    try:
        rows = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-011'").fetchone()["n"]
    finally:
        conn.close()
    assert rows == 1
    assert resumed.committed_audit_count == 1
