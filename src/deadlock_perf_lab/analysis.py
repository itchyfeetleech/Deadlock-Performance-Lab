"""Round-level comparisons. Individual frames are not independent trials."""
from __future__ import annotations

from datetime import datetime
import random
import statistics
from pathlib import Path

from .metrics import percentile
from .storage import digest, read_json
from .planning import verify_plan


def bootstrap_ci(values: list[float], *, seed: int = 47, samples: int = 4000) -> list[float] | None:
    if len(values) < 3:
        return None
    rng = random.Random(seed)
    boot = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(samples))
    return [percentile(boot, .025), percentile(boot, .975)]


def aggregate_metrics(records: list[dict]) -> dict:
    # Equal weight per capture; never silently pool frames across rounds.
    keys = ("avg_fps", "low_1_fps", "low_01_fps", "p99_frame_ms", "over_budget_pct")
    result = {}
    for key in keys:
        values = [r["metrics"].get(key) for r in records]
        result[key] = statistics.fmean(values) if values and all(v is not None for v in values) else None
    return result


# Results from earlier versions list checks to confirm by hand under "quality_blockers".
# Those checks are gone; the data problems among them are kept as warnings.
REVIEW_PROMPTS = ("Replay POV is not explicitly selected.", "Review demo_info", "Replay progression and camera require",
                  "Whole GameInfo swap:", "Renderer flag requested;", "Manual capture: confirm", "Config applied: confirm",
                  "Record resolution, graphics preset", "Benchmark conditions were not recorded",
                  "Interval-sampled evidence cannot", "The raw capture contained malformed rows")


def capture_notes(record: dict) -> list[str]:
    """A capture's warnings, including data problems older versions stored as blockers."""
    notes = list(record.get("warnings", []))
    notes += [b for b in record.get("quality_blockers", []) if not b.startswith(REVIEW_PROMPTS) and b not in notes]
    return notes


