"""Local browser app: guided setup, benchmarks, live progress and results.

Standard library only. The server listens on 127.0.0.1 on a random port. Every
request needs the per-launch secret, which the opened URL turns into a
SameSite=Strict cookie, and the expected Host header. Requests that change
anything also need a custom header, which other websites cannot send.
"""
from __future__ import annotations

import contextlib
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import hmac
import html
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
import urllib.request
import webbrowser

from . import __version__
from .analysis import timings
from .imports import REVIEWABLE, review_run
from . import configs
from .planning import PRESETS, make_plan
from .profiles import DEMO_PROFILES, add_profile, catalog
from .report import bundle, generate_report
from .runner import recover, request_cancel, runner_alive
from .storage import LabError, atomic_write, digest, read_json
from .system import detect_conditions, discover_install, doctor, find_replays, process_start_time
from .workspace import ensure_workspace, launch_options, missing_conditions, save_settings

NAME = "Deadlock Performance Lab"
IDLE_EXIT_S = 30 * 60
LAUNCH_OVERHEAD_S = 20  # Typical Steam launch, replay load and shutdown per capture.
DEMO_CASES = [p["id"] for p in DEMO_PROFILES]
PRESET_ROUNDS = {"scout": 1, "screen": 1, "confirm": 5}


def state_file() -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache / "deadlock-perf-lab/gui.json"


def self_command() -> list[str]:
    """How to start this program again, for a desktop launcher."""
    script = Path(sys.argv[0]) if sys.argv and sys.argv[0] else None
    if script and script.suffix == ".pyz":
        return [sys.executable, str(script.resolve())]
    if script and script.name == "dpl" and script.is_file():
        return [str(script.absolute())]  # Desktop sessions often lack ~/.local/bin on PATH.
    found = shutil.which("dpl")
    return [found] if found else [sys.executable, "-m", "deadlock_perf_lab"]


def install_shortcut(workspace: Path) -> Path:
    """Add the app to the desktop's application menu (no Terminal needed)."""
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    icon = data / "icons/hicolor/scalable/apps/deadlock-performance-lab.svg"
    atomic_write(icon, files("deadlock_perf_lab").joinpath("assets/icon.svg").read_bytes())

    def quoted(arg: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_./+:=-]+", arg):
            return arg
        return '"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"'

    command = " ".join(quoted(a) for a in [*self_command(), "--workspace", str(workspace.resolve()), "gui"])
    entry = data / "applications/deadlock-performance-lab.desktop"
    atomic_write(entry, (
        "[Desktop Entry]\nType=Application\n"
        f"Name={NAME}\nComment=Benchmark Deadlock settings on Linux\n"
        f"Exec={command.replace('%', '%%')}\nIcon={icon}\nTerminal=false\nCategories=Game;Utility;\n"
    ).encode())
    return entry


