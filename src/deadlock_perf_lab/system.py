"""Read-only Linux discovery. Never changes governors, drivers or Steam."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import re
import shlex
import shutil

from .storage import digest, read_json

APP_ID = "1422450"


def install_lock(install: Path) -> Path:
    key = hashlib.sha256(str(install.resolve()).encode()).hexdigest()[:24]
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "deadlock-perf-lab/locks" / f"{key}.lock"


VDF_TOKEN = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])|//[^\n]*|\[[^\]\n]*\]|([^\s{}"]+)')


def parse_vdf(text: str) -> dict:
    """Parse Valve's text KeyValues format (read-only; keys are lowercased).

    Later duplicate keys win. Conditional suffixes such as [$WIN32] are ignored.
    """
    root: dict = {}
    stack = [root]
    key = None
    for match in VDF_TOKEN.finditer(text):
        quoted, brace, bare = match.groups()
        if brace == "{":
            child: dict = {}
            if key is not None:
                stack[-1][key] = child
            stack.append(child)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif quoted is not None or bare is not None:
            value = bare if quoted is None else re.sub(r"\\(.)", r"\1", quoted)
            if key is None:
                key = value.lower()
            else:
                stack[-1][key] = value
                key = None
    return root


def vdf_get(data: dict, *path: str):
    for part in path:
        if not isinstance(data, dict):
            return None
        data = data.get(part.lower())
    return data


def steam_roots() -> list[Path]:
    return [Path.home() / p for p in (
        ".local/share/Steam", ".steam/steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam")]


def read_vdf(path: Path) -> dict:
    try:
        return parse_vdf(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def discover_install() -> Path | None:
    override = os.environ.get("DEADLOCK_INSTALL_DIR")
    if override:
        return Path(override).expanduser().resolve()
    roots = steam_roots()
    libraries = list(roots)
    for root in roots:
        config = root / "steamapps/libraryfolders.vdf"
        if config.is_file():
            libraries.extend(Path(p.replace("\\\\", "\\")) for p in
                             re.findall(r'"path"\s+"([^"]+)"', config.read_text(errors="replace")))
    for library in libraries:
        for name in ("Deadlock", "deadlock"):
            candidate = library / "steamapps/common" / name
            if (candidate / "game/citadel/gameinfo.gi").is_file():
                return candidate.resolve()
    return None


def steam_launch_options() -> list[str] | None:
    """Deadlock launch options saved by each local Steam account, or None if unreadable.

    Steam can keep a just-edited value in memory until it next saves its config,
    so a missing value is advisory; the first live capture is the real check.
    """
    found = None
    seen = set()
    for root in steam_roots():
        for config in sorted(root.glob("userdata/*/config/localconfig.vdf")):
            if config.resolve() in seen:
                continue
            seen.add(config.resolve())
            data = read_vdf(config)
            apps = (vdf_get(data, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps")
                    or vdf_get(data, "UserLocalConfigStore", "apps") or {})
            found = found if found is not None else []
            options = vdf_get(apps, APP_ID, "LaunchOptions")
            if isinstance(options, str) and options.strip():
                found.append(options)
    return found


def detect_conditions(install: Path | None) -> dict[str, str]:
    """Best-effort, read-only suggestions for the benchmark conditions form."""
    detected = {}
    if install:
        video = read_vdf(install / "game/citadel/cfg/video.txt")
        settings = next((v for v in video.values() if isinstance(v, dict)), {})
        width, height = settings.get("setting.defaultres"), settings.get("setting.defaultresheight")
        if width and height:
            detected["resolution"] = f"{width}x{height}"
        if "setting.fullscreen" in settings:
            if settings.get("setting.fullscreen") == "1":
                mode = "Fullscreen"
            elif settings.get("setting.nowindowborder") == "1":
                mode = "Borderless window"
            else:
                mode = "Windowed"
            numerator = settings.get("setting.refreshrate_numerator")
            denominator = settings.get("setting.refreshrate_denominator") or "1"
            try:
                rate = float(numerator) / float(denominator)
                if rate > 0:
                    mode += f", {rate:g} Hz"
            except (TypeError, ValueError, ZeroDivisionError):
                pass
            detected["display_mode"] = mode
    for root in steam_roots():
        mapping = vdf_get(read_vdf(root / "config/config.vdf"), "InstallConfigStore", "Software", "Valve", "Steam",
                          "CompatToolMapping")
        if isinstance(mapping, dict):
            tool = vdf_get(mapping, APP_ID, "name") or vdf_get(mapping, "0", "name")
            if isinstance(tool, str) and tool:
                detected["proton_version"] = tool
                break
    return detected


def find_replays(install: Path | None, limit: int = 200) -> list[str]:
    """Replay files under game/citadel, relative to it, newest first."""
    if not install:
        return []
    citadel = install / "game/citadel"
    found = []
    for folder, pattern in ((citadel, "*.dem"), (citadel / "replays", "**/*.dem")):
        try:
            found.extend(p for p in folder.glob(pattern) if p.is_file())
        except OSError:
            continue
    found = sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [p.relative_to(citadel).as_posix() for p in found]


def identity() -> dict:
    cpu = "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        match = re.search(r"model name\s*:\s*(.+)", cpuinfo.read_text(errors="replace"))
        if match:
            cpu = match[1].strip()
    gpu = []
    for device in sorted(Path("/sys/class/drm").glob("card[0-9]*/device")):
        try:
            gpu.append({"vendor": (device / "vendor").read_text().strip(),
                        "device": (device / "device").read_text().strip(),
                        "driver": (device / "driver").resolve().name})
        except OSError:
            pass
    memory = "unknown"
    if Path("/proc/meminfo").is_file():
        memory = Path("/proc/meminfo").read_text().splitlines()[0].split(":", 1)[1].strip()
    governors = sorted({p.read_text().strip() for p in
                        Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor")})
    return {"os": platform.system(), "kernel": platform.release(), "architecture": platform.machine(),
            "cpu": cpu, "logical_cpus": os.cpu_count(), "gpu": gpu, "memory": memory,
            "governors": governors}


def game_identity(install: Path) -> dict:
    manifest = install.parent.parent / f"appmanifest_{APP_ID}.acf"
    build = "unknown"
    if manifest.is_file():
        match = re.search(r'"buildid"\s+"([^"]+)"', manifest.read_text(errors="replace"))
        if match:
            build = match[1]
    files = {}
    for relative in ("game/citadel/gameinfo.gi", "game/citadel/cfg/autoexec.cfg", "game/citadel/cfg/video.txt"):
        path = install / relative
        files[relative] = digest(path) if path.is_file() else None
    return {"build_id": build, "baseline_files": files}


def game_processes() -> dict[int, str]:
    """Only actual Deadlock executables, never Python/shell command strings.

    /proc starttime is recorded with each PID to prevent signaling PID reuse.
    """
    found = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / "cmdline").read_bytes().split(b"\0")
            executable = args[0].decode(errors="replace").replace("\\", "/").rsplit("/", 1)[-1].lower()
            if executable not in {"deadlock.exe", "deadlock", "citadel", "project8.exe"}:
                continue
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if stat[0] == "Z":
                continue
            found[int(proc.name)] = stat[19]
        except (OSError, IndexError):
            continue
    return found


def doctor(install: Path | None, workspace: Path) -> list[dict]:
    """Setup checks. Checks with required=False are advice and never block a run."""
    checks = []

    def add(name, passed, detail, required=True):
        checks.append({"check": name, "ok": bool(passed), "detail": str(detail), "required": required})

    add("Linux", platform.system() == "Linux", platform.system())
    add("Steam", shutil.which("steam"), shutil.which("steam") or "Not found. Install native (non-Flatpak) Steam and sign in.")
    add("MangoHud", shutil.which("mangohud"),
        shutil.which("mangohud") or "Not found. Install MangoHud from your distribution (plus its 32-bit package if needed).")
    add("Game install", install and (install / "game/citadel/gameinfo.gi").is_file(),
        install or "Not found. Choose the Deadlock folder in the app, or run dpl init --install PATH.")
    running = game_processes()
    add("Game closed", not running, "Deadlock is not running." if not running else
        "Close Deadlock first. The lab never stops a game it didn't start.")
    if install:
        add("Native Steam library", ".var/app/com.valvesoftware.Steam" not in str(install),
            "Flatpak Steam automation is not supported." if ".var/app/com.valvesoftware.Steam" in str(install) else "Native installation")
        guard = install_lock(install).with_suffix(".json")
        if guard.exists():
            pending = read_json(guard)
            state = read_json(Path(pending["journal"]))
            add("Install recovery", state.get("state") == "restored", f"Recovery workspace: {pending['workspace']}")
        add("Writable game config", os.access(install / "game/citadel/cfg", os.W_OK), install / "game/citadel/cfg")
    journals = [p for p in (workspace / "sessions").glob("*/runs/*/transaction.json")
                if '"state": "restored"' not in p.read_text()]
    add("Recovery", not journals, "No pending restores." if not journals else f"Run dpl recover; {len(journals)} journal(s).")
    options = steam_launch_options()
    capture = str(workspace / "capture.conf")
    if options is None:
        add("Steam launch options", False, "Steam settings not found; the first live capture verifies them.", False)
    elif any(capture in o or shlex.quote(capture) in o for o in options):
        add("Steam launch options", True, "Found in Steam settings.", False)
    elif any("MANGOHUD_CONFIGFILE" in o for o in options):
        add("Steam launch options", False, "Steam points MangoHud at a different workspace. Paste the options again.", False)
    else:
        add("Steam launch options", False, "Not found yet. Paste them into Deadlock's Steam properties "
            "(Steam may only save them when it closes).", False)
    return checks


def process_start_time(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (OSError, IndexError):
        return None


def process_matches(pid: int, start_time: str) -> bool:
    """Check a known process without scanning every process during capture."""
    return process_start_time(pid) == start_time
