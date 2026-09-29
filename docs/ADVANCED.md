# Advanced use

Most benchmarks need only the app: build [configs](CONFIGS.md), press start, read the ranking. This page covers testing many settings at scale, console cvars, and settings the lab can't apply for you. See the [first benchmark guide](QUICKSTART.md) for setup.

## Benchmark lengths

| App name | `--preset` | Rounds | Capture | Warm-up | Settle | Cooldown |
|---|---|---:|---:|---:|---:|---:|
| Quick look | `scout` | 1 | 5 s | 2 s | 1 s | 0 s |
| Shortlist | `screen` | 1 | 10 s | 5 s | 1 s | 0 s |
| Confirm | `confirm` | 5 | 30 s | 45 s | 5 s | 5 s |
| (command line only) | `custom` | 5 | from `lab.json` | from `lab.json` | from `lab.json` | from `lab.json` |

`--rounds N` overrides the round count. Short passes can miss small effects and intermittent stalls, and one round has no way to produce a verdict, so use them to find candidates. Each round is your current setup, every config once in shuffled order, then your current setup again, and every capture launches a fresh game process. Testing 50 configs for one round is 52 launches. Steam shader preparation can make a launch much slower; let it finish and keep the renderer and cache state the same between trials.

## Test many settings

Find out which of many settings matter, then confirm the best few:

1. **Make one config per setting (or value).** In the app, tick the settings in the builder and press **Test each setting separately…**. Give a setting several values (`1, 2, 4, 8`) to see how it scales. The command-line equivalent reads a CSV with `id,cvar,value` columns and an optional `name`:

   ```bash
   printf 'id,cvar,value,name\nfarz-6000,r_farz,6000,Shorter far plane\ncull-16,r_size_cull_threshold,1.6,Cull small objects\n' > tests.csv
   dpl profile sweep tests.csv              # start from your installed gameinfo.gi
   dpl profile sweep tests.csv --base ~/Downloads/gameinfo.gi   # or from another file
   ```

   Each config changes one setting, or adds it if it's absent. A row that would change nothing is rejected.
2. **Shortlist.** Run all of them once (Shortlist length). The ranking in **Results** sorts by change in average FPS and marks anything smaller than the variation between your two baseline captures as noise. From the terminal: `dpl plan --cases 'farz*,cull*' --preset screen`, `dpl run --live`, then `dpl shortlist --top 5`.
3. **Confirm.** Press **Re-test the top N** in Results, or plan the winners with `--preset confirm`. Only a five-round run can give an *improved* or *regressed* verdict.

Rankings use average FPS and never override the measurement checks. A broad search will always produce a lucky winner, which is why the second run matters. Compare each config only with its own run's baselines, because different lengths use different capture conditions.

`dpl timings` shows how long captures actually took and estimates what remains.

## Console cvars instead of files

Configs change `gameinfo.gi` and `video.txt`. To test cvars set from the console at launch instead (a temporary `autoexec`):

```bash
printf 'r_farz 6000\n' > farz.cfg
dpl profile add farz-6000 --autoexec farz.cfg --description 'Shorter far plane'
dpl plan --cases farz-6000 --preset confirm
```

Only cvar assignments and comments are accepted. Commands that load other configs, bind keys or change the scene are rejected. The FPS limit and graphics API are run settings, not configs: `--fps-max` and `--renderer` on `dpl plan`, or the Benchmark tab.

## Settings you change by hand

Manual experiments cover Proton, drivers, upscaling, VRR/VSync, display modes, OS power settings and anything else the lab can't apply for you. The application does not edit these settings for you. Record the exact settings and restore the control setup for each baseline.

### Prepare one treatment

```bash
dpl profile add shadows-low --manual --description 'Change shadow quality from High to Low; all other video settings unchanged'
```

Record the baseline conditions in the app's **Set up** tab (or edit `lab.json` in your workspace, `~/.local/share/deadlock-performance-lab` by default), together with the intended scenario, timing and frame budget. Record driver/Mesa version, Proton, resolution, render scale, VSync/VRR, display mode, overlays and background load. Set `sample_s` to your intended window, usually 30 seconds.

```bash
dpl plan --manual --cases shadows-low --rounds 5
dpl setup --manual
```

The printed schedule defines the capture order. With one treatment each round is baseline → shadows-low → baseline. A frozen manual plan accepts only imports; it cannot launch an automated suite. The setup command writes `manual.conf` in the workspace and prints the per-game Steam launch options line. Manual logging uses `log_interval=0`, is off at startup and writes into the workspace's `imports/` folder.

### Capture each scheduled trial

1. Set the scheduled baseline or treatment. Restart the game when the setting needs a restart.
2. Warm the same scene and establish the same camera. For replay work, seek back to your intended starting point after warming.
3. Press **Shift+F2** (MangoHud's default logging toggle) to start. Capture at least the planned duration, then toggle it off. MangoHud hotkeys can be overridden by your configuration; see the [official configuration](https://github.com/flightlessmango/MangoHud/blob/master/data/MangoHud.conf).
4. Preserve a separate CSV for each trial. Complete repeat rounds independently; do not split one CSV into “repeats.”
5. Inspect and import the stopped log. If the actual measurement begins 2 seconds into the file, pass `--start 2`; the parser requires enough coverage for the complete planned duration.

```bash
W=~/.local/share/deadlock-performance-lab
dpl inspect $W/imports/deadlock_FIRST.csv --interval-ms 0 --start 0 --duration 30
dpl import $W/imports/deadlock_FIRST.csv --case baseline --round 1 --interval-ms 0
dpl import $W/imports/deadlock_SECOND.csv --case shadows-low --round 1 --interval-ms 0
dpl import $W/imports/deadlock_THIRD.csv --case baseline --round 1 --interval-ms 0
```

Continue with rounds 2–5. Follow the actual schedule when testing multiple treatments. Changed capture hardware metadata or logging intervals, repeated source hashes and wrong-order imports are rejected. A copy is stored per run; changing the original later does not change the experiment's evidence.

### Confirm conditions and interpret

An imported CSV cannot establish which settings or camera were active. Record a specific operator review for each capture you checked:

```bash
dpl review --run 002-shadows-low --note 'Confirmed Low shadows, same replay tick and player POV, and the unchanged baseline settings shown in my notes.'
dpl report --open
```

Manual sessions also appear in the app's **Results** tab, where you can open their reports.

Reviews are bound to the exact result hash. They cannot waive bad data or missing pre-recorded conditions. Reports summarize available CPU/GPU telemetry to support investigation, but low GPU load alone does not prove a CPU bottleneck.

To return to automated replay capture, paste the line from the app's **Set up** tab (or `dpl setup`) back into Steam, replacing the `manual.conf` one.
