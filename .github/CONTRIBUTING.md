# Contributing

## Reporting bugs

Use the bug report template. Don't upload a whole workspace: it can contain account identifiers, local paths and your configs.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -v
ruff check src tests
python -m build
dpl --workspace /tmp/dpl-dev          # the app, with a throwaway workspace
```

Tests use temporary workspaces and fake game, Steam and console fixtures. They need neither Steam nor Deadlock, and don't use the network. The app page and the report (`src/deadlock_perf_lab/assets/app.html` and `report.html`) have no build step or external assets. Check changes in a browser at desktop and phone widths, and the report in its light and dark themes too; `dpl demo --open` builds one.

## How it fits together

`dpl` is a Python package with no runtime dependencies. The app is a local web page served by `gui.py`; it calls the same functions as the command line. Live capture uses native Steam, VConsole and MangoHud. Manual imports and the demo feed the same analysis and report pipeline.

| Module | Responsibility |
|---|---|
| `cli.py` | Arguments and command dispatch; `dpl` alone opens the app |
| `gui.py`, `assets/app.html` | App server (127.0.0.1, per-launch secret cookie) and its single-page interface. Benchmarks run as detached `dpl run` processes |
| `workspace.py` | Default workspace location, settings validation, capture setup, session lookup |
| `configs.py` | gameinfo.gi / video.txt configs: presets fetched from OptimizationLock, setting catalogue, editing, batches, the exact files a config writes |
| `profiles.py` | Profile validation (baseline, configs, console cvars, manual) |
| `planning.py` | Lengths, run settings, configs frozen into plans, randomized schedules, plan verification |
| `system.py` | Steam discovery and read-only settings detection, setup checks, fingerprints, process identity |
| `runner.py`, `vconsole.py` | Game lifecycle, replay control, capture orchestration |
| `transaction.py`, `storage.py` | Atomic writes, backups, recovery journals, locks |
| `capture.py`, `metrics.py` | MangoHud parsing, window validation, metrics, binned traces and percentiles |
| `imports.py` | Ordered manual captures and review records |
| `analysis.py` | Evidence checks, round comparisons, timings, rankings |
| `report.py`, `assets/report.html` | Offline HTML report and its Markdown, JSON, CSV and ZIP exports |

Plans own the experiment's conditions and schedule, and analysis checks every result against its plan before comparing. Metric definitions and verdict rules live in the [methodology](../docs/METHODOLOGY.md).

### The report

`report.py` embeds the analysis as JSON in `assets/report.html`, which draws its charts as inline SVG with no dependencies. Labels are inserted as text (`textContent`), never as HTML.

### Saved data (schema 1)

```text
~/.local/share/deadlock-performance-lab/   # or --workspace / DPL_WORKSPACE / legacy ./.lab
  lab.json                          # conditions and scenario (app Set up tab)
  capture.conf / manual.conf        # MangoHud configuration
  profiles/<id>.json                # your configs (starting file frozen in) and other custom profiles
  cache/optimizationlock/           # presets downloaded from GitHub (refreshed hourly)
  imports/                          # manually captured logs
  sessions/<UTC>-<random>/
    plan.json                       # frozen plan with SHA-256, including the exact files each config writes
    status.json / events.log / runner.json / runner.log
    runs/001-baseline/              # result.json, window.json, capture/*.csv, steam.log, vconsole.log,
                                    # transaction.json + backup/, review.json, timings.json
    report/index.html / summary.* / runs.csv
```

Plans can't be edited or resumed after they start; create a new plan when conditions change. Unsupported schemas are rejected. Profiles saved by 0.1-0.2 (`gameinfo`, `launch`) still load and run, but nothing creates them any more.

**Recovery and export boundaries.** A write-ahead journal records backups before any file changes. An install-wide `flock` and a pending-journal pointer in the user's cache protect concurrent workspaces, and PID start times are checked before signalling the game. See [recovery](../docs/TROUBLESHOOTING.md#recover-after-an-interruption). The app accepts requests only from `127.0.0.1` with the expected Host header and a `SameSite=Strict` secret cookie, and changes also need a header other websites can't send. Reports embed their data in one HTML file with all text escaped, and the ZIP exporter includes only four report files. See [SECURITY.md](SECURITY.md).

## Pull requests

Explain the problem, the resulting behavior and what you checked. Changes to capture or analysis must preserve the [measurement rules](../docs/METHODOLOGY.md). Code that changes game files needs failure and restoration tests. Keep runtime dependencies at zero. Don't commit raw experiments, game binaries or replays. Contributions use the project's GPL-3.0-only license.

## Releases

1. Update the version in `pyproject.toml` and `src/deadlock_perf_lab/__init__.py`, and date the changelog entry.
2. Run the tests, lint and build. Install the wheel into a fresh venv outside the checkout and check `dpl --version`, `dpl demo` and the app.
3. Walk through Set up, Configs, Benchmark and Results at desktop and phone widths. Keep synthetic previews labelled, and record any live smoke tests and their limits in the changelog, separately from automated tests.
4. Push and require CI to pass, then push a `vX.Y.Z` tag on that commit. The release workflow checks the tag matches the version, builds the wheel, sdist and `dpl.pyz`, and publishes a preview GitHub release with checksums.
