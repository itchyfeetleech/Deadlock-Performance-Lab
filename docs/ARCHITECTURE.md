# Architecture

`dpl` is a Python package using only the standard library at runtime. The app is a local web page served by `gui.py`; it calls the same functions as the command line. Live capture uses native Steam, VConsole and MangoHud; manual imports and the demo feed the same analysis and report pipeline.

| Module | Responsibility |
|---|---|
| `cli.py` | Arguments and command dispatch; `dpl` alone opens the app |
| `gui.py`, `assets/app.html` | Local app server (127.0.0.1, per-launch secret cookie) and its single-page interface; benchmarks run as detached `dpl run` processes |
| `workspace.py` | Default workspace location, settings validation, capture setup and session lookup |
| `configs.py` | gameinfo.gi / video.txt configs: presets fetched from OptimizationLock, setting catalogue, ConVars and video.txt editing, the exact files a config writes |
| `profiles.py`, `sweep.py` | Profile validation (baseline, configs, console cvars, manual) and one-cvar GameInfo sweeps |
| `planning.py` | Presets, run settings (FPS limit, renderer), configs materialized into frozen plans, randomized schedules and plan verification |
| `system.py` | Steam discovery and read-only settings detection (launch options, resolution, Proton), setup checks, fingerprints, process identity and install lock paths |
| `runner.py`, `vconsole.py` | Game lifecycle, replay control and capture orchestration |
| `transaction.py`, `storage.py` | Atomic writes, backups, recovery journals and locks |
| `capture.py`, `metrics.py` | MangoHud parsing, window validation, metrics and binned frame-time traces |
| `imports.py` | Ordered manual captures and operator review records |
| `analysis.py` | Evidence checks, round comparisons, timing summaries and shortlists |
| `report.py`, `assets/report.html` | Offline HTML, Markdown, JSON, CSV and ZIP exports |

Capture and import code do not depend on report rendering. Plans own the experiment's conditions and schedule; analysis checks results against that plan before comparison. Metric definitions and verdict rules live in the [methodology](METHODOLOGY.md).

## Saved data (schema 1)

```text
~/.local/share/deadlock-performance-lab/   # or --workspace / DPL_WORKSPACE / legacy ./.lab
  lab.json                         # conditions and scenario (app Set up tab)
  capture.conf / manual.conf        # MangoHud configuration
  profiles/<id>.json                # your configs (starting file frozen in) and other custom profiles
  cache/optimizationlock/           # presets downloaded from GitHub (refreshed hourly)
  imports/                         # manually captured logs
  sessions/<UTC>-<random>/
    plan.json                      # frozen plan with SHA-256
    status.json / events.log
    runner.json / runner.log       # live runner PID (removed on exit) and its output
    runs/001-baseline/
      result.json / window.json
      capture/*.csv                # automated capture
      capture.csv                  # imported or demo capture
      steam.log / vconsole.log
      transaction.json / backup/
      review.json                  # operator verification
      timings.json                 # live run phase durations
    report/index.html / summary.* / runs.csv
```

Plans cannot be edited or resumed after starting. Create a new plan when conditions change; historical sessions remain readable. Unsupported schemas are rejected. Old aggregate `results.csv` files lack the capture-window evidence needed for import.

## Recovery and export boundaries

A write-ahead journal records backups before changing files. An install-wide `flock` and pending-journal pointer in the user's cache protect concurrent workspaces. PID start times are checked before signalling the game. See [recovery instructions](TROUBLESHOOTING.md#recover-after-interruption).

The app server accepts requests only from `127.0.0.1` with the expected Host header and a per-launch secret held in a `SameSite=Strict` cookie; changes also need a custom header that other websites cannot send. Reports embed their data and browser assets in one HTML file. Text is escaped, and the ZIP exporter includes only the four report files. Labels and notes remain user-authored content; see [security and data handling](../SECURITY.md).
