"""Custom gameinfo.gi / video.txt configs, and presets fetched from Sqooky/OptimizationLock.

A config is what a benchmark compares with your current setup. It has a
gameinfo.gi part and/or a video.txt part. Each part starts from a file (your
current one, a community preset downloaded from GitHub, or a file you import)
and applies setting overrides on top, like OptimizationLock's own updater.
Nothing is bundled: presets are fetched on request and frozen into the config.
"""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote
import urllib.error
import urllib.request

from .profiles import BLOCKED, valid_id, validate_gameinfo
from .storage import LabError, atomic_write, read_json
from .sweep import convar_spans

REPO = "Sqooky/OptimizationLock"
REPO_URL = f"https://github.com/{REPO}"
RAW = "https://raw.githubusercontent.com/{repo}/main/{path}"
CACHE_TTL_S = 60 * 60
MAX_FILE = 2_000_000

# Same names and paths as OptimizationLock's gameinfo_updater.py.
GAMEINFO_PRESETS = {
    "sqooky": ("Sqooky's OptimizationLock", "Sqooky's .gi/gameinfo.gi",
               "The recommended, documented performance config."),
    "boot": ("Boot's maximum FPS", "boot's maxium fps config/gameinfo.gi",
             "Aggressive FPS config with strong visual tradeoffs; described upstream as unmaintained."),
    "kaiz": ("Kaizuchaneru's minimum spec", "kaizuchanerus minimum spec/gameinfo.gi",
             "Aggressive visual reductions for weak hardware."),
    "test": ("Sqooky's test config", "test_cfg/gameinfo.gi", "Experimental development version; may break visuals."),
    "piggy": ("Piggy's config (outdated)", "piggy's config (comparatively outdated)/gameinfo.gi",
              "Older community config, kept for comparison."),
    "clean": ("Clean Valve default", "clean gameinfo.gi/gameinfo.gi",
              "Up-to-date stock file. Use it to compare against stock when your installed file is already modified."),
}
VIDEO_PRESETS = {
    "liah": ("Liah's video.txt (test config)", "test_cfg/video.txt", "Low settings used with Sqooky's test config."),
    "piggy": ("Piggy's video.txt (outdated)", "piggy's config (comparatively outdated)/video.txt",
              "Older low-settings video.txt."),
}
REFERENCE = "cvars_we_can_modify.txt"

# Keys that identify your GPU/format and must always come from your own video.txt.
VIDEO_DEVICE_KEYS = ("Version", "VendorID", "DeviceID", "setting.knowndevice")
VIDEO_DISPLAY_KEYS = ("setting.defaultres", "setting.defaultresheight", "setting.refreshrate_numerator",
                      "setting.refreshrate_denominator", "setting.fullscreen", "setting.coop_fullscreen",
                      "setting.nowindowborder", "setting.mat_vsync", "setting.monitor_index",
                      "setting.aspectratiomode", "setting.high_dpi", "setting.fullscreen_min_on_focus_loss",
                      "setting.recommendedheight", "setting.r_fullscreen_gamma")
