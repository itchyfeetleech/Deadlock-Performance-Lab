# Advanced use

## Benchmark settings

| Setting | `dpl plan` | App range | Default |
|---|---|---|---|
| Rounds | `--rounds N` | 1–30 | 3 |
| Capture length | `--capture SECONDS` | 5–180 s | `lab.json` (30 s) |
| Warm-up | `--warmup SECONDS` | 0–180 s | `lab.json` (45 s) |
| Settle | `--settle SECONDS` | 0–30 s | `lab.json` (5 s) |
| Cooldown | `--cooldown SECONDS` | 0–120 s | `lab.json` (5 s) |
| FPS limit | `--fps-max N` (0 = uncapped) | Uncapped, game's setting, or 30–500 | App: uncapped. Command line: the game's setting |
| Graphics API | `--renderer default\|vulkan\|dx11` | Game default, Vulkan, DirectX 11 | Game default |

On the command line, timings can go up to 600 s (capture and warm-up) and 300 s (settle and cooldown). A round is your current setup, every config once in shuffled order, then your current setup again, and every capture is a fresh game launch: 50 configs for one round is 52 launches. Steam shader preparation can make a launch much slower. `dpl timings` shows how long captures took and estimates what remains.

## Test many settings

1. **One config per setting or value.** In the app, tick settings and press **Test each setting separately…**. From the command line, write a CSV with `id,cvar,value` columns and an optional `name`:

   ```bash
   printf 'id,cvar,value,name\nfarz-6000,r_farz,6000,Shorter far plane\ncull-16,r_size_cull_threshold,1.6,Cull small objects\n' > tests.csv
   dpl profile sweep tests.csv              # start from your installed gameinfo.gi
   dpl profile sweep tests.csv --base ~/Downloads/gameinfo.gi   # or from another file
   ```

   Each config changes or adds one setting. A row that changes nothing is rejected.
2. **Rank** them with a short run, for example one round of 10 s captures. **Results** ranks them by change in average FPS. From the terminal: `dpl plan --cases 'farz*,cull*' --rounds 1 --capture 10 --warmup 5`, `dpl run --live`, then `dpl shortlist --top 5`.
3. **Run the best ones again** with more rounds: **Benchmark the top N again** in Results, or `dpl plan --cases … --rounds 5`.

## Console cvars

To test cvars set from the console at launch (a temporary `autoexec`) instead of files:

```bash
printf 'r_farz 6000\n' > farz.cfg
dpl profile add farz-6000 --autoexec farz.cfg --description 'Shorter far plane'
dpl plan --cases farz-6000 --rounds 5
```

Only cvar assignments and comments are accepted. The FPS limit and graphics API are run settings, not configs: `--fps-max` and `--renderer` on `dpl plan`, or the Benchmark tab.

## Manual captures

For changes DPL can't apply itself (Proton, drivers, upscaling, VRR/VSync, display modes, power settings), you make the change and capture with MangoHud yourself, then import the logs.

```bash
dpl profile add shadows-low --manual --description 'Shadow quality High → Low'
dpl plan --manual --cases shadows-low --rounds 5
dpl setup --manual
```

The plan prints the capture order: with one change, each round is baseline → shadows-low → baseline. `dpl setup --manual` writes `manual.conf` in the workspace and prints the Steam launch options line for it; logging is per-frame, off at startup, and writes to the workspace's `imports/` folder. Record your game settings in the app's **Set up** tab (or `lab.json`) first, and set `sample_s` to your capture length.

For each scheduled capture:

1. Apply the baseline or changed setting, restarting the game if the setting needs it.
2. Warm up the same scene and camera.
3. Press **Shift+F2** (MangoHud's default logging toggle), capture at least the planned duration, then press it again.
4. Import the log in schedule order. Use `--start` if the measurement starts later in the file.

```bash
W=~/.local/share/deadlock-performance-lab
dpl inspect $W/imports/deadlock_FIRST.csv --interval-ms 0 --start 0 --duration 30
dpl import $W/imports/deadlock_FIRST.csv --case baseline --round 1 --interval-ms 0
dpl import $W/imports/deadlock_SECOND.csv --case shadows-low --round 1 --interval-ms 0
dpl import $W/imports/deadlock_THIRD.csv --case baseline --round 1 --interval-ms 0
```

Imports out of order, repeated logs, or logs from different hardware or logging intervals are rejected. Each import is copied into the session.

Then open the report with `dpl report --open`. Manual sessions also appear in the app's **Results** tab. To go back to automated capture, paste the line from **Set up** (or `dpl setup`) into Steam in place of the `manual.conf` one.
