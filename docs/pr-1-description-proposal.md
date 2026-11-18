# PR #1 description — proposal only

**Status:** PR #1 is already merged. The GitHub API returned no description body
and no PR comments, so this text has **not** been posted. Copy it into a follow-up
or edit only if desired; do not treat this file as proof that the PR description
was updated.

PR: [#1 — Day09: Complete M1-M4 Core Evaluation](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/pull/1)

## Verification

Commands were run from `src/`:

```powershell
python -m pytest -q -m student -o addopts= -k "lab9 and not advanced"
python -m lab9.evalset --check
python -m lab9.gate --pr reports/eval_fixed.json --baseline reports/baseline_v1.json --spec config/metric_spec.yaml
python -m lab9.gate --pr reports/eval_seeded_regression.json --baseline reports/baseline_v1.json --spec config/metric_spec.yaml
```

Observed results:

- Core student tests: **11 passed**.
- Eval set v1 (`4e0cfd04a0f6`): **0 problems**.
- `fixed`: **exit 0 — merge**.
- `seeded_regression`: **exit 1 — blocked**.

Seeded-regression gate summary (paired baseline `E-swarm-20261118-4e0c`):

```text
pass_rate              0.7143   delta -0.271 CI [-0.500, -0.057] BLOCK
exit 1 — blocked: approval_bypass, refund_amount_correct, reply_amount_matches_ledger, pass_rate
SEEDED_GATE_EXIT=1
```

The generated reports are `reports/baseline_v1.json`, `reports/eval_fixed.json`,
and `reports/eval_seeded_regression.json`. The gate run also reported
`refund_amount_correct` delta −0.200, CI [−0.414, +0.000].

GitHub reports PR #1 as merged. Its `detect`, `eval-gate`, and `eval-gate-v2`
check runs completed successfully:

- [detect](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/actions/runs/44241162618/job/134589151509)
- [eval-gate](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/actions/runs/44241162618/job/134589186555)
- [eval-gate-v2](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/actions/runs/44241162618/job/134589398167)

These checks do not replace the output above in a PR description.