VIDEO_GROUPS = {
    "Display": {"setting.defaultres": "Width", "setting.defaultresheight": "Height",
                "setting.refreshrate_numerator": "Refresh rate", "setting.refreshrate_denominator": "Refresh rate divisor",
                "setting.fullscreen": "Fullscreen", "setting.coop_fullscreen": "Borderless fullscreen",
                "setting.nowindowborder": "No window border", "setting.mat_vsync": "VSync",
                "setting.mat_viewportscale": "Render scale", "setting.monitor_index": "Monitor",
                "setting.aspectratiomode": "Aspect ratio mode", "setting.high_dpi": "High DPI",
                "setting.r_fullscreen_gamma": "Brightness (gamma)",
                "setting.fullscreen_min_on_focus_loss": "Minimise on focus loss"},
    "Quality": {"setting.cpu_level": "CPU detail level", "setting.gpu_level": "GPU detail level",
                "setting.mem_level": "Memory level", "setting.gpu_mem_level": "GPU memory level",
                "setting.shaderquality": "Shader quality", "setting.r_texture_stream_mip_bias": "Texture detail (mip bias)",
                "setting.r_citadel_shadow_quality": "Shadow quality", "setting.r_citadel_fog_quality": "Fog quality",
                "setting.r_citadel_ssao_quality": "Ambient occlusion (SSAO)",
                "setting.r_citadel_distancefield_ao_quality": "Distance-field AO",
                "setting.r_displacement_mapping": "Displacement mapping",
                "setting.r_env_map_uses_height_map": "Environment map height",
                "setting.r_particle_max_detail_level": "Particle detail",
                "setting.r_dashboard_render_quality": "Dashboard/UI render quality", "setting.useadvanced": "Advanced settings"},
    "Effects": {"setting.r_effects_bloom": "Bloom (effects)", "setting.r_post_bloom": "Bloom (post-process)",
                "setting.r_depth_of_field": "Depth of field", "setting.r_citadel_motion_blur": "Motion blur",
                "setting.r_screen_space_shadows": "Screen-space shadows", "setting.r_arealights": "Area lights",
                "setting.r_particle_depth_feathering": "Particle depth feathering",
                "setting.r_citadel_half_res_noisy_effects": "Half-resolution noisy effects",
                "setting.r_citadel_distancefield_reflections": "Distance-field reflections",
                "setting.r_citadel_distancefield_shadows": "Distance-field shadows",
                "setting.r_particle_shadows": "Particle shadows", "setting.r_particle_cables_cast_shadows": "Cable shadows",
                "setting.r_light_sensitivity_mode": "Light sensitivity mode", "setting.r_reduce_flash": "Reduce flashes"},
    "Upscaling & latency": {"setting.r_citadel_antialiasing": "Anti-aliasing", "setting.r_citadel_upscaling": "Upscaling",
                            "setting.r_citadel_dlss_settings_mode": "DLSS mode", "setting.r_dlss_preset": "DLSS preset",
                            "setting.r_citadel_fsr_rcas_sharpness": "FSR sharpness",
                            "setting.r_citadel_fsr2_sharpness": "FSR 2 sharpness", "setting.r_low_latency": "Low latency"},
}

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}\Z")
VIDEO_KEY = re.compile(r"(setting\.)?[A-Za-z_][A-Za-z0-9_.]{0,127}\Z")
CONVAR_LINE = re.compile(r'^\s*(?P<off>//\s*)?(?P<name>[A-Za-z_]\w*)\s+(?P<value>"[^"\n]*"|[^\s"/]+)\s*(?://(?P<note>.*))?$')
HEADER = re.compile(r"^\s*//\s*(?:=+|-{2,})\s*(?P<title>[^=\\-][^=\\]*?)\s*(?:=+|-{2,})\s*\\*\s*$")
DEFAULT = re.compile(r'\[def:?\s*"?([^"\]]*)"?\]', re.I)
SKIP_SECTIONS = ("shouldn't", "cannot change", "performance config", "end of config", "if you are modifying")


# ---- fetching -----------------------------------------------------------------------
def cache_dir(workspace: Path) -> Path:
    return workspace / "cache" / "optimizationlock"


def fetch(workspace: Path, path: str, *, refresh: bool = False) -> tuple[str, dict]:
    """Text of a file from Sqooky's repository, cached in the workspace."""
    name = hashlib.sha256(path.encode()).hexdigest()[:16]
    body, meta_path = cache_dir(workspace) / f"{name}.txt", cache_dir(workspace) / f"{name}.json"
    meta = read_json(meta_path) if meta_path.is_file() else None
    fresh = meta and time.time() - meta.get("fetched_epoch", 0) < CACHE_TTL_S
    if body.is_file() and meta and (fresh and not refresh):
        return body.read_text(encoding="utf-8"), meta
    url = RAW.format(repo=REPO, path=quote(path, safe="/"))
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "deadlock-performance-lab"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise LabError(f"{path} is unexpectedly large.")
        text = data.decode("utf-8")
    except (urllib.error.URLError, OSError, UnicodeDecodeError, ValueError) as exc:
        if body.is_file() and meta:
            return body.read_text(encoding="utf-8"), {**meta, "stale": True, "error": str(exc)}
        raise LabError(f"Couldn't download {path} from GitHub ({exc}). Check your internet connection.") from exc
    meta = {"url": url, "source": f"{REPO_URL}/blob/main/{quote(path, safe='/')}", "path": path,
            "sha256": hashlib.sha256(data).hexdigest(), "fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetched_epoch": time.time()}
    atomic_write(body, data)
    atomic_write(meta_path, json.dumps(meta).encode())
    return text, meta


