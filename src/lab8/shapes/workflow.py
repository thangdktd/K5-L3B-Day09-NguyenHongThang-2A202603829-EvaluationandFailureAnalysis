"""Shape A — deterministic refund workflow (CP2 + CP3).

Money is computed by code (`compute_compensation`), never by the model. The
host (`durability.issue_refund`) is the only writer and enforces approval,
ownership, per-order caps and idempotency.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace
from lab8.tools import compute_compensation, get_claim_view, lookup_order


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    run_id = make_run_id("workflow", claim_id, seed)
    trace = Trace(run_id)

    # 1. Load the claim view (safe fields only — no parent_secret, no ticket text).
    claim_view = get_claim_view(conn, claim_id)
    trace.add(
        "claim_view",
        safe_dump(
            {
                "found": bool(claim_view.get("found")),
                "claim_id": claim_view.get("claim_id"),
                "order_id": claim_view.get("order_id"),
            }
        ),
    )
    if not claim_view.get("found"):
        trace.add("decision", {"status": "failed", "reason": "unknown_claim"})
        return finish(
            conn,
            shape="workflow",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    principal_id = claim_view["principal_id"]
    order_id = claim_view.get("order_id")

    # 2. Missing order_id → needs_info (do not extract an order id from ticket text).
    if not order_id:
        trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
        return finish(
            conn,
            shape="workflow",
            claim_id=claim_id,
            seed=seed,
            status="needs_info",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="missing_order_id",
        )

    # 3. Look up the order (scope-checked against the claim's principal).
    order_view = lookup_order(conn, order_id, principal_id)
    trace.add(
        "lookup_order",
        safe_dump(
            {
                "visible": bool(order_view.get("visible")),
                "reason": order_view.get("reason"),
                "order_id": order_view.get("order_id"),
            }
        ),
    )
    if not order_view.get("visible"):
        trace.add(
            "decision",
            {"status": "escalated", "reason": order_view.get("reason")},
        )
        return finish(
            conn,
            shape="workflow",
            claim_id=claim_id,
            seed=seed,
            status="escalated",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=order_view.get("reason"),
        )

    order = order_view["order"]

    # 4. Compute compensation — code owns the money, model does not.
    quote_payload = compute_compensation(conn, order)
    trace.add("quote", safe_dump(quote_payload))
    proposal = int(quote_payload["amount_vnd"])

    # 5. Quote <= 0 → denied, do not call issue_refund (no policy_denied audit).
    if proposal <= 0:
        trace.add(
            "decision",
            {"status": "denied", "reason": quote_payload.get("reason")},
        )
        return finish(
            conn,
            shape="workflow",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=quote_payload.get("reason"),
        )

    # 6. Quote > 0 → hand the full quote to the host. The host subtracts earlier
    #    refunds on the same order and applies approval/paid caps.
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        trace.add(
            "decision",
            {"status": status, "reason": outcome.get("reason")},
        )
        return finish(
            conn,
            shape="workflow",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome.get("reason"),
        )

    trace.add("decision", {"status": "resolved"})
    return finish(
        conn,
        shape="workflow",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )