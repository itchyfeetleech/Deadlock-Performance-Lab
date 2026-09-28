# Changelog

## 0.3.0 — Unreleased

**A graphical app.** Running `dpl` now opens a local app in your browser. It guides you through setup, benchmarking and results, so you no longer have to edit `lab.json` by hand or learn the commands. Every command still works.

- **Set up** checks Steam, MangoHud and the game, and shows the Steam launch options line with a Copy button. It detects whether the line is saved in Steam and lists your downloaded replays. Resolution, display mode and Proton version are filled in from the game's `video.txt` and Steam's settings.
- **Benchmark** lets you tick configs (including your own console settings), choose Quick look, Shortlist or Confirm, and see the number of launches and estimated time before you start. Runs continue in the background with live progress and a Cancel button that restores your files.
- **Results** lists every session with Open report, Share ZIP and a review panel, so you can confirm the captures you watched. It also shows a **Restore my files** banner after an interrupted run.
- **Add to app menu** (or `dpl shortcut`) installs a desktop launcher. Opening the app again reuses a running window, and the app closes itself after 30 idle minutes.
- The app listens only on `127.0.0.1` and needs a per-launch secret cookie, the expected Host header and, for changes, a custom request header.

**Fewer hurdles**

- The workspace now defaults to one per-user folder, `~/.local/share/deadlock-performance-lab`, instead of `./.lab` in whatever directory you ran from. The Steam launch options line therefore stays valid wherever you run `dpl`. An existing `./.lab` is still used from its own directory. `--workspace` and `DPL_WORKSPACE` override the default.
- Every command creates the workspace on first use when needed. Missing-workspace errors say what to do.
- New workspaces follow player `1` by default instead of leaving the camera target unset.
- `dpl doctor` distinguishes advice (`WARN`) from blocking failures.
- Settings saved from the app are validated before `lab.json` is written.
- Single-file `dpl.pyz` builds (run with `python3 dpl.pyz`, no install needed), plus a release workflow that attaches them with the wheel and sdist when a version tag is pushed.

**Tidy-up**

- The project is called Deadlock Performance Lab everywhere. Links point to the renamed repository; the old GitHub Pages address returned 404.
- The published results website moved to `site/`, and the value-sweep scripts and matrix moved to `research/`. Removed the machine-specific `BENCHMARK-LAUNCH.md` runbook.
- The README and first-benchmark guide are rewritten around the app. The other guides point to the new workspace location.
- `THIRD_PARTY_NOTICES.md` and the GameInfo source manifest now record the 2026-09-06 comment-line edits to three bundled files, with current hashes. They previously described the files as unchanged.
- Earlier unreleased changes: removed the report header badge, baseline-history panel, iteration-time panel and Print/PDF button; replaced the sort dropdown with sortable columns; separated workspace setup, planning, capture processing and report rendering.

## 0.2.0 — 2026-09-06

- Rebuilt results around a searchable, sortable configuration table with average FPS, 1% low, P99 time and paired effects.
- Added linked capture overlays, selected-effect intervals, sensor tables, baseline history and comparison CSV export.
- Added the 5-second scouting preset and per-phase iteration timings. Reduced camera-command guard overhead in new plans.
- Preserved old plan behavior, evidence checks, recovery and offline report compatibility.

Validation recorded for this release: 51 automated tests; a live baseline → GameInfo → baseline scout completed with restoration verified. Iterations took 27.7, 69.5 and 24.3 seconds; Steam shader processing accounted for 50.5 seconds of the middle launch. The report was inspected with synthetic data and an existing partial sweep, including sorting, capture selection and a 390-pixel layout. Shorter scout captures are not evidence of an equivalent-duration speedup.

## 0.1.0 — 2026-09-05

First packaged Linux community preview.

- Replaced the script collection with an installable `dpl` application and guided terminal menu.
- Added frozen, randomized experiment plans with baseline-bracketed repeat rounds.
- Added event-driven replay readiness, screen/confirm presets, profile selectors, one-cvar matrix generation, timing summaries and provisional shortlists.
- Added per-frame MangoHud parsing with explicit capture windows, long-stall retention and capture-integrity checks.
- Added replay/bot automation, readback evidence, install-wide serialization and crash recovery journals.
- Added custom profiles, attributed community snapshots and manual-capture experiments.
- Added round-level confidence intervals, baseline stability checks and operator-verification gates.
- Added offline interactive reports, CSV/JSON/Markdown and private-by-default report ZIP exports.
- Added tests, Linux CI, wheel/sdist builds, installation, methodology, optimization and contributor guides.

Validation recorded for this release: 48 automated tests and two three-run live replay sessions on Linux with native Steam, Proton and MangoHud. Capture and restoration completed. A GameInfo sequence had a 34.7-second median iteration with 10-second captures and 5-second warm-up; cold launches varied substantially. These smoke tests do not establish an optimization winner or replace camera/playback review.

Historical aggregate rows from the prototype are not accepted as validated measurements.
