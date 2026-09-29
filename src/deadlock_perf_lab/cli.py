"""One entry point: the app (dpl), plus commands for scripting and advanced experiments."""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import sys
import webbrowser

from . import __version__
from .analysis import analyze, shortlist, timings
from .capture import read_mangohud
from .imports import import_capture
from .planning import DEFAULT_ROUNDS, make_plan
from .profiles import DEMO_PROFILES, add_profile, catalog
from .report import bundle, generate_report, markdown_report
from .runner import recover, run_session
from .storage import LabError, atomic_write, digest, read_json
from .system import discover_install, doctor, identity
from .workspace import default_workspace, initialize, launch_options, load_workspace, session_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dpl", description="Deadlock Performance Lab — benchmark Deadlock settings on Linux.",
        epilog="Run dpl with no command to open the app.")
    p.add_argument("--version", action="version", version=f"Deadlock Performance Lab {__version__}")
    p.add_argument("--workspace", type=Path, default=None,
                   help="where settings and results are kept (default: ~/.local/share/deadlock-performance-lab, "
                        "or ./.lab if it exists; env DPL_WORKSPACE)")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    def command(name, help_text):
        cmd = sub.add_parser(name, help=help_text, description=help_text)
        cmd.add_argument("--workspace", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        return cmd

    gui = command("gui", "Open the app in your browser (same as running dpl on its own).")
    gui.add_argument("--no-browser", action="store_true", help="print the address instead of opening a browser")
    gui.add_argument("--port", type=int, default=0, help="fixed local port (default: random)")
    demo = command("demo", "Build an example report from made-up data; no game needed.")
    demo.add_argument("--open", action="store_true", help="open the report in your browser")
    demo.add_argument("--rounds", type=int, default=5)
    command("shortcut", "Add Deadlock Performance Lab to your desktop's application menu.")
    init = command("init", "Create a workspace; discover your Steam library.")
    init.add_argument("--install", help="Deadlock installation directory")
    init.add_argument("--replay", help="absolute or citadel-relative .dem path")
    diag = command("doctor", "Check game, tools, running processes and pending recovery.")
    diag.add_argument("--json", action="store_true")
    setup = command("setup", "Show the per-game Steam launch options for capture.")
    setup.add_argument("--manual", action="store_true", help="write a manual per-frame capture config (toggle with Shift+F2)")
    profiles = command("profiles", "List your configs and other profiles.")
    profiles.add_argument("--json", action="store_true")
    profile = command("profile", "Show, add or sweep configs.")
    ps = profile.add_subparsers(dest="action", required=True)
    show = ps.add_parser("show")
    show.add_argument("id")
    show.add_argument("--diff", action="store_true", help="diff a GameInfo snapshot against the current install")
    sweep = ps.add_parser("sweep", help="save one single-setting config per row of an id,cvar,value[,name] CSV")
    sweep.add_argument("matrix", type=Path)
    sweep.add_argument("--base", type=Path, help="start from this gameinfo.gi instead of your installed one")
    add = ps.add_parser("add", help="save a config from your own gameinfo.gi and/or video.txt (or a cvar file)")
    add.add_argument("id")
    add.add_argument("--name")
    add.add_argument("--description", default="")
    add.add_argument("--gameinfo", type=Path, help="a complete gameinfo.gi to test")
    add.add_argument("--video", type=Path, help="a complete video.txt to test (your resolution and device are kept)")
    add.add_argument("--autoexec", type=Path, help="console cvars applied at launch instead")
    add.add_argument("--manual", action="store_true", help="a change you make by hand (see docs/ADVANCED.md)")
    plan = command("plan", "Create a benchmark plan: configs, run settings and shuffled rounds.")
    plan.add_argument("--cases", required=True, help="comma-separated config IDs (see dpl profiles); globs allowed")
    plan.add_argument("--fps-max", type=int, default=None,
                      help="FPS limit for every capture, baseline included (0 = uncapped; default: keep the game's)")
    plan.add_argument("--renderer", choices=["default", "vulkan", "dx11"], default="default",
                      help="graphics API for every capture (default: the game's)")
    plan.add_argument("--rounds", type=int, help=f"rounds of your current setup plus every config (default {DEFAULT_ROUNDS})")
    plan.add_argument("--capture", type=float, dest="sample_s", metavar="SECONDS", help="time recorded per capture (default: lab.json)")
    plan.add_argument("--warmup", type=float, dest="warmup_s", metavar="SECONDS", help="replay time before seeking back to the start tick (default: lab.json)")
    plan.add_argument("--settle", type=float, dest="settle_s", metavar="SECONDS", help="pause on the start tick before recording (default: lab.json)")
    plan.add_argument("--cooldown", type=float, dest="cooldown_s", metavar="SECONDS", help="wait between captures (default: lab.json)")
    plan.add_argument("--seed", type=int, default=47)
    plan.add_argument("--experimental", action="store_true", help="allow legacy whole-file gameinfo profiles saved by older versions")
    plan.add_argument("--manual", action="store_true", help="plan captures made by the operator")
    run = command("run", "Run a plan; --live launches the game.")
    run.add_argument("session", nargs="?", default="latest")
    run.add_argument("--live", action="store_true")
    timing = command("timings", "Show how long captures took and estimate the time left.")
    timing.add_argument("session", nargs="?", default="latest")
    short = command("shortlist", "List a session's configs with the largest FPS gains.")
    short.add_argument("session", nargs="?", default="latest")
    short.add_argument("--top", type=int, default=5)
    command("sessions", "List sessions and their status.")
    status = command("status", "Show a session's current progress.")
    status.add_argument("session", nargs="?", default="latest")
    inspect = command("inspect", "Inspect a MangoHud CSV without adding it to an experiment.")
    inspect.add_argument("csv", type=Path)
    inspect.add_argument("--interval-ms", type=float)
    inspect.add_argument("--start", type=float, default=0)
    inspect.add_argument("--duration", type=float)
    inspect.add_argument("--budget-fps", type=float, default=144)
    imp = command("import", "Import the next capture in a manual plan's frozen schedule.")
    imp.add_argument("csv", type=Path)
    imp.add_argument("--session", default="latest")
    imp.add_argument("--case", required=True)
    imp.add_argument("--round", type=int, required=True)
    imp.add_argument("--interval-ms", type=float, required=True, help="0 for confirmed per-frame logs; 100 for legacy 10Hz logs")
    imp.add_argument("--start", type=float, default=0)
    for name, description in (("compare", "Print the comparison as Markdown."),
                              ("report", "Build the offline HTML report, CSV, JSON and Markdown."),
                              ("export", "Create a shareable report ZIP (no raw captures, logs or backups).")):
        cmd = command(name, description)
        cmd.add_argument("session", nargs="?", default="latest")
        if name == "report":
            cmd.add_argument("--open", action="store_true")
        if name == "export":
            cmd.add_argument("--output", type=Path, required=True)
    rec = command("recover", "Put game files back after an interrupted run.")
    rec.add_argument("--force", action="store_true", help="preserve conflicting edits then restore the verified backup")
    return p


def show_plan(session: Path, plan: dict) -> None:
    print(f"\nExperiment {plan['id']} · {'MANUAL' if plan.get('manual') else 'DEMO' if plan['synthetic'] else 'LIVE PLAN'}")
    s = plan["context"]["scenario"]
    print(f"{plan['rounds']} rounds · {len(plan['schedule'])} runs · {s['sample_s']} s capture, {s['warmup_s']} s warm-up, "
          f"{s['settle_s']} s settle, {s['cooldown_s']} s cooldown · seed {plan['seed']}")
    for round_index in range(1, plan["rounds"] + 1):
        print(f"  Round {round_index}: " + " → ".join(x["case"] for x in plan["schedule"] if x["round"] == round_index))
    minimum = len(plan["schedule"]) * (s["sample_s"] + s["warmup_s"] + s["settle_s"] + s["cooldown_s"]) / 60
    print(f"\nConfigured timing: about {minimum:.1f} minutes plus launch/load/seek overhead.")
    print(f"Frozen plan: {session / 'plan.json'}")
    print("Import captures in this order with dpl import." if plan.get("manual") else f"Execute: dpl --workspace {session.parent.parent} run {plan['id']} --live")


def main(argv: list[str] | None = None) -> int:
    p = parser()
    try:
        args = p.parse_args(argv)
        workspace = (args.workspace or default_workspace()).expanduser().resolve()
        if any(c in str(workspace) for c in "\r\n,="):
            raise LabError("Workspace path cannot contain newlines, commas or '=' (MangoHud config syntax).")
        cmd = args.command or "gui"
        if cmd == "gui":
            from .gui import serve
            return serve(workspace, open_browser=not getattr(args, "no_browser", False), port=getattr(args, "port", 0))
        elif cmd == "shortcut":
            from .gui import install_shortcut
            load_workspace(workspace) if (workspace / "lab.json").exists() else initialize(workspace)
            print(f"Added {install_shortcut(workspace)}\nLook for Deadlock Performance Lab in your application menu.")
        elif cmd == "init":
            initialize(workspace, args.install, args.replay)
            print(f"Workspace created: {workspace}\nRun dpl to use the app, or edit {workspace / 'lab.json'}.")
        elif cmd == "doctor":
            config = read_json(workspace / "lab.json") if (workspace / "lab.json").exists() else {}
            install = Path(config["install"]) if config.get("install") else discover_install()
            checks = doctor(install, workspace)
            if args.json:
                print(json.dumps({"checks": checks, "system": identity()}, indent=2))
            else:
                for check in checks:
                    label = "PASS" if check["ok"] else "FAIL" if check["required"] else "WARN"
                    print(f"{label}  {check['check']}: {check['detail']}")
                print(f"\nWorkspace: {workspace}\nThe first live capture confirms that Steam's launch options work.")
            return 0 if all(c["ok"] for c in checks if c["required"]) else 1
        elif cmd == "setup":
            load_workspace(workspace)
            options = launch_options(workspace)
            if args.manual:
                path = workspace / "manual.conf"
                atomic_write(path, f"log_interval=0\nautostart_log=0\noutput_folder={workspace / 'imports'}\n".encode())
                options = options.replace("capture.conf", "manual.conf")
            print("Deadlock → Steam Properties → General → Launch Options\n\n" + options)
            print("\nPut any options you already use after %command%.")
            if args.manual:
                print("Toggle logging with Shift+F2.")
        elif cmd == "profiles":
            entries = catalog(workspace)
            if args.json:
                print(json.dumps([{k: v for k, v in x.items() if k != "content"} for x in entries.values()], indent=2))
            else:
                for entry in entries.values():
                    print(f"{entry['id']:<23} {entry['kind']:<9} {entry.get('name', entry['id'])}\n  {entry['description']}")
        elif cmd == "profile":
            if args.action == "show":
                entry = catalog(workspace).get(args.id)
                if not entry:
                    raise LabError("Unknown profile. See dpl profiles.")
                shown = {k: v for k, v in entry.items() if k != "content"}
                for part in ("gameinfo", "video"):
                    if isinstance(shown.get(part), dict):
                        shown[part] = {k: v for k, v in shown[part].items() if k != "content"}
                print(json.dumps(shown, indent=2))
                if args.diff and entry["kind"] == "config":
                    from .configs import preview
                    shown = preview(entry, Path(load_workspace(workspace)["install"]))
                    print("\n".join(shown["notes"]) + "\n" + shown["gameinfo_diff"] + shown["video_diff"])
                elif args.diff and entry["kind"] == "gameinfo":
                    config = load_workspace(workspace)
                    original = Path(config["install"]) / "game/citadel/gameinfo.gi"
                    print("".join(difflib.unified_diff(original.read_text().splitlines(True), entry["content"].splitlines(True),
                                                       fromfile="current/gameinfo.gi", tofile=args.id)))
                elif "content" in entry:
                    print(entry["content"])
            elif args.action == "sweep":
                load_workspace(workspace)
                from .configs import sweep_from_csv
                paths = sweep_from_csv(workspace, args.matrix, args.base)
                print(f"Saved {len(paths)} single-setting configs. They appear in the app; benchmark them with dpl plan --cases.")
                print("\n".join(p.stem for p in paths))
            else:
                load_workspace(workspace)
                chosen = [bool(args.gameinfo or args.video), bool(args.autoexec), args.manual]
                if sum(chosen) != 1:
                    raise LabError("Give --gameinfo and/or --video, or --autoexec, or --manual.")
                entry = {"id": args.id, "name": args.name or args.id, "category": "custom", "status": "experimental",
                         "description": args.description}
                if args.autoexec:
                    entry.update(kind="autoexec", content=args.autoexec.read_text(encoding="utf-8"),
                                 source_sha256=digest(args.autoexec))
                elif args.manual:
                    entry.update(kind="manual")
                else:
                    entry["kind"] = "config"
                    for part, source in (("gameinfo", args.gameinfo), ("video", args.video)):
                        if source:
                            entry[part] = {"source": "file", "content": source.read_text(encoding="utf-8"),
                                           "filename": source.name, "overrides": {}, "keep_display": True}
                    if not entry["description"]:
                        from .configs import summary
                        entry["description"] = summary(entry)
                if not entry["description"]:
                    raise LabError("Add --description to say what this change is.")
                print(add_profile(workspace, entry))
        elif cmd == "plan":
            session, plan = make_plan(workspace, args.cases.split(","), args.rounds, args.seed,
                                      experimental=args.experimental, manual=args.manual,
                                      timing={k: v for k in ("sample_s", "warmup_s", "settle_s", "cooldown_s")
                                              if (v := getattr(args, k)) is not None},
                                      fps_max=args.fps_max, renderer=args.renderer)
            show_plan(session, plan)
        elif cmd == "run":
            session = session_path(workspace, args.session)
            plan = read_json(session / "plan.json")
            if not plan["synthetic"] and not args.live:
                show_plan(session, plan)
                print("\nPlan only. Add --live to launch the game and apply temporary treatments.")
                return 0
            try:
                run_session(workspace, session)
            finally:
                if (session / "runs").exists():
                    print(f"Report: {generate_report(session)}")
        elif cmd == "demo":
            if not (workspace / "lab.json").exists():
                initialize(workspace)
            session, plan = make_plan(workspace, [p["id"] for p in DEMO_PROFILES], args.rounds, 47, demo=True)
            run_session(workspace, session)
            output = generate_report(session)
            print(f"\nDEMO DATA ONLY — no game was launched.\nReport: {output}")
            if args.open:
                webbrowser.open(output.as_uri())
        elif cmd == "timings":
            data = timings(session_path(workspace, args.session))
            print(json.dumps(data, indent=2))
        elif cmd == "shortlist":
            if not 1 <= args.top <= 50:
                raise LabError("top must be between 1 and 50")
            session = session_path(workspace, args.session)
            candidates = shortlist(session, args.top)
            for c in candidates:
                ci = f" (95% interval {c['ci95_pct'][0]:+.1f} to {c['ci95_pct'][1]:+.1f}%)" if c["ci95_pct"] else ""
                print(f"  {c['case']:<28} {c['delta_pct']:+.2f}% average FPS{ci} · {len(c['paired_rounds'])} rounds")
            if candidates:
                print("\nRe-test them: dpl plan --cases " + ",".join(c["case"] for c in candidates))
            else:
                print("No complete baseline-bracketed rounds yet.")
        elif cmd == "sessions":
            if not (workspace / "sessions").exists():
                print("No results yet. Try: dpl demo --open")
            else:
                for session in sorted((workspace / "sessions").iterdir()):
                    if (session / "status.json").exists():
                        status = read_json(session / "status.json")
                        print(f"{session.name}  {status['state']:<10} {status['completed']}/{status['total']}")
        elif cmd == "status":
            print(json.dumps(read_json(session_path(workspace, args.session) / "status.json"), indent=2))
        elif cmd == "inspect":
            import math
            if not math.isfinite(args.budget_fps) or args.budget_fps <= 0:
                raise LabError("budget-fps must be finite and positive.")
            capture = read_mangohud(args.csv, start_s=args.start, duration_s=args.duration, interval_ms=args.interval_ms)
            print(json.dumps({"metrics": capture.metrics(1000 / args.budget_fps), "metadata": capture.metadata, "warnings": capture.warnings}, indent=2))
        elif cmd == "import":
            print(import_capture(session_path(workspace, args.session), args.csv, args.case, args.round,
                                 interval_ms=args.interval_ms, start_s=args.start))
        elif cmd in {"compare", "report", "export"}:
            session = session_path(workspace, args.session)
            if cmd == "compare":
                print(markdown_report(analyze(session)))
            elif cmd == "report":
                output = generate_report(session)
                print(output)
                if args.open:
                    webbrowser.open(output.as_uri())
            else:
                print(bundle(session, args.output.resolve()))
        elif cmd == "recover":
            restored = recover(workspace, force=args.force)
            print("\n".join(restored) if restored else "No pending restoration.")
        return 0
    except KeyboardInterrupt:
        print("\nCancelled. Game files were restored unless an error is shown above; run dpl doctor to confirm.", file=sys.stderr)
        return 130
    except (LabError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"dpl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
