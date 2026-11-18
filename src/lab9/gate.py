"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    def report_rows(report: dict, label: str) -> tuple[list[dict], set[tuple[str, int]]]:
        rows = report.get("rows")
        manifest = report.get("manifest")
        if not isinstance(rows, list):
            problems.append(f"{label} rows are missing or invalid")
            return [], set()
        if not isinstance(manifest, dict):
            problems.append(f"{label} manifest is missing or invalid")
            return rows, set()

        items, seeds = manifest.get("items"), manifest.get("seeds")
        if type(items) is not int or items < 1:
            problems.append(f"{label} manifest item count is invalid")
        if not isinstance(seeds, list) or not seeds or any(type(seed) is not int for seed in seeds):
            problems.append(f"{label} manifest seeds are missing or invalid")
            seeds = []
        elif len(set(seeds)) != len(seeds):
            problems.append(f"{label} manifest contains duplicate seeds")

        if type(items) is int and items >= 0 and isinstance(seeds, list):
            expected = items * len(seeds)
            if len(rows) != expected:
                problems.append(f"{label} row count {len(rows)} does not match manifest {expected}")

        pairs: set[tuple[str, int]] = set()
        for row in rows:
            if not isinstance(row, dict):
                problems.append(f"{label} contains an invalid row")
                continue
            item_id, seed = row.get("item_id"), row.get("seed")
            if not isinstance(item_id, str) or not item_id or type(seed) is not int:
                problems.append(f"{label} contains a row with an invalid item_id/seed")
                continue
            pair = (item_id, seed)
            if pair in pairs:
                problems.append(f"{label} contains duplicate row {item_id}@{seed}")
            pairs.add(pair)
        return rows, pairs

    pr_manifest = pr.get("manifest")
    base_manifest = base.get("manifest")
    if not isinstance(pr_manifest, dict) or not isinstance(base_manifest, dict):
        problems.append("report manifest is missing or invalid")
    else:
        pr_sha, base_sha = pr_manifest.get("eval_set_sha"), base_manifest.get("eval_set_sha")
        if not isinstance(pr_sha, str) or not isinstance(base_sha, str) or not pr_sha or not base_sha:
            problems.append("eval_set_sha is missing or invalid")
        elif pr_sha != base_sha:
            problems.append("eval_set_sha differs from baseline")
        if pr_manifest.get("items") != base_manifest.get("items"):
            problems.append("manifest item count differs from baseline")
        pr_seeds, base_seeds = pr_manifest.get("seeds"), base_manifest.get("seeds")
        if (isinstance(pr_seeds, list) and isinstance(base_seeds, list)
                and all(type(seed) is int for seed in (*pr_seeds, *base_seeds))
                and set(pr_seeds) != set(base_seeds)):
            problems.append("manifest seed set differs from baseline")

    pr_rows, pr_pairs = report_rows(pr, "PR")
    base_rows, base_pairs = report_rows(base, "baseline")
    if pr_pairs != base_pairs:
        problems.append("PR (item_id, seed) rows differ from baseline")

    for label, report in (("PR", pr), ("baseline", base)):
        failures = report.get("evaluator_failures")
        if failures is None or not isinstance(failures, list):
            problems.append(f"{label} evaluator_failures is missing or invalid")
        elif failures:
            problems.append(f"{label} has evaluator failures")

    graded_metrics = [
        metric["id"] for metric in spec.get("metrics", [])
        if metric.get("grader") and metric.get("level") != "system"
    ]
    for row in pr_rows:
        if not isinstance(row, dict):
            continue
        for metric_id in graded_metrics:
            value = row.get(metric_id)
            if value is None:
                problems.append(f"row {row.get('item_id')}@{row.get('seed')} has missing {metric_id}")
                continue
            if isinstance(value, float) and not math.isfinite(value):
                problems.append(f"row {row.get('item_id')}@{row.get('seed')} has non-finite {metric_id}")

    metrics = pr.get("metrics")
    if not isinstance(metrics, dict):
        problems.append("PR metrics are missing or invalid")
    else:
        for metric_id, value in metrics.items():
            if isinstance(value, float) and not math.isfinite(value):
                problems.append(f"metric {metric_id} is non-finite")

    def slice_tags(rows: list[dict], label: str) -> dict[str, tuple[str, ...]]:
        tags_by_item: dict[str, tuple[str, ...]] = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("item_id"), str):
                continue
            raw_tags = row.get("slices") or []
            if not isinstance(raw_tags, list) or any(not isinstance(tag, str) for tag in raw_tags):
                problems.append(f"{label} row {row.get('item_id')} has invalid slice tags")
                continue
            tags = tuple(sorted(set(raw_tags)))
            item_id = row["item_id"]
            if item_id in tags_by_item and tags_by_item[item_id] != tags:
                problems.append(f"{label} slice tags vary across rows for {item_id}")
            tags_by_item[item_id] = tags
        return tags_by_item

    if slice_tags(pr_rows, "PR") != slice_tags(base_rows, "baseline"):
        problems.append("PR item slice tags differ from baseline")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def threshold_violations(new: dict, old: dict, label: str) -> None:
            for bound, is_looser in (
                ("min", lambda new_value, old_value: new_value < old_value),
                ("max", lambda new_value, old_value: new_value > old_value),
            ):
                if bound not in old:
                    continue
                new_value = new.get(bound)
                old_value = old[bound]
                valid = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and math.isfinite(value)
                if not valid(old_value) or not valid(new_value) or is_looser(new_value, old_value):
                    problems.append(f"{label} {bound} threshold was loosened or removed")

        old_metrics = {metric["id"]: metric for metric in base_spec.get("metrics", [])}
        new_metrics = {metric["id"]: metric for metric in spec.get("metrics", [])}
        for metric_id, old_metric in old_metrics.items():
            new_metric = new_metrics.get(metric_id)
            if new_metric is None:
                problems.append(f"metric {metric_id} was removed from spec")
                continue
            threshold_violations(new_metric.get("threshold", {}), old_metric.get("threshold", {}),
                                f"metric {metric_id}")
            if old_metric.get("blocking") and not new_metric.get("blocking"):
                problems.append(f"metric {metric_id} was made non-blocking")
            if old_metric.get("threshold", {}).get("no_significant_drop") \
                    and not new_metric.get("threshold", {}).get("no_significant_drop"):
                problems.append(f"metric {metric_id} dropped no_significant_drop")

        old_slices = {(entry["name"], entry["metric"]): entry for entry in base_spec.get("slices", [])}
        new_slices = {(entry["name"], entry["metric"]): entry for entry in spec.get("slices", [])}
        for slice_id, old_slice in old_slices.items():
            new_slice = new_slices.get(slice_id)
            label = f"slice {slice_id[0]}/{slice_id[1]}"
            if new_slice is None:
                problems.append(f"{label} was removed from spec")
                continue
            threshold_violations(new_slice, old_slice, label)
            if old_slice.get("blocking") and not new_slice.get("blocking"):
                problems.append(f"{label} was made non-blocking")
            if old_slice.get("no_significant_drop") and not new_slice.get("no_significant_drop"):
                problems.append(f"{label} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for slice_spec in spec.get("slices") or []:
        name, metric = slice_spec["name"], slice_spec["metric"]
        pr_items = per_item(pr, metric, slice_name=name)
        base_items = per_item(base, metric, slice_name=name)
        value = sum(pr_items.values()) / len(pr_items) if pr_items else None
        threshold = slice_spec.get("min")
        verdict, note = "ok", ""
        if value is None:
            verdict = "missing"
        elif threshold is not None and value < threshold:
            verdict = "fail"

        if slice_spec.get("no_significant_drop"):
            if not pr_items or set(pr_items) != set(base_items):
                verdict = "unpaired"
                note = "paired slice item sets differ or are empty"
            else:
                keys = sorted(pr_items)
                delta, low, high = stats.paired_bootstrap(
                    [pr_items[key] for key in keys],
                    [base_items[key] for key in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )
                note = f"Δ {delta:+.3f} CI [{low:+.3f}, {high:+.3f}]"
                if high < 0:
                    verdict = "fail"

        if verdict != "ok" and slice_spec.get("blocking"):
            blocked.append(f"slice:{name}/{metric}")
        label = "ok" if verdict == "ok" else ("BLOCK" if slice_spec.get("blocking") else "warn")
        lines.append(
            f"  slice:{name}/{metric:<14} {value!s:<8} "
            f"{json.dumps({'min': threshold, 'no_significant_drop': slice_spec.get('no_significant_drop', False)})!s:<44} "
            f"{note:<36} {label}"
        )
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    pr_manifest = pr.get("manifest")
    base_manifest = base.get("manifest")
    if not isinstance(pr_manifest, dict) or not isinstance(base_manifest, dict):
        return ["integrity"], ["  INTEGRITY report manifest is missing or invalid"]

    pr_sha, base_sha = pr_manifest.get("eval_set_sha"), base_manifest.get("eval_set_sha")
    if isinstance(pr_sha, str) and isinstance(base_sha, str) and pr_sha != base_sha:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    pr_seeds, base_seeds = pr_manifest.get("seeds"), base_manifest.get("seeds")
    if (isinstance(pr_seeds, list) and isinstance(base_seeds, list)
            and all(type(seed) is int for seed in (*pr_seeds, *base_seeds))
            and sorted(pr_seeds) != sorted(base_seeds)):
        return ["paired_samples"], ["  PAIRED SAMPLES differ from the baseline's seed set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            if not a or set(a) != set(b):
                verdict = "unpaired"
                note = "paired item sets differ or are empty"
            else:
                keys = sorted(a)
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys],
                    [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    pr_manifest = pr.get("manifest") or {}
    print(f"gate: PR {pr.get('run_id', 'unknown')} vs main {base.get('run_id', 'unknown')} "
          f"· eval set {pr_manifest.get('eval_set_sha', 'unknown')}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
