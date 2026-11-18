# PR #2 description — proposal only

**Status:** PR #2 is already merged. The GitHub API returned no description body
and no PR comments, so this text has **not** been posted. This is a draft for a
future record, not evidence that the PR description was updated.

PR: [#2 — feat: complete M5 eval set v2 and slice gate](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/pull/2)

## Verification

Commands were run from `src/`:

```powershell
python -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json
python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110
python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
python -m lab9.traps --pr reports/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
python -m pytest -q -m student -o addopts= -k advanced
```

Observed baseline: `E-swarm-20261118-cd0d`, eval-set SHA `cd0de49de85d`,
28 items × 5 seeds; `pass_rate=0.9786`, `pass_hat_5=0.8929`.

The A/A comparison against seeds `66,77,88,99,110` reported Δ=0 for every
metric; `pass_hat_5` was 0.8929 on both sets.

```text
fixed                expect merge got merge
honest_refactor      expect merge got merge
seeded_regression    expect block got block
slice_regression     expect block got block
flaky_regression     expect block got block
mutation score 3/3 · false alarms 0
```

V2 gates: baseline/swarm **exit 0**; `fixed` **exit 0**;
`honest_refactor` **exit 0**; `slice_regression` **exit 1**, blocked by
`slice:money_movement/pass_rate` (slice pass rate 0.85 vs floor 0.90; overall
pass rate 0.9357).

Public integrity traps:

```text
evaluator_errors_as_nan: exit 1 — blocked: integrity
dropped_failing_rows:    exit 1 — blocked: integrity
cherry_picked_seeds:     exit 1 — blocked: paired_samples
loosened_spec:           exit 1 — blocked: integrity
```

These are individual `lab9.gate` runs over the four generated trap reports.
The aggregate `lab9.traps` command also returned exit 0, meaning no public
trap leaked through.

Advanced/Expert student tests: **12 passed**. Both `eval-gate` and
`eval-gate-v2` checks on PR #2 completed successfully:

- [eval-gate](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/actions/runs/44259344564/job/134648698751)
- [eval-gate-v2](https://github.com/thangdktd/K5-L3B-Day9-NguyenHongThang-2A202603829-Evaluation-and-Failure-Analysis/actions/runs/44259344564/job/134648916289)

The `--aa` run is deterministic on MockLLM and does not establish a real-model
noise interval. The trap result covers the four public traps only.
