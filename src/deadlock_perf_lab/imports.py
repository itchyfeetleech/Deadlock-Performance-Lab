"""Manual experiments use the same plan, parser and round-level analysis."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from .capture import chart_series, frame_distribution, read_mangohud
from .storage import LabError, digest, exclusive_lock, fingerprint, read_json, write_json
from .planning import verify_plan


def import_capture(session: Path, source: Path, case: str, round_index: int, *, interval_ms: float,
                   start_s: float = 0) -> Path:
    plan = read_json(session / "plan.json")
    verify_plan(plan)
    if plan["synthetic"] or not plan.get("manual"):
        raise LabError("Use dpl plan --manual before importing real captures. Demo and automated sessions reject imports.")
    with exclusive_lock(session / ".import.lock"):
        records = [read_json(p) for p in sorted((session / "runs").glob("*/result.json"))]
        if len(records) >= len(plan["schedule"]):
            raise LabError("All planned captures are already imported. Create a new plan.")
        item = plan["schedule"][len(records)]
        if item["case"] != case or item["round"] != round_index:
            raise LabError(f"Next planned capture is {item['case']}, round {item['round']}. Import in the frozen schedule order.")
        source_hash = digest(source)
        if source_hash in {r.get("capture_sha256") for r in records}:
            raise LabError("This raw capture was already imported. Reusing a capture is not an independent repeat.")
        scenario = plan["context"]["scenario"]
        capture = read_mangohud(source, start_s=start_s, duration_s=scenario["sample_s"], interval_ms=interval_ms)
        if records:
            first = records[0]["capture_metadata"]
            if fingerprint(first["system"]) != fingerprint(capture.metadata["system"]):
                raise LabError("Capture system metadata differs from this session. Create a separate experiment.")
            if first["interval_ms"] != interval_ms:
                raise LabError("Capture logging intervals differ. Do not mix measurement resolutions.")
        directory = session / "runs" / f"{item['index']:03d}-{case}"
        directory.mkdir(parents=True, exist_ok=False)
        # Copy an immutable source snapshot; detect concurrent writer activity.
        destination = directory / "capture.csv"
        shutil.copyfile(source, destination)
        if digest(destination) != source_hash or capture.metadata["sha256"] != source_hash:
            destination.unlink()
            directory.rmdir()
            raise LabError("Source capture changed while importing. Stop logging before import.")
        write_json(directory / "result.json", {
            "schema": 1, "id": directory.name, **item, "context_key": plan["context_key"], "synthetic": False,
            "status": "ok", "started_at": datetime.now(timezone.utc).isoformat(),
            "capture_sha256": source_hash, "raw_capture": "capture.csv", "capture_metadata": capture.metadata,
            "profile_sha256": plan["profiles"][case]["sha256"],
            "metrics": capture.metrics(1000 / scenario["budget_fps"]), "warnings": capture.warnings,
            "series": chart_series(capture.times, capture.frames),
            "distribution": frame_distribution(capture.frames),
        })
        write_json(session / "status.json", {"state": "complete" if len(records) + 1 == len(plan["schedule"]) else "importing",
                                            "completed": len(records) + 1, "total": len(plan["schedule"])})
        return directory

