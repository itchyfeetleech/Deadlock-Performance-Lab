# Changelog

## 0.3.0 — Unreleased

Running `dpl` opens a local app in your browser. Every command still works.

### New

- **Set up:** checks Steam, MangoHud and the game, shows the Steam launch line with a Copy button, detects whether Steam saved it, lists your replays, and fills in resolution, display mode and Proton version.
- **Configs:** build a `gameinfo.gi` and/or `video.txt` config that starts from your installed file, a [Sqooky/OptimizationLock](https://github.com/Sqooky/OptimizationLock) preset (downloaded from GitHub when you pick it) or an imported file. Tick settings grouped by OptimizationLock's categories, with switches, sliders and search. Every row shows its description and default, and any documented cvar can be added by name. Preview the exact diff, save, edit, duplicate, and download the finished files. `video.txt` presets keep your GPU identifiers and, by default, your resolution and display settings.
- **Test each setting separately:** turns ticked settings, and any list of values for each, into one single-setting config per value, with an optional combined config. `dpl profile sweep tests.csv` does the same from a CSV.
- **Benchmark:** choose Quick look, Shortlist or Confirm and see the launches and time before you start. **FPS limit** (uncapped by default) and **graphics API** are run settings applied to every capture, baseline included (`dpl plan --fps-max N --renderer vulkan|dx11`). Runs continue in the background with live progress and a Cancel button that restores your files.
- **Results:** a ranking by FPS change with baseline noise marked, a **Re-test the top N at Confirm length** button that reuses the run settings, the report and a Share ZIP. A **Restore my files** banner appears after an interrupted run.
- **Add to app menu** (or `dpl shortcut`) installs a desktop launcher. The app closes itself after 30 idle minutes, and running `dpl` again reuses an open window.
- **Report:** each config's change with its 95% interval against the baseline variation (average FPS or 1% lows), per-round results, frame-time percentile curves, the settings each config changes, two-capture frame-time overlays and a run-order chart. Light and dark themes, phone layout and print styles.
- **`dpl.pyz`:** a single file that runs with `python3 dpl.pyz`, attached to releases with the wheel and sdist.

### Changed

- The workspace is now one per-user folder, `~/.local/share/deadlock-performance-lab`, so the Steam launch line stays valid from any directory. An existing `./.lab` is still used from its own directory. `--workspace` and `DPL_WORKSPACE` override it.
- Configs are frozen into each plan as the exact files they write, so later edits never change past results. Hidden `gameinfo.gi` cvars are reported. A `video.txt` the game rewrites is restored, and the report notes what changed.
- `dpl plan` requires `--cases`. `dpl doctor` separates advice (`WARN`) from failures. Settings saved from the app are validated before `lab.json` is written.
- One product name, "Deadlock Performance Lab", everywhere; links point at the renamed repository.
- Captures store frame-time percentiles; older results get them from their verified raw capture when a report is built. Analysis adds a 1% low interval and per-round 1% low changes. `summary.json` also carries each config's changed settings and the run schedule, `summary.md` ranks configs and adds the 1% low change, and `runs.csv` adds P95 frame time.

### Removed

- The bundled treatments: FPS-cap and renderer profiles (now run settings) and four community `gameinfo.gi` snapshots (now presets fetched on request; nothing third-party is redistributed). Profiles saved by 0.1–0.2 still load and run.
- `dpl audit-legacy` and the prototype-era `results.csv` documentation.
- One-off research scripts, the sample `examples/` folder and a machine-specific launch runbook.
- `dpl guide` (the docs cover the same steps).
- Verdicts (*improved*, *regressed*, *inconclusive*), the manual capture review (`dpl review`) and `--threshold`. Results show each change with its 95% interval and the baseline variation; changes within that variation are marked *≈ noise*. Data problems that used to block a verdict, such as a cvar reading back a different value, are notes on the capture. Game settings on the Set up tab are optional.

### Repository

- Documentation is five guides (first benchmark, configs, advanced use, methodology, troubleshooting). Contributing and security notes moved to `.github/`, with a bug report template.
- CI builds and smoke-tests the wheel and `dpl.pyz`, and a tag-triggered workflow publishes releases with checksums.

## 0.2.0 — 2026-09-06

- Searchable, sortable configuration table with average FPS, 1% low, P99 time and paired effects; linked capture overlays, selected-effect intervals, sensor tables and CSV export.
- 5-second scouting preset and per-phase timings; less camera-command overhead in new plans.

## 0.1.0 — 2026-09-05

First packaged Linux preview: installable `dpl` with frozen, randomized, baseline-bracketed plans; replay and bot automation with readback evidence; per-frame MangoHud parsing; crash-safe file restoration; manual-capture experiments; round-level confidence intervals and baseline stability checks; offline reports with private-by-default ZIP exports.