class App:
    """Everything the page can ask for. Methods return JSON-ready values."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.children: list[subprocess.Popen] = []
        self.summaries: dict[str, tuple[float, dict]] = {}
        self.lock = threading.Lock()

    # ---- reading -----------------------------------------------------------------
    def config(self) -> dict:
        return ensure_workspace(self.workspace)

    def install(self, config: dict) -> Path | None:
        return Path(config["install"]) if config.get("install") else discover_install()

    def sessions_dir(self) -> Path:
        return self.workspace / "sessions"

    def session(self, session_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id or ""):
            raise LabError("Unknown session.")
        path = self.sessions_dir() / session_id
        if not (path / "plan.json").is_file():
            raise LabError("Unknown session.")
        return path

    def summary(self, session: Path) -> dict:
        plan_path = session / "plan.json"
        mtime = plan_path.stat().st_mtime
        cached = self.summaries.get(session.name)
        if not cached or cached[0] != mtime:
            plan = read_json(plan_path)
            names = [{"id": k, "name": v.get("name", k)} for k, v in plan["profiles"].items() if k != "baseline"]
            cached = (mtime, {
                "id": plan["id"], "created_at": plan.get("created_at"), "synthetic": plan["synthetic"],
                "manual": bool(plan.get("manual")), "preset": plan.get("preset", "custom"), "rounds": plan["rounds"],
                "cases": names, "mode": plan["context"]["scenario"].get("mode"),
                "research": bool(plan.get("value_sweep") or plan.get("baseline_policy")),
            })
            self.summaries[session.name] = cached
        result = dict(cached[1])
        try:
            result["status"] = read_json(session / "status.json")
        except LabError:
            result["status"] = {"state": "unknown", "completed": 0, "total": 0}
        result["alive"] = bool(runner_alive(session))
        result["starting"] = result["status"].get("state") == "planned" and self.starting(session)
        if result["status"].get("state") == "running" and not result["alive"] and not self.starting(session):
            result["status"]["state"] = "interrupted"
        result["has_results"] = any((session / "runs").glob("*/result.json"))
        return result

    def starting(self, session: Path) -> bool:
        self.children = [c for c in self.children if c.poll() is None]
        return any(getattr(c, "session", None) == session.name for c in self.children)

    def running(self) -> str | None:
        folder = self.sessions_dir()
        self.children = [c for c in self.children if c.poll() is None]
        for child in reversed(self.children):
            # A runner that already finished its captures may still be writing its report.
            try:
                state = read_json(folder / child.session / "status.json").get("state")
            except LabError:
                state = "planned"
            if state in {"planned", "running"}:
                return child.session
        if folder.is_dir():
            for session in folder.iterdir():
                if (session / "runner.json").is_file() and runner_alive(session):
                    return session.name
        return None

    def state(self) -> dict:
        config = self.config()
        install = self.install(config)
        checks = doctor(install, self.workspace)
        try:
            profiles = [self.public_profile(p) for p in catalog(self.workspace).values() if p["id"] != "baseline"]
            profile_error = None
        except LabError as exc:
            profiles, profile_error = [], str(exc)
        sessions = []
        if self.sessions_dir().is_dir():
            for session in sorted(self.sessions_dir().iterdir(), reverse=True):
                if (session / "plan.json").is_file():
                    try:
                        sessions.append(self.summary(session))
                    except (LabError, OSError, KeyError):
                        continue
        scenario = config["scenario"]
        scene_ready = bool(install) and (scenario.get("mode") == "bots" or bool(scenario.get("replay")))
        return {
            "version": __version__, "workspace": str(self.workspace), "config": config,
            "install": str(install) if install else None, "checks": checks,
            "launch_options": launch_options(self.workspace),
            "detected": detect_conditions(install), "missing_conditions": missing_conditions(config),
            "replays": find_replays(install), "profiles": profiles, "profile_error": profile_error,
            "presets": {name: {**PRESETS[name], "rounds": PRESET_ROUNDS[name]} for name in PRESET_ROUNDS},
            "launch_overhead_s": LAUNCH_OVERHEAD_S, "sessions": sessions, "running": self.running(),
            "ready": {"tools": all(c["ok"] for c in checks if c["required"] and c["check"] != "Game closed"),
                      "game_closed": next((c["ok"] for c in checks if c["check"] == "Game closed"), True),
                      "launch": next((c["ok"] for c in checks if c["check"] == "Steam launch options"), False),
                      "scene": scene_ready and not missing_conditions(config)},
            "recovery_needed": any(not c["ok"] for c in checks if c["check"] in {"Recovery", "Install recovery"}),
        }

    @staticmethod
    def public_profile(profile: dict) -> dict:
        result = {k: v for k, v in profile.items() if k not in {"content", "flags", "materialized"}}
        for part in ("gameinfo", "video"):
            if isinstance(result.get(part), dict):
                result[part] = {k: v for k, v in result[part].items() if k != "content"}
        return result

    def detail(self, session_id: str) -> dict:
        session = self.session(session_id)
        result = self.summary(session)
        events = session / "events.log"
        result["events"] = [line.split(" ", 1)[-1] for line in
                            events.read_text(errors="replace").splitlines()[-60:]] if events.is_file() else []
        log = session / "runner.log"
        if result["status"].get("state") in {"failed", "interrupted"} and log.is_file():
            result["log_tail"] = log.read_text(errors="replace").splitlines()[-15:]
        runs = []
        for path in sorted((session / "runs").glob("*/result.json")):
            record = read_json(path)
            review = path.parent / "review.json"
            reviewed = review.is_file() and read_json(review).get("result_sha256") == digest(path)
            blockers = record.get("quality_blockers", [])
            reviewable = [b for b in blockers if b.startswith(REVIEWABLE)]
            metrics = record.get("metrics") or {}
            runs.append({"id": record.get("id", path.parent.name), "case": record.get("case"), "round": record.get("round"),
                         "status": record.get("status"), "error": record.get("error"),
                         "avg_fps": metrics.get("avg_fps"), "low_1_fps": metrics.get("low_1_fps"),
                         "p99_frame_ms": metrics.get("p99_frame_ms"),
                         "reviewable": [] if reviewed else reviewable, "reviewed": reviewed,
                         "blockers": [b for b in blockers if b not in reviewable]})
        result["runs"] = runs
        try:
            estimate = timings(session)
            result["remaining_min"] = estimate["estimated_remaining_minutes"]
        except (LabError, KeyError, ValueError, OSError):
            result["remaining_min"] = None
        return result

    # ---- actions -----------------------------------------------------------------
    def spawn(self, session: Path, live: bool) -> None:
        with self.lock:
            if self.running():
                raise LabError("A benchmark is already running. Wait for it to finish or cancel it first.")
            package_root = str(Path(__file__).resolve().parent.parent)
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH")]))
            env["PYTHONUNBUFFERED"] = "1"
            command = [sys.executable, "-m", "deadlock_perf_lab", "--workspace", str(self.workspace),
                       "run", session.name, *(["--live"] if live else [])]
            with (session / "runner.log").open("ab") as log:
                # A separate session keeps the benchmark (and its file restoration)
                # alive if this window or terminal closes.
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         cwd=self.workspace, env=env, start_new_session=True)
            child.session = session.name
            self.children.append(child)

    def preflight(self, config: dict) -> None:
        install = self.install(config)
        failures = [f"{c['check']}: {c['detail']}" for c in doctor(install, self.workspace)
                    if c["required"] and not c["ok"]]
        if failures:
            raise LabError("Not ready yet — " + "; ".join(failures))

    def demo(self) -> dict:
        self.config()
        session, _ = make_plan(self.workspace, DEMO_CASES, 5, 47, demo=True)
        from .runner import run_session
        with contextlib.redirect_stdout(io.StringIO()):  # Keep progress lines out of the server terminal.
            run_session(self.workspace, session)
        generate_report(session)
        return {"session": session.name}

    def benchmark(self, body: dict) -> dict:
        config = self.config()
        cases = [str(c) for c in body.get("cases") or []]
        if not cases:
            raise LabError("Pick at least one configuration to compare with your current setup.")
        preset = body.get("preset", "screen")
        if preset not in PRESET_ROUNDS:
            raise LabError("Unknown benchmark length.")
        rounds = int(body.get("rounds") or PRESET_ROUNDS[preset])
        fps_max = body.get("fps_max")
        fps_max = None if fps_max in (None, "", "keep") else int(fps_max)
        available = catalog(self.workspace)
        experimental = any(available.get(c, {}).get("kind") == "gameinfo" for c in cases)
        self.preflight(config)
        session, _ = make_plan(self.workspace, cases, rounds, secrets.randbelow(1_000_000),
                               experimental=experimental, preset=preset, fps_max=fps_max,
                               renderer=str(body.get("renderer") or "default"))
        self.spawn(session, live=True)
        return {"session": session.name}

    def start(self, body: dict) -> dict:
        session = self.session(body.get("session"))
        plan = read_json(session / "plan.json")
        if plan.get("manual"):
            raise LabError("Manual sessions take captures through dpl import.")
        if read_json(session / "status.json").get("state") != "planned":
            raise LabError("This session already ran. Start a new benchmark instead.")
        if not plan["synthetic"]:
            self.preflight(self.config())
        self.spawn(session, live=not plan["synthetic"])
        return {"session": session.name}

    def cancel(self, body: dict) -> dict:
        session = self.session(body.get("session"))
        if not request_cancel(session):
            raise LabError("That benchmark is not running.")
        return {"cancelling": session.name}

    def review(self, body: dict) -> dict:
        session = self.session(body.get("session"))
        note = str(body.get("note", ""))
        runs = [str(r) for r in body.get("runs") or []]
        if not runs:
            raise LabError("Select the captures you checked.")
        for run in runs:
            review_run(session, run, note)
        return {"reviewed": len(runs)}

    # ---- configs -------------------------------------------------------------------
    def installed(self) -> Path:
        install = self.install(self.config())
        if not install or not (install / "game/citadel/gameinfo.gi").is_file():
            raise LabError("Set your Deadlock folder in Set up first.")
        return install

    def config_source(self, part: str, source: str, refresh: bool = False) -> dict:
        """Settings in a starting file: your current one, or a preset downloaded from GitHub."""
        if part not in {"gameinfo", "video"}:
            raise LabError("Unknown file.")
        meta = {}
        if source == "current":
            path = configs.install_file(self.installed(), part)
            if not path.is_file():
                raise LabError(f"{path.name} not found. Launch Deadlock once so it creates it.")
            text = path.read_text(encoding="utf-8")
        else:
            text, meta = configs.preset_text(self.workspace, part, source, refresh=refresh)
        return self.parse_source(part, text) | {"meta": meta}

    @staticmethod
    def parse_source(part: str, text: str) -> dict:
        if part == "gameinfo":
            configs.validate_gameinfo(text)
            return {"settings": configs.convars(text)}
        return {"settings": configs.video_settings(text)}

    def config_catalog(self, refresh: bool = False) -> dict:
        result = {"presets": configs.presets(), "video": None, "gameinfo": None, "error": None}
        try:
            text, meta = configs.preset_text(self.workspace, "gameinfo", "sqooky", refresh=refresh)
            result["gameinfo"] = configs.catalog_from(text)
            result["meta"] = meta
        except LabError as exc:
            result["error"] = str(exc)
        try:
            current = self.config_source("video", "current")["settings"]
        except (LabError, OSError):
            current = {}
        result["video"] = configs.video_catalog(list(current))
        return result

    def cvar_search(self, query: str) -> list[dict]:
        query = query.strip().lower()
        if len(query) < 2:
            return []
        if not hasattr(self, "_reference"):
            self._reference = configs.reference(self.workspace)
        hits = [v for k, v in self._reference.items() if query in k]
        hits.sort(key=lambda v: (not v["name"].lower().startswith(query), len(v["name"])))
        return hits[:40]

    def saved_config(self, config_id: str) -> dict:
        profile = catalog(self.workspace).get(config_id)
        if not profile or profile.get("kind") != "config":
            raise LabError("Unknown config.")
        result = self.public_profile(profile)
        for part in ("gameinfo", "video"):
            if (profile.get(part) or {}).get("content"):
                result[part]["base_settings"] = self.parse_source(part, profile[part]["content"])["settings"]
        return result

    def build_config(self, body: dict) -> dict:
        available = catalog(self.workspace)
        for part in ("gameinfo", "video"):
            spec = body.get(part)
            if isinstance(spec, dict) and spec.get("source") == "file" and not spec.get("content"):
                # Imported files stay on the server; editing or copying a config reuses them.
                existing = available.get(body.get("id") or spec.get("copy_of") or "") or {}
                previous = existing.get(part) or {}
                spec.update(content=previous.get("content", ""), filename=previous.get("filename"))
        return configs.build(self.workspace, body)

    def save_config(self, body: dict) -> dict:
        profile = self.build_config(body)
        if not body.get("id"):  # A new config never replaces another with the same name.
            taken, base, n = catalog(self.workspace), profile["id"], 2
            while profile["id"] in taken:
                profile["id"], n = f"{base[:60]}-{n}", n + 1
        configs.materialize(profile, self.installed())  # Refuse configs that can't apply here.
        add_profile(self.workspace, profile, replace=bool(body.get("id")))
        return {"id": profile["id"], "description": profile["description"]}

    def delete_config(self, body: dict) -> dict:
        profile = catalog(self.workspace).get(str(body.get("id")))
        if not profile or profile.get("category") != "custom":
            raise LabError("Only your own configs can be deleted.")
        (self.workspace / "profiles" / f"{profile['id']}.json").unlink()
        return {"deleted": profile["id"]}

    def config_file(self, config_id: str, name: str) -> bytes:
        profile = catalog(self.workspace).get(config_id)
        if not profile or profile.get("kind") != "config":
            raise LabError("Unknown config.")
        files = configs.materialize(profile, self.installed())
        content = files["gameinfo" if name == "gameinfo.gi" else "video"]
        if content is None:
            raise LabError(f"This config doesn't change {name}.")
        return content.encode()

    def open_folder(self, body: dict) -> dict:
        path = self.session(body["session"]) if body.get("session") else self.workspace
        opener = shutil.which("xdg-open")
        if not opener:
            raise LabError(f"Open this folder yourself: {path}")
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return {"path": str(path)}

    def report(self, session_id: str) -> Path:
        session = self.session(session_id)
        if not any((session / "runs").glob("*/result.json")):
            raise LabError("No captures yet, so there is no report.")
        return generate_report(session)

    def export(self, session_id: str) -> bytes:
        session = self.session(session_id)
        with tempfile.TemporaryDirectory() as directory:
            return bundle(session, Path(directory) / "report.zip").read_bytes()


class Handler(BaseHTTPRequestHandler):
    server: "Server"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - quiet access log
        pass

    # ---- plumbing ------------------------------------------------------------------
    def send(self, status: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self' data: 'unsafe-inline'; connect-src 'self'; frame-ancestors 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, value, status: int = 200) -> None:
        self.send(status, json.dumps(value, allow_nan=False, default=str).encode(), "application/json")

    def error(self, message: str, status: int = 400) -> None:
        self.json({"error": message}, status)

    def authorized(self, mutating: bool) -> bool:
        if self.headers.get("Host", "") not in self.server.hosts:
            return False
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        morsel = cookie.get(self.server.cookie_name)
        if not morsel or not hmac.compare_digest(morsel.value, self.server.token):
            return False
        if mutating:
            origin = self.headers.get("Origin")
            if self.headers.get("X-DPL") != "1" or (origin and origin not in self.server.origins):
                return False
        return True

    def handle_one_request(self):
        self.server.last_request = time.monotonic()
        super().handle_one_request()

    # ---- routes --------------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        if path == "/api/ping":
            return self.json({"app": "dpl", "workspace": str(self.server.app.workspace)})
        if path == "/icon.svg":
            return self.send(200, files("deadlock_perf_lab").joinpath("assets/icon.svg").read_bytes(), "image/svg+xml")
        if path == "/" and "token" in parse_qs(url.query):
            token = parse_qs(url.query)["token"][0]
            if self.headers.get("Host", "") in self.server.hosts and hmac.compare_digest(token, self.server.token):
                cookie = f"{self.server.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/"
                return self.send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
        if not self.authorized(False):
            return self.send(403, (
                "<!doctype html><meta charset=utf-8><title>Deadlock Performance Lab</title>"
                "<body style='font:15px system-ui;background:#121612;color:#ecebdf;padding:40px'>"
                "<h1 style='font:26px Georgia,serif'>This link has expired</h1>"
                "<p>Run <code>dpl</code> again (or use the app menu shortcut) to open a fresh window.</p>"
            ).encode(), "text/html; charset=utf-8")
        app = self.server.app
        try:
            if path == "/":
                return self.send(200, files("deadlock_perf_lab").joinpath("assets/app.html").read_bytes(),
                                 "text/html; charset=utf-8")
            if path == "/api/state":
                return self.json(app.state())
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            if path == "/api/configs/catalog":
                return self.json(app.config_catalog(query.get("refresh") == "1"))
            if path == "/api/configs/source":
                return self.json(app.config_source(query.get("part", ""), query.get("source", "current"),
                                                   query.get("refresh") == "1"))
            if path == "/api/configs/search":
                return self.json(app.cvar_search(query.get("q", "")))
            if match := re.fullmatch(r"/api/configs/([a-z0-9_-]+)/(gameinfo\.gi|video\.txt)", path):
                return self.send(200, app.config_file(match[1], match[2]), "application/octet-stream",
                                 {"Content-Disposition": f'attachment; filename="{match[2]}"'})
            if match := re.fullmatch(r"/api/configs/([a-z0-9_-]+)", path):
                return self.json(app.saved_config(match[1]))
            if path.startswith("/api/session/"):
                return self.json(app.detail(unquote(path.rsplit("/", 1)[1])))
            if match := re.fullmatch(r"/report/([A-Za-z0-9_-]+)/?", path):
                return self.send(200, app.report(match[1]).read_bytes(), "text/html; charset=utf-8")
            if match := re.fullmatch(r"/export/([A-Za-z0-9_-]+)\.zip", path):
                return self.send(200, app.export(match[1]), "application/zip",
                                 {"Content-Disposition": f'attachment; filename="dpl-{match[1]}.zip"'})
            return self.error("Not found", 404)
        except (LabError, OSError, ValueError, KeyError) as exc:
            if path.startswith(("/report/", "/export/")):
                page = f"<!doctype html><meta charset=utf-8><p style='font:15px system-ui'>{html.escape(str(exc))}"
                return self.send(400, page.encode(), "text/html; charset=utf-8")
            return self.error(str(exc))

    def do_POST(self):
        if not self.authorized(True):
            return self.error("Forbidden", 403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                return self.error("Request too large", 413)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("expected an object")
        except ValueError:
            return self.error("Invalid request")
        app = self.server.app
        actions = {
            "/api/settings": lambda: {"config": save_settings(app.workspace, body)},
            "/api/demo": app.demo,
            "/api/benchmark": lambda: app.benchmark(body),
            "/api/start": lambda: app.start(body),
            "/api/cancel": lambda: app.cancel(body),
            "/api/review": lambda: app.review(body),
            "/api/configs/save": lambda: app.save_config(body),
            "/api/configs/preview": lambda: configs.preview(app.build_config(body), app.installed()),
            "/api/configs/parse": lambda: app.parse_source(str(body.get("part")), str(body.get("content", ""))),
            "/api/configs/delete": lambda: app.delete_config(body),
            "/api/recover": lambda: {"restored": recover(app.workspace, force=False)},
            "/api/shortcut": lambda: {"path": str(install_shortcut(app.workspace))},
            "/api/open-folder": lambda: app.open_folder(body),
            "/api/quit": self.quit,
        }
        action = actions.get(urlsplit(self.path).path)
        if not action:
            return self.error("Not found", 404)
        try:
            return self.json(action())
        except (LabError, OSError, ValueError, KeyError, TypeError) as exc:
            return self.error(str(exc) or type(exc).__name__)

    def quit(self) -> dict:
        threading.Thread(target=self.server.shutdown, daemon=True).start()
        return {"bye": True}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, app: App, port: int = 0):
        super().__init__(("127.0.0.1", port), Handler)
        self.app = app
        self.token = secrets.token_urlsafe(24)
        self.port = self.server_address[1]
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.origins = {f"http://{host}" for host in self.hosts}
        self.cookie_name = f"dpl_{self.port}"
        self.last_request = time.monotonic()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?token={self.token}"


def existing_instance(workspace: Path) -> str | None:
    """URL of an already-running app window for this workspace, if any."""
    try:
        state = json.loads(state_file().read_text())
        if state.get("workspace") != str(workspace.resolve()) or process_start_time(state["pid"]) != state["start"]:
            return None
        port = urlsplit(state["url"]).port
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as response:
            if json.load(response).get("app") == "dpl":
                return state["url"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return None


def serve(workspace: Path, *, open_browser: bool = True, port: int = 0) -> int:
    workspace = workspace.resolve()
    ensure_workspace(workspace)
    if not port and (url := existing_instance(workspace)):
        print(f"{NAME} is already open: {url}")
        if open_browser:
            webbrowser.open(url)
        return 0
    server = Server(App(workspace), port)
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"pid": os.getpid(), "start": process_start_time(os.getpid()), "url": server.url,
                   "workspace": str(workspace), "started": datetime.now().isoformat()}, f)

    def idle_watch():
        while True:
            time.sleep(30)
            if time.monotonic() - server.last_request > IDLE_EXIT_S:
                print("Closed after 30 idle minutes. Run dpl to open it again.")
                server.shutdown()
                return

    threading.Thread(target=idle_watch, daemon=True).start()
    print(f"{NAME} {__version__}\n\n  Open: {server.url}\n\nWorkspace: {workspace}\n"
          "Keep this running while you use the app. Ctrl+C (or Quit in the app) closes it; "
          "a running benchmark continues and restores your files.")
    if open_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        print("\nClosed.")
    finally:
        server.server_close()
        try:
            if json.loads(path.read_text()).get("pid") == os.getpid():
                path.unlink()
        except (OSError, ValueError):
            pass
    return 0

