"""Workspace configuration, capture setup and session lookup."""
from __future__ import annotations

from pathlib import Path
import math
import os
import shlex

from .storage import LabError, atomic_write, read_json, write_json
from .system import discover_install

CONDITIONS = ("resolution", "graphics_preset", "proton_version", "display_mode")
# Placeholders that workspaces from earlier versions stored for blank game settings.
PLACEHOLDERS = {"record me", "Record upscaling, frame generation, VSync/VRR, driver overrides and background apps."}


def default_workspace() -> Path:
    """One stable per-user workspace, so Steam's launch option always points at it.

    DPL_WORKSPACE overrides it. An existing ./.lab workspace from earlier
    releases is still used when dpl runs from that directory.
    """
    if os.environ.get("DPL_WORKSPACE"):
        return Path(os.environ["DPL_WORKSPACE"]).expanduser()
    if (Path(".lab") / "lab.json").is_file():
        return Path(".lab")
    data = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share"
    return Path(data) / "deadlock-performance-lab"


def load_workspace(workspace: Path) -> dict:
    if not (workspace / "lab.json").is_file():
        raise LabError(f"No workspace at {workspace}. Open the app with dpl, or create one with dpl init.")
    return validate_config(read_json(workspace / "lab.json"))


def validate_config(config: dict) -> dict:
    if config.get("schema") != 1:
        raise LabError("Unsupported workspace schema. This release reads schema 1.")
    scenario = config.get("scenario", {})
    if scenario.get("mode") not in {"replay", "bots"}:
        raise LabError("scenario.mode must be replay or bots")
    for key, minimum, maximum in (("sample_s", 1, 600), ("warmup_s", 0, 600), ("settle_s", 0, 300),
                                   ("cooldown_s", 0, 300), ("budget_fps", 1, 2000)):
        value = scenario.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise LabError(f"scenario.{key} must be between {minimum} and {maximum}.")
    tick = scenario.get("tick")
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise LabError("scenario.tick must be a nonnegative integer.")
    return config


def initialize(workspace: Path, install: str | None = None, replay: str | None = None) -> dict:
    if (workspace / "lab.json").exists():
        raise LabError(f"Workspace already exists: {workspace}. Edit lab.json to change it.")
    found = Path(install).expanduser().resolve() if install else discover_install()
    config = {"schema": 1, "install": str(found) if found else None,
              "scenario": {"mode": "replay", "replay": replay or "", "tick": 70000, "player": "1",
                           "map": "dl_midtown", "sample_s": 30, "warmup_s": 45, "settle_s": 5,
                           "cooldown_s": 5, "budget_fps": 144},
              "conditions": {**{key: "" for key in CONDITIONS}, "notes": ""}}
    write_json(workspace / "lab.json", config)
    for folder in ("profiles", "sessions", "imports"):
        (workspace / folder).mkdir(exist_ok=True)
    # Outside benchmark runs this neutral config leaves logging off.
    atomic_write(workspace / "capture.conf", b"no_display\nautostart_log=0\n")
    return config


def ensure_workspace(workspace: Path) -> dict:
    """Load the workspace, creating it with discovered defaults on first use."""
    if not (workspace / "lab.json").exists():
        initialize(workspace)
    return load_workspace(workspace)


def save_settings(workspace: Path, values: dict) -> dict:
    """Apply a validated subset of settings from the app's forms to lab.json."""
    config = ensure_workspace(workspace)
    if "install" in values:
        install = str(values["install"] or "").strip()
        if install:
            path = Path(install).expanduser()
            if not (path / "game/citadel/gameinfo.gi").is_file():
                raise LabError(f"Not a Deadlock install (no game/citadel/gameinfo.gi): {path}")
            config["install"] = str(path.resolve())
        else:
            config["install"] = None
    scenario = config["scenario"]
    for key, value in (values.get("scenario") or {}).items():
        if key in {"replay", "player", "map"}:
            value = str(value).strip()
            if any(c in value for c in '\n\r\0;"'):
                raise LabError(f"{key} cannot contain quotes, semicolons or line breaks.")
            scenario[key] = value
        elif key == "mode":
            scenario[key] = value
        elif key in {"tick", "sample_s", "warmup_s", "settle_s", "cooldown_s", "budget_fps"}:
            try:
                scenario[key] = int(value) if key == "tick" else float(value)
            except (TypeError, ValueError) as exc:
                raise LabError(f"{key} must be a number.") from exc
            if key != "tick" and scenario[key].is_integer():
                scenario[key] = int(scenario[key])
        else:
            raise LabError(f"Unknown scenario setting: {key}")
    for key, value in (values.get("conditions") or {}).items():
        if key not in (*CONDITIONS, "notes"):
            raise LabError(f"Unknown condition: {key}")
        value = " ".join(str(value).split())[:500]
        config["conditions"][key] = value
    if config["install"] and scenario.get("mode") == "replay" and scenario.get("replay"):
        replay = Path(scenario["replay"]).expanduser()
        if not replay.is_absolute():
            replay = Path(config["install"]) / "game/citadel" / replay
        if not replay.is_file():
            raise LabError(f"Replay not found: {replay}")
    write_json(workspace / "lab.json", validate_config(config))  # Never save an unusable config.
    return config



def launch_options(workspace: Path) -> str:
    return f"env -u MANGOHUD_CONFIG MANGOHUD=1 MANGOHUD_CONFIGFILE={shlex.quote(str(workspace / 'capture.conf'))} %command%"


def session_path(workspace: Path, value: str) -> Path:
    if value == "latest":
        folder = workspace / "sessions"
        paths = sorted(p for p in folder.iterdir() if (p / "plan.json").is_file()) if folder.is_dir() else []
        if not paths:
            raise LabError("No sessions yet. Try the demo first: dpl demo --open")
        return paths[-1]
    path = Path(value).expanduser()
    if path.is_dir() and (path / "plan.json").is_file():
        return path.resolve()
    from .profiles import valid_id
    # Session IDs contain uppercase UTC T/Z; accept the generated pattern too.
    if not __import__("re").fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        valid_id(value)
    path = workspace / "sessions" / value
    if not (path / "plan.json").is_file():
        raise LabError(f"Session not found: {value}")
    return path
