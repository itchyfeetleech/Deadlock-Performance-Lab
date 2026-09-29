"""Portable, offline reports. Export allowlists exclude logs and backups."""
from __future__ import annotations

import csv
import html
import io
import json
import re
from pathlib import Path
from importlib.resources import files
import zipfile

from .analysis import analyze
from .capture import frame_distribution, read_mangohud
from .profiles import ID_PATTERN
from .storage import LabError, atomic_write, fingerprint, read_json, write_json

CHANGE_LIMIT = 400


def public_payload(analysis: dict) -> dict:
    result = json.loads(json.dumps(analysis))
    scenario = result["context"]["scenario"]
    if scenario.get("replay"):
        # The content hash identifies the replay without exposing a username,
        # filesystem path or match ID. Player selection is anonymized too.
        scenario["replay"] = "local replay (identified by SHA-256)"
    scenario.pop("replay_command", None)
    if scenario.get("player"):
        scenario["player"] = "target-" + fingerprint(str(scenario["player"]))[:10]
    for record in result["runs"]:
        record.pop("capture_metadata", None)
    # This report contains user-authored labels/notes; arbitrary secrets typed
    # into those cannot be inferred or reliably removed. Document that boundary.
    return result


def treatment(profile: dict) -> dict:
    """What a treatment changes, as setting names and values. Never whole file contents."""
    kind = profile.get("kind")
    changes: list[list[str]] = []
    notes: list[str] = []
    text = ""
    if kind == "config":
        from .configs import summary
        done = profile.get("materialized")
        for part, label, key in (("gameinfo", "gameinfo.gi", "cvars"), ("video", "video.txt", "video_changes")):
            values = done.get(key) if done else (profile.get(part) or {}).get("overrides")
            changes += [[label, str(name), str(value)] for name, value in (values or {}).items()]
        notes = list((done or {}).get("notes", []))
        text = summary(profile)
    elif kind == "autoexec":
        for line in profile.get("content", "").splitlines():
            line = line.split("//", 1)[0].strip()
            if line:
                name, _, value = line.partition(" ")
                changes.append(["console", name, value.strip().strip('"')])
        text = "Console settings applied at launch"
    elif kind == "launch":
        text = "Launch options: " + " ".join(profile.get("flags", []))
    elif kind == "gameinfo":
        text = "Replaces the whole gameinfo.gi"
    elif kind == "manual":
        text = "Captured manually"
    return {"summary": text, "description": profile.get("description", ""), "notes": notes,
            "changes": changes[:CHANGE_LIMIT], "more_changes": max(0, len(changes) - CHANGE_LIMIT)}


def add_distributions(session: Path, runs: list[dict]) -> None:
    """Results recorded before percentile curves were stored get one from their verified raw capture."""
    for record in runs:
        meta = record.get("capture_metadata")
        if "distribution" in record or not meta or not ID_PATTERN.fullmatch(str(record.get("id", ""))):
            continue
        try:
            capture = read_mangohud(session / "runs" / record["id"] / record["raw_capture"],
                                    start_s=meta.get("start_s", 0), duration_s=meta.get("requested_duration_s"),
                                    interval_ms=meta.get("interval_ms"))
        except (LabError, OSError, KeyError, TypeError, ValueError):
            continue
        if (capture.metadata["sha256"] == record.get("capture_sha256")
                and len(capture.frames) == record["metrics"].get("samples")):
            record["distribution"] = frame_distribution(capture.frames)


def report_payload(session: Path) -> dict:
    analysis = analyze(session)
    plan = read_json(session / "plan.json")
    add_distributions(session, analysis["runs"])
    for comparison in analysis["comparisons"]:
        comparison["treatment"] = treatment(plan["profiles"].get(comparison["case"], {}))
    analysis["plan"] = {"rounds": plan["rounds"], "preset": plan.get("preset"), "manual": bool(plan.get("manual")),
                        "created_at": plan.get("created_at"), "version": plan.get("version"),
                        "baseline_name": plan["profiles"]["baseline"].get("name", "Your current setup"),
                        "schedule": plan["schedule"]}
    return public_payload(analysis)


def fmt(value: float | None, suffix: str = "", signed: bool = False) -> str:
    if value is None:
        return "—"
    return (f"{value:+.1f}" if signed else f"{value:.1f}") + suffix


def interval(ci: list[float] | None) -> str:
    return " to ".join(fmt(x, "%", True) for x in ci) if ci else "—"


