"""Personal test for Shape A — Workflow (thangdktd).

Kiểm tra claim thiếu `order_id` phải trả `needs_info`, không tạo refund effect
và không ghi giao dịch hoàn tiền vào ledger.

Không hardcode claim ID: tìm claim có order_id là None từ dữ liệu mẫu.
"""

from __future__ import annotations

import time

from lab8.db import connect, init_store
from lab8.metrics import trial_pass
from lab8.shapes import SHAPES
from tests.conftest import BY_ID, CLAIMS, WORLD


def _find_claim_without_order_id() -> str:
    """Tìm claim có order_id là None trong dữ liệu mẫu (không hardcode)."""
    for row in CLAIMS:
        if row.get("order_id") is None:
            return row["claim_id"]
    raise AssertionError("Không tìm thấy claim nào thiếu order_id trong dữ liệu mẫu")


def _store(tmp_path, name: str):
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def test_claim_missing_order_id_returns_needs_info_no_refund(tmp_path):
    """Claim thiếu order_id → needs_info, không có refund effect, không ghi ledger."""
    claim_id = _find_claim_without_order_id()
    expected = BY_ID[claim_id]["expected"]

    store = _store(tmp_path, f"workflow-{claim_id}-needs-info.sqlite")
    started_at = time.time()
    result = SHAPES["workflow"](claim_id, seed=11, store_path=str(store))

    conn = connect(store)
    try:
        passed, reason = trial_pass(result.as_dict(), expected, conn, started_at=started_at)

        # RunResult fields
        assert result.status == "needs_info", f"status={result.status}"
        assert result.proposal_amount == 0, f"proposal_amount={result.proposal_amount}"
        assert result.refund_effects == [], f"refund_effects={result.refund_effects}"
        assert result.committed_audit_count == 0, f"audit_count={result.committed_audit_count}"

        # Ledger không được có dòng refund cho claim này
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)
        ).fetchone()["n"]
        assert count == 0, f"ledger has {count} row(s) for {claim_id}"

        assert passed, reason
    finally:
        conn.close()