def analyze(session: Path) -> dict:
    plan = read_json(session / "plan.json")
    verify_plan(plan)
    records = []
    for path in sorted((session / "runs").glob("*/result.json")):
        record = read_json(path)
        record["warnings"] = capture_notes(record)
        record.pop("quality_blockers", None)
        record["_directory"] = str(path.parent)
        records.append(record)
    warnings = []
    valid = []
    excluded = []
    seen = set()
    for record in records:
        why = []
        raw_name = record.get("raw_capture", "")
        raw = Path(record.pop("_directory")) / raw_name
        if record.get("status") == "ok":
            if not raw_name or Path(raw_name).is_absolute() or ".." in Path(raw_name).parts or not raw.is_file():
                why.append("raw capture missing or invalid")
            elif digest(raw) != record.get("capture_sha256"):
                why.append("raw capture changed after measurement")
            index = record.get("index", 0)
            planned = plan["schedule"][index - 1] if isinstance(index, int) and 0 < index <= len(plan["schedule"]) else {}
            if any(record.get(k) != planned.get(k) for k in ("index", "case", "round")):
                why.append("run does not match the planned schedule")
            profile = plan["profiles"].get(record.get("case"), {})
            if record.get("profile_sha256") != profile.get("sha256"):
                why.append("treatment fingerprint differs from the plan")
        if record.get("status") != "ok":
            why.append(record.get("error", "failed capture"))
        if record.get("context_key") != plan["context_key"]:
            why.append("incompatible benchmark conditions")
        if record.get("synthetic") != plan["synthetic"]:
            why.append("mixed synthetic and measured evidence")
        if record.get("capture_sha256") in seen:
            why.append("duplicate raw capture")
        if record.get("capture_sha256"):
            seen.add(record["capture_sha256"])
        if not why:
            valid.append(record)
        else:
            excluded.append({"id": record.get("id"), "reasons": why})
    if plan["synthetic"]:
        warnings.append("DEMO DATA — made-up numbers, not Deadlock measurements.")
    if len(valid) < len(plan["schedule"]):
        warnings.append(f"Incomplete session: {len(valid)}/{len(plan['schedule'])} usable runs.")
    base = [r for r in valid if r["case"] == "baseline"]
    base_fps = [r["metrics"]["avg_fps"] for r in base]
    base_cv = statistics.pstdev(base_fps) / statistics.fmean(base_fps) * 100 if base_fps else None
    drift = (base_fps[-1] / base_fps[0] - 1) * 100 if len(base_fps) >= 2 else None
    for record in valid:
        for warning in record.get("warnings", []):
            if warning not in warnings:
                warnings.append(warning)
    comparisons = []
    for case, profile in plan["profiles"].items():
        if case == "baseline":
            continue
        own = [r for r in valid if r["case"] == case]
        deltas = []
        low_deltas = []
        paired_rounds = []
        for round_index in range(1, plan["rounds"] + 1):
            controls = [r for r in base if r["round"] == round_index]
            treatments = [r for r in own if r["round"] == round_index]
            if len(controls) != 2 or len(treatments) != 1:
                continue
            control = statistics.fmean(r["metrics"]["avg_fps"] for r in controls)
            deltas.append((treatments[0]["metrics"]["avg_fps"] / control - 1) * 100)
            paired_rounds.append(round_index)
            lows = [r["metrics"].get("low_1_fps") for r in controls]
            low = treatments[0]["metrics"].get("low_1_fps")
            # Kept aligned with paired_rounds; None where a true 1% low is unavailable.
            low_deltas.append((low / statistics.fmean(lows) - 1) * 100
                              if all(x is not None for x in lows) and low is not None else None)
        known_lows = [x for x in low_deltas if x is not None]
        comparisons.append({"case": case, "name": profile.get("name", case), "kind": profile["kind"],
                            "metrics": aggregate_metrics(own),
                            "runs": len(own), "paired_rounds": paired_rounds,
                            "delta_pct": statistics.fmean(deltas) if deltas else None,
                            "ci95_pct": bootstrap_ci(deltas), "round_deltas_pct": deltas,
                            "low_1_delta_pct": statistics.fmean(known_lows) if known_lows else None,
                            "low_1_ci95_pct": bootstrap_ci(known_lows) if len(known_lows) == len(deltas) else None,
                            "round_low_1_deltas_pct": low_deltas,
                            "avg_fps": statistics.fmean(r["metrics"]["avg_fps"] for r in own) if own else None})
    return {"schema": 1, "session": plan["id"], "synthetic": plan["synthetic"],
            "baseline": {"metrics": aggregate_metrics(base), "runs": len(base), "avg_fps": statistics.fmean(base_fps) if base_fps else None,
                         "cv_pct": base_cv, "drift_pct": drift},
            "comparisons": comparisons, "warnings": warnings, "excluded": excluded,
            "valid_runs": len(valid), "expected_runs": len(plan["schedule"]),
            "context": plan["context"], "runs": valid}


def timings(session: Path) -> dict:
    plan = read_json(session / "plan.json")
    durations = []
    phases = {}
    for path in sorted((session / "runs").glob("*/result.json")):
        result = read_json(path)
        if result.get("status") != "ok" or not result.get("finished_at"):
            continue
        for name, value in result.get("phase_timings_s", {}).items():
            phases.setdefault(name, []).append(value)
        durations.append((datetime.fromisoformat(result["finished_at"]) -
                          datetime.fromisoformat(result["started_at"])).total_seconds())
    median = statistics.median(durations) if durations else None
    remaining = len(plan["schedule"]) - len(durations)
    return {"session": plan["id"], "completed": len(durations), "planned": len(plan["schedule"]),
            "rounds": plan["rounds"], "treatments": len(plan["profiles"]) - 1,
            "sample_s": plan["context"]["scenario"]["sample_s"],
            "median_phases_s": {k: statistics.median(v) for k, v in phases.items()}, "median_run_s": median,
            "mean_run_s": statistics.fmean(durations) if durations else None,
            "estimated_remaining_minutes": median * remaining / 60 if median is not None else None}


def shortlist(session: Path, top: int = 5) -> list[dict]:
    report = analyze(session)
    candidates = [c for c in report["comparisons"] if c["delta_pct"] is not None]
    return sorted(candidates, key=lambda c: c["delta_pct"], reverse=True)[:top]