def preset_text(workspace: Path, kind: str, preset: str, *, refresh: bool = False) -> tuple[str, dict]:
    table = GAMEINFO_PRESETS if kind == "gameinfo" else VIDEO_PRESETS
    if preset not in table:
        raise LabError(f"Unknown {kind} preset: {preset}")
    text, meta = fetch(workspace, table[preset][1], refresh=refresh)
    (validate_gameinfo if kind == "gameinfo" else validate_video)(text)
    return text, {**meta, "preset": preset, "name": table[preset][0]}


def presets() -> dict:
    def listing(table):
        return [{"id": k, "name": v[0], "description": v[2], "source": f"{REPO_URL}/blob/main/{quote(v[1], safe='/')}"}
                for k, v in table.items()]
    return {"repository": REPO_URL, "gameinfo": listing(GAMEINFO_PRESETS), "video": listing(VIDEO_PRESETS)}


# ---- gameinfo.gi ConVars ------------------------------------------------------------------
def unquote(value: str) -> str:
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value


def convars(text: str) -> dict[str, str]:
    """Direct ConVars leaf values, keyed by lowercase name (the last definition wins)."""
    spans, _ = convar_spans(text)
    return {name: values[-1][2] for name, values in spans.items()}


def check_override(name: str, value: str, *, video: bool = False) -> None:
    if not (VIDEO_KEY if video else NAME).fullmatch(name or ""):
        raise LabError(f"Invalid setting name: {name!r}")
    if not video and name.lower() in BLOCKED:
        raise LabError(f"{name} can't be set by a config.")
    if not isinstance(value, str) or len(value) > 200 or any(c in value for c in '"\r\n\0{}'):
        raise LabError(f"{name}: values can't contain quotes, braces or line breaks.")


def set_convars(text: str, overrides: dict[str, str]) -> str:
    """Set ConVars values, replacing every definition or adding missing ones."""
    if not overrides:
        return text
    spans, closing = convar_spans(text)
    edits = []
    added = []
    for name, value in overrides.items():
        check_override(name, value)
        matches = spans.get(name.lower())
        if matches:
            edits.extend((start, end, f'"{value}"') for start, end, _ in matches)
        else:
            added.append(f'        {name} "{value}"')
    if added:
        line_start = text.rfind("\n", 0, closing) + 1
        if text[line_start:closing].strip():  # "ConVars { a 1 }" on one line
            edits.append((closing, closing, " ".join(line.strip() for line in added) + " "))
        else:
            block = "        // Added by Deadlock Performance Lab\n" + "\n".join(added) + "\n"
            edits.append((line_start, line_start, block))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    validate_gameinfo(text)
    return text


def catalog_from(text: str) -> list[dict]:
    """Settings grouped by the section headers of a documented gameinfo.gi (Sqooky's layout)."""
    body = text[text.find("ConVars"):] if "ConVars" in text else text
    categories: dict[str, dict] = {}
    current = "General"
    skipping = False
    for line in body.splitlines():
        header = HEADER.match(line)
        if header:
            title = re.sub(r"^\d+(\.\d+)?\.?\s*", "", header["title"]).strip(" .")
            skipping = any(word in title.lower() for word in SKIP_SECTIONS)
            if "end of config" in title.lower():
                break
            if not skipping and title:
                current = title.capitalize() if title.isupper() and len(title) > 3 else title
                if "chat wheel" in current.lower():
                    current = "Chat wheel when pinging"
            continue
        match = CONVAR_LINE.match(line)
        if skipping or not match or "example" in match["name"]:
            continue
        note = match["note"] or ""
        default = DEFAULT.search(note)
        description = DEFAULT.sub("", note).strip(" /\\")
        entry = {"name": match["name"], "value": unquote(match["value"]), "default": default[1] if default else None,
                 "description": re.sub(r"\s{2,}", " ", description)[:400], "optional": bool(match["off"])}
        group = categories.setdefault(current.lower(), {"name": current, "settings": {}})
        group["settings"].setdefault(match["name"].lower(), entry)
    return [{"name": g["name"], "settings": list(g["settings"].values())} for g in categories.values() if g["settings"]]


def reference(workspace: Path) -> dict[str, dict]:
    """Every modifiable cvar with its description, default and flags (OptimizationLock's list)."""
    text, _ = fetch(workspace, REFERENCE)
    result = {}
    for line in text.splitlines():
        if " | " not in line or line.startswith(("Name |", "----")):
            continue
        name, rest = line.split(" | ", 1)
        parts = rest.rsplit(" | ", 2)
        if len(parts) == 3 and NAME.fullmatch(name.strip()):
            result[name.strip().lower()] = {"name": name.strip(), "description": parts[0].strip(),
                                            "default": parts[1].strip(), "flags": parts[2].strip()}
    return result


