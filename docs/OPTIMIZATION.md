# Screening many settings

Most people should build configs in the app ([custom gameinfo.gi and video.txt configs](CONFIGS.md)). This page covers larger, command-line experiments: testing many single-cvar values to find which settings matter, then confirming the best ones. The baseline is always your current installation. See the [first benchmark guide](QUICKSTART.md) for capture setup.

## Console cvars instead of files

Configs change `gameinfo.gi` and `video.txt`. To test cvars set from the console at launch instead (a temporary `autoexec`):

```bash
printf 'r_farz 6000\n' > farz.cfg
dpl profile add farz-6000 --autoexec farz.cfg --description 'Shorter far plane'
dpl plan --cases farz-6000 --preset confirm
```

Only cvar assignments and comments are accepted. Commands that load other configs, bind keys or change the scene are rejected. Use [manual experiments](MANUAL_EXPERIMENTS.md) for settings the lab can't apply, such as Proton, drivers or OS settings. A frame cap and the graphics API are run settings, not configs: `--fps-max` and `--renderer` on `dpl plan`, or the Benchmark tab in the app.

## Screen a large set

Use short captures to find candidates, then confirm them in a fresh experiment with longer captures and repeated rounds. The app offers the first three presets as Quick look, Shortlist and Confirm.

| Preset (app name) | Rounds by default | Capture | Warm-up | Settle | Cooldown |
|---|---:|---:|---:|---:|---:|
| `scout` (Quick look) | 1 | 5 s | 2 s | 1 s | 0 s |
| `screen` (Shortlist) | 1 | 10 s | 5 s | 1 s | 0 s |
| `confirm` (Confirm) | 5 | 30 s | 45 s | 5 s | 5 s |
| `custom` (command-line default) | 5 | From `lab.json` | From `lab.json` | From `lab.json` | From `lab.json` |

`--rounds N` overrides the round count. Presets are saved in the plan without editing `lab.json`. Short passes can miss small effects and intermittent stalls; neither `scout` nor `screen` has enough rounds for an improvement verdict.

To generate one-cvar GameInfo profiles from a CSV:

```bash
dpl profile sweep examples/convar-matrix.csv --base '/path/to/Deadlock/game/citadel/gameinfo.gi'
dpl plan --cases 'gi*' --preset screen --experimental
dpl run --live
dpl shortlist --top 5
```

The CSV requires `id,cvar,value`, with an optional `name`. Each profile changes one direct ConVars assignment, or adds it if absent. Duplicate definitions and unchanged values are rejected. The base file must match your current GameInfo when you plan the live run. Single-cvar sweeps are stricter than configs: a setting the console can't read back blocks that treatment's verdict, because the cvar is the thing being tested. The [example matrix](../examples/convar-matrix.csv) contains candidates to test, not recommended settings. Quote selectors such as `'gi*'` to prevent shell expansion.

Inspect the shortlisted results, then use their profile IDs in a new plan:

```bash
dpl plan --cases gi-example-a,gi-example-b --preset confirm --experimental
dpl run --live
```

Rankings use average FPS change and do not override measurement checks. Compare each treatment with its own session's baselines; different presets use different capture conditions.

## Estimate runtime

```bash
dpl timings
```

This shows successful-run durations, phase medians and an estimate of remaining time. Every capture uses a fresh game process. A one-round screen of 50 treatments means 52 launches, including the two baselines. Launching, loading and seeking take time beyond the preset durations.

Large launch delays can come from Steam shader preparation. Let it finish and keep the renderer and cache state consistent between trials. See [troubleshooting](TROUBLESHOOTING.md) for startup and capture failures.

New plans start replay loading from the temporary startup config and seek immediately after confirmed signon. Cvar readback and final demo-info requests use engine acknowledgements rather than fixed delays; hidden cvars are reported. Readback runs during the configured camera-settle interval. These changes reduce setup time while retaining the configured warm-up and capture duration. Create a fresh plan to use the new replay-start protocol; existing plans preserve their recorded scenario.

Repeated captures still launch a fresh process. Reusing a process for all five repetitions could save more launch/load time, but changes the independence and cache history of the experiment and is not supported by this runner. Replay seeking already uses the engine's fast-goto path when available; changing demo speed, cutting the replay file, or skipping warm-up can change the scene or cache state being measured.