def ranked(result: dict) -> list[dict]:
    return sorted(result["comparisons"], key=lambda c: (c["delta_pct"] is None, -(c["delta_pct"] or 0)))


def markdown_report(result: dict) -> str:
    base = result["baseline"]
    lines = ["# Deadlock Performance Lab", "", f"Session: `{result['session']}`", "",
             "**DEMO DATA — not game measurements.**" if result["synthetic"] else "Measured capture report.", "",
             f"Baseline: {fmt(base['avg_fps'], ' FPS')} · 1% low {fmt(base['metrics'].get('low_1_fps'), ' FPS')} · "
             f"CV {fmt(base['cv_pct'], '%')} · drift {fmt(base['drift_pct'], '%', True)}.", "",
             "| Config | Rounds | Average FPS | Change | 95% interval | 1% low change |",
             "|---|---:|---:|---:|---|---:|"]
    for c in ranked(result):
        label = c["name"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {label} | {len(c['paired_rounds'])} | {fmt(c['avg_fps'])} | {fmt(c['delta_pct'], '%', True)} | "
                     f"{interval(c['ci95_pct'])} | {fmt(c.get('low_1_delta_pct'), '%', True)} |")
    if result["warnings"]:
        lines += ["", "## Notes", ""] + [f"- {w}" for w in result["warnings"]]
    lines += ["", "Change: per round, against that round's two baseline captures. 95% interval: bootstrap over rounds (3 or more).",
              "Average FPS = 1000 / mean frame time. 1% low = 1000 / mean of the slowest 1% of frame times.", ""]
    return "\n".join(lines)


def fallback(result: dict) -> str:
    """The ranking and notes as plain HTML, for viewers with JavaScript turned off."""
    escape = html.escape
    rows = "".join(
        f"<tr><td>{escape(c['name'])}</td><td>{fmt(c['delta_pct'], '%', True)}</td><td>{escape(interval(c['ci95_pct']))}</td>"
        f"<td>{fmt(c['avg_fps'])}</td><td>{fmt(c['metrics']['low_1_fps'])}</td></tr>"
        for c in ranked(result)) or '<tr><td colspan="5">Baseline only: no configs to compare.</td></tr>'
    items = "".join(f"<li>{escape(n)}</li>" for n in result["warnings"]) or "<li>No warnings.</li>"
    base = result["baseline"]
    return (f"<p>Your current setup: {fmt(base['avg_fps'], ' FPS')} average · baseline variation {fmt(base['cv_pct'], '%')} · "
            f"drift {fmt(base['drift_pct'], '%', True)} · {result['valid_runs']} of {result['expected_runs']} captures usable.</p>"
            "<table><thead><tr><th>Config</th><th>FPS change</th><th>95% interval</th><th>Average FPS</th><th>1% low</th>"
            f"</tr></thead><tbody>{rows}</tbody></table><h2>Notes</h2><ul>{items}</ul>")


def generate_report(session: Path) -> Path:
    result = report_payload(session)
    output = session / "report"
    output.mkdir(exist_ok=True)
    write_json(output / "summary.json", result)
    atomic_write(output / "summary.md", markdown_report(result).encode())
    stream = io.StringIO(newline="")
    keys = ["id", "case", "round", "synthetic", "avg_fps", "low_1_fps", "low_01_fps", "p95_frame_ms", "p99_frame_ms",
            "max_frame_ms", "over_budget_pct", "stalls_over_50ms", "samples", "capture_sha256"]
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    for record in result["runs"]:
        values = {key: record.get(key, record["metrics"].get(key, "")) for key in keys}
        # Prevent CSV formula execution in spreadsheet programs.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for k, v in values.items()})
    atomic_write(output / "runs.csv", stream.getvalue().encode())
    page = files("deadlock_perf_lab").joinpath("assets/report.html").read_text()
    substitutions = {
        "__TITLE__": html.escape(result["session"]),
        "__FALLBACK__": fallback(result),
        "__DATA__": json.dumps(result, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026"),
    }
    # One pass over the template, so a label containing a marker is never expanded.
    page = re.sub(r"__(?:TITLE|FALLBACK|DATA)__", lambda match: substitutions[match[0]], page)
    atomic_write(output / "index.html", page.encode())
    return output / "index.html"


def bundle(session: Path, destination: Path) -> Path:
    report = generate_report(session).parent
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("index.html", "summary.json", "summary.md", "runs.csv"):
            archive.write(report / name, name)
    return destination