# ---- video.txt ------------------------------------------------------------------------------
PAIR = re.compile(r'"(?P<key>[^"\n]+)"[ \t]+"(?P<value>[^"\n]*)"')


def validate_video(text: str) -> None:
    if not isinstance(text, str) or not text.strip() or len(text) > 200_000:
        raise LabError("video.txt is empty or too large.")
    stripped = PAIR.sub("", re.sub(r"//[^\n]*", "", text))
    if not re.fullmatch(r'\s*"[^"\n]+"\s*\{\s*\}\s*', stripped):
        raise LabError('Expected a video.txt: one "video.cfg" { "setting" "value" … } block.')


def video_settings(text: str) -> dict[str, str]:
    """video.txt pairs in file order (original key case; the last duplicate wins)."""
    validate_video(text)
    result: dict[str, str] = {}
    lowered: dict[str, str] = {}
    for match in PAIR.finditer(text):
        key = lowered.setdefault(match["key"].lower(), match["key"])
        result[key] = match["value"]
    return result


def set_video(text: str, overrides: dict[str, str]) -> str:
    for key, value in overrides.items():
        check_override(key, value, video=True)
        pattern = re.compile(r'("' + re.escape(key) + r'"[ \t]+)"[^"\n]*"', re.I)
        text, count = pattern.subn(lambda m: m[1] + f'"{value}"', text)
        if not count:
            closing = text.rstrip().rfind("}")
            text = text[:closing].rstrip("\t ") + f'\t"{key}"\t\t"{value}"\n' + text[closing:]
    validate_video(text)
    return text


def video_catalog(keys: list[str]) -> list[dict]:
    groups = [{"name": name, "settings": [{"name": k, "label": label} for k, label in table.items()]}
              for name, table in VIDEO_GROUPS.items()]
    known = {k.lower() for table in VIDEO_GROUPS.values() for k in table}
    other = [{"name": k, "label": k.removeprefix("setting.")} for k in keys
             if k.lower() not in known and k.lower().startswith("setting.")]
    if other:
        groups.append({"name": "Other", "settings": other})
    return groups


# ---- configs --------------------------------------------------------------------------------
def install_file(install: Path, part: str) -> Path:
    return install / ("game/citadel/gameinfo.gi" if part == "gameinfo" else "game/citadel/cfg/video.txt")


def validate_part(part: str, spec) -> None:
    if spec is None:
        return
    if not isinstance(spec, dict) or spec.get("source") not in {"current", "preset", "file"}:
        raise LabError(f"Config {part}: source must be current, preset or file.")
    if spec["source"] != "current":
        (validate_gameinfo if part == "gameinfo" else validate_video)(spec.get("content", ""))
    overrides = spec.get("overrides") or {}
    if not isinstance(overrides, dict) or len(overrides) > 2000:
        raise LabError(f"Config {part}: invalid overrides.")
    for name, value in overrides.items():
        check_override(name, value, video=part == "video")


def validate_config(profile: dict) -> None:
    parts = {part: profile.get(part) for part in ("gameinfo", "video")}
    for part, spec in parts.items():
        validate_part(part, spec)
    if not any(spec and (spec["source"] != "current" or spec.get("overrides")) for spec in parts.values()):
        raise LabError("This config doesn't change anything yet. Pick a starting file or tick some settings.")


def pgi_version(text: str) -> str | None:
    match = re.search(r'PGIVersion\s+"?([0-9A-Fa-f]+)', text)
    return match[1].upper() if match else None


