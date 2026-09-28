# Research experiments

This folder holds the scripts and inputs behind the community results published at
[itchyfeetleech.github.io/Deadlock-Performance-Lab](https://itchyfeetleech.github.io/Deadlock-Performance-Lab/).
You do **not** need anything here to benchmark your own setup — use the `dpl` app for that.

| Path | Purpose |
|---|---|
| [`particle-value-matrix.csv`](particle-value-matrix.csv) | The 32 numeric CVAR values tested in the value sweep |
| [`scripts/prepare_value_sweep.py`](scripts/prepare_value_sweep.py) | Freezes the sweep plan (one baseline per round); never launches the game |
| [`scripts/value_sweep_summary.py`](scripts/value_sweep_summary.py) | Exports per-value averages from a finished session |
| [`scripts/publish_value_sweep.py`](scripts/publish_value_sweep.py) | Rebuilds the published page and charts in [`site/`](../site) (needs matplotlib) |

The published pages and data live in [`site/`](../site), which GitHub Pages deploys.
The 100-CVAR teamfight screen is documented in [`site/results/README.md`](../site/results/README.md).

Run the scripts from the repository root with the tool installed (`pip install -e .`), as modules:
`python -m research.scripts.<name>`.

## Numeric CVAR value sweep

Completed: **99/99 captures**. [Published report](https://itchyfeetleech.github.io/Deadlock-Performance-Lab/particle-values.html) · [Shareable chart](../site/results/particle-values-summary.png).

Prepared at Sqooky's request after the 100-CVAR screen. This tests eight numeric CVARs at four candidate values each, independently: **32 variants × 3 repeats + 3 baselines = 99 captures**. It is prepared only; no game is launched by the preparation script.

| CVAR | Reference value* | Candidate values | Reason to test |
|---|---:|---|---|
| `cl_particle_fallback_base` | 0 | 2, 5, 10, 20 | Base setting for cheaper particle effects under load. |
| `cl_particle_fallback_multiplier` | 0 | 2, 5, 10, 20 | Scales fallback behavior; requested by Sqooky. |
| `cl_particle_sim_fallback_threshold_ms` | 6 | 1, 2, 4, 8 | Simulation-time threshold for new systems to use cheaper effects. |
| `cl_particle_sim_fallback_base_multiplier` | 5 | 1, 10, 25, 100 | How aggressively simulation overload triggers cheaper effects. |
| `r_particle_max_size_cull` | 1200 | 600, 900, 1600, 2400 | CPU/GPU tradeoff: systems larger in every dimension skip culling; lower values can save CPU checks while drawing more. |
| `r_size_cull_threshold` | 0.8 | 0.4, 1.0, 1.6, 2.4 | Strongest positive result in the screen: 1.6 averaged +6.66% FPS. |
| `cl_particle_max_count` | 0 | 250, 500, 1000, 2000 | 500 averaged −9.22% FPS; check whether the response changes with the count setting. |
| `lb_sun_csm_size_cull_threshold_texels` | 10 | 5, 20, 30, 60 | Numeric shadow-culling candidate; 30 averaged +2.07% FPS. |

*Reference values are provisional defaults from the community CVAR definitions, not independently verified live readbacks for these hidden settings. The actual reference configuration is the complete installed GameInfo at planning time, with existing video and autoexec settings. The common baseline covers the reference point; candidate values do not include unchanged default copies. These are test values, not recommended settings or proven safe visual limits.

The candidate definitions and particle-size interpretation come from [OptimizationLock's CVAR reference](https://github.com/Sqooky/OptimizationLock/blob/main/cvars_we_can_modify.txt) and [its base config](https://github.com/Sqooky/OptimizationLock/blob/main/Sqooky's%20.gi/base_convars.txt). Historical effects are exploratory arithmetic means from [the three-repeat screen](../site/results/teamfight100-three-repeat.csv).

Keep the same replay scene: demo `102565106.dem`, tick **134987**, player **1**, 10-second captures, 10-second warm-up, 2-second camera settling and no cooldown. The preparation script uses the replay configured in `.lab/lab.json` and explicitly freezes those timings and tick. Each variant changes one direct GameInfo ConVars assignment; each capture restarts the game and restores its original files. Order is seeded and shuffled each round, with the three baselines at the beginning, middle and end of their respective rounds.

Fallback controls may interact or remain inactive unless the workload crosses a threshold. A flat result does not prove a CVAR is useless. Do not combine candidates in this first pass. Afterward, compare all three captures, FPS, slow frames, readback quality and visual cues; use a separate confirmation experiment for the best candidate values or fallback combinations. Object/shadow culling can remove useful visual detail. These three-repeat averages are exploratory, with no bracketed statistical verdict.

## Prepare

### Prepare

```bash
python -m research.scripts.prepare_value_sweep
```

This reads [the value matrix](particle-value-matrix.csv), creates or reuses identical one-CVAR profiles, freezes a new plan and writes its path to `research/particle-values/session.txt` inside your workspace. It does not change the live game configuration or overwrite earlier sessions.

### Run

With Steam running and Deadlock closed, start the prepared session from the app's **Results** page, or from a terminal:

```bash
dpl run SESSION_ID --live
```

At roughly 37 seconds per capture, expect about **one hour**, plus variable Steam shader preparation.

### Summarize and publish

```bash
python -m research.scripts.value_sweep_summary SESSION_DIR
python -m research.scripts.publish_value_sweep SESSION_DIR
```

The summary writes `report/value-sweep-averages.csv` inside the session. It keeps counts and quality notes so incomplete or unverified candidates stay visible, and it does not label a "best" value. The publisher re-verifies every raw capture and writes `site/particle-values.html` and `site/results/particle-values-*`.