def materialize(profile: dict, install: Path) -> dict:
    """The exact files a config writes into this installation, plus what they change."""
    result = {"gameinfo": None, "video": None, "cvars": {}, "video_changes": {}, "notes": []}
    spec = profile.get("gameinfo")
    if spec and (spec["source"] != "current" or spec.get("overrides")):
        current = install_file(install, "gameinfo").read_text(encoding="utf-8")
        text = set_convars(spec.get("content") or current, spec.get("overrides") or {})
        if text != current:
            result["gameinfo"] = text
            before, after = convars(current), convars(text)
            names = {k.lower(): k for k in (spec.get("overrides") or {})}
            result["cvars"] = {names.get(k, k): v for k, v in after.items() if before.get(k) != v}
            if spec["source"] != "current":
                result["notes"].append("Replaces the whole gameinfo.gi, including engine sections outside ConVars.")
                if pgi_version(text) and pgi_version(current) and pgi_version(text) != pgi_version(current):
                    result["notes"].append("The starting file was made for a different game version (PGIVersion "
                                           "differs). If the game misbehaves, refresh the preset.")
    spec = profile.get("video")
    if spec and (spec["source"] != "current" or spec.get("overrides")):
        path = install_file(install, "video")
        if not path.is_file():
            raise LabError(f"{path} not found. Launch Deadlock once so it creates video.txt.")
        current = path.read_text(encoding="utf-8")
        mine = video_settings(current)
        overrides = dict(spec.get("overrides") or {})
        if spec["source"] != "current":
            keep = VIDEO_DEVICE_KEYS + (VIDEO_DISPLAY_KEYS if spec.get("keep_display", True) else ())
            lower = {k.lower(): (k, v) for k, v in mine.items()}
            for key in keep:
                if key.lower() in lower and key.lower() not in {k.lower() for k in overrides}:
                    overrides[lower[key.lower()][0]] = lower[key.lower()][1]
        text = set_video(spec.get("content") or current, overrides)
        if text != current:
            result["video"] = text
            before = {k.lower(): v for k, v in mine.items()}
            result["video_changes"] = {k: v for k, v in video_settings(text).items() if before.get(k.lower()) != v}
    if not result["gameinfo"] and not result["video"]:
        raise LabError(f"{profile.get('name', profile.get('id'))} is identical to your current files.")
    return result


def summary(profile: dict) -> str:
    parts = []
    for part, label in (("gameinfo", "gameinfo.gi"), ("video", "video.txt")):
        spec = profile.get(part)
        if not spec or (spec["source"] == "current" and not spec.get("overrides")):
            continue
        start = {"current": "your file", "file": f"imported {spec.get('filename') or 'file'}"}.get(
            spec["source"], spec.get("preset_name") or "a preset")
        count = len(spec.get("overrides") or {})
        parts.append(f"{label}: {start}" + (f" + {count} change{'s' * (count != 1)}" if count else ""))
    return " · ".join(parts)


def build(workspace: Path, body: dict) -> dict:
    """A validated config profile from the app's editor."""
    name = " ".join(str(body.get("name", "")).split())[:80]
    if not name:
        raise LabError("Give the config a name.")
    config_id = body.get("id") or "cfg-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "config")
    profile = {"id": valid_id(config_id), "name": name, "kind": "config", "category": "custom", "status": "experimental"}
    for part in ("gameinfo", "video"):
        spec = body.get(part)
        if not isinstance(spec, dict):
            continue
        source = spec.get("source", "current")
        out = {"source": "preset" if source not in {"current", "file"} else source,
               "overrides": {str(k): str(v) for k, v in (spec.get("overrides") or {}).items()}}
        if part == "video":
            out["keep_display"] = bool(spec.get("keep_display", True))
        if source == "file":
            out["content"] = str(spec.get("content", ""))
            out["filename"] = Path(str(spec.get("filename") or "imported")).name[:120]
        elif source not in {"current", "preset"}:
            text, meta = preset_text(workspace, part, source)
            out.update(content=text, preset=source, preset_name=meta["name"], source_url=meta["source"],
                       source_sha256=meta["sha256"], fetched_at=meta["fetched_at"])
        elif source == "preset":
            raise LabError("Choose which preset to start from.")
        if out["source"] != "current" or out["overrides"]:
            profile[part] = out
    profile["description"] = " ".join(str(body.get("description", "")).split())[:300] or summary(profile)
    validate_config(profile)
    return profile


def diff(before: str, after: str | None, name: str) -> str:
    if after is None:
        return ""
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile=f"current/{name}", tofile=f"config/{name}", n=2))


def preview(profile: dict, install: Path) -> dict:
    files = materialize(profile, install)
    result = {"notes": files["notes"], "cvars": files["cvars"], "video_changes": files["video_changes"]}
    for part, name in (("gameinfo", "gameinfo.gi"), ("video", "video.txt")):
        path = install_file(install, part)
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        result[f"{part}_diff"] = diff(current, files[part], name)
    return result
