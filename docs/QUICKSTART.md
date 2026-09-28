# Your first benchmark

This guide follows the app (`dpl`). Every step also has a terminal equivalent, listed at the end.

## What you need

- Linux with Python 3.11+. [Install the app](../README.md#install-and-open).
- Native Steam, signed in to an account that owns Deadlock, with a working Proton. Flatpak Steam and remote streaming aren't supported.
- [MangoHud](https://github.com/flightlessmango/MangoHud#installation) from your distribution's packages. Some setups also need its 32-bit package.
- A downloaded match replay (`.dem`). Replays aren't distributed with this project.

The example report and all analysis work without any of these.

## 1. Set up

Run `dpl`. The **Set up** tab has three steps. Each one turns green when it's done.

**Check your PC** lists anything missing, with the fix. Press **Check again** after installing something.

**Let Steam record frame times** gives you one line. In Steam, right-click Deadlock → *Properties…* → *General* → *Launch Options* and paste it:

```text
env -u MANGOHUD_CONFIG MANGOHUD=1 MANGOHUD_CONFIGFILE=/home/you/.local/share/deadlock-performance-lab/capture.conf %command%
```

Keep any options you already use after `%command%`, and don't repeat `%command%`. Wrappers such as GameMode or gamescope need to be combined deliberately; write your final launch options in the notes field. The line loads MangoHud invisibly, and it only records while a benchmark runs, so normal play doesn't change. Steam sometimes saves launch options only when it closes, so the app may not detect the line right away; the first capture confirms it. If you ever delete the workspace, remove the line from Steam too.

**Choose the test scene** decides what every config is measured on:

| Field | What to enter |
|---|---|
| Deadlock folder | Usually found automatically. It contains `game/citadel`. |
| Replay file | Replays in `game/citadel` (for example `game/citadel/replays/`), newest first. Choose *Other file…* for anything else inside that folder. |
| Start at tick | A busy moment such as a teamfight. Leave plenty of replay after it: at least warm-up plus capture time. |
| Player to follow | The player slot the camera follows. Choose someone who stays alive for the whole capture. |
| Target FPS | Usually your monitor's refresh rate. Slower frames count as over budget. |
| Your game settings | Resolution, graphics quality, Proton version and display mode. Detected values are pre-filled; check them. Results can't get a verdict until these are filled in. |

A **bot match** scene is available for rough CPU stress tests. Bots behave randomly, so bot results never get a verdict.

Your baseline is your installation exactly as it is, including any existing `gameinfo.gi` or `autoexec.cfg` changes. If you want stock Deadlock as the control, restore it yourself first (for example with Steam's *Verify integrity of game files*).

## 2. Benchmark

On the **Benchmark** tab:

1. **Tick the configs to compare.** Built-ins cover FPS caps, the Vulkan and DX11 renderers, and four attributed community `gameinfo.gi` files (marked *whole file*). Choose *Add your own console settings* for cvars such as `fps_max 165`.
2. **Choose how thorough:**

   | Length | Rounds | Capture | Use it for |
   |---|---:|---:|---|
   | Quick look | 1 | 5 s | Checking everything works and seeing rough numbers |
   | Shortlist | 1 | 10 s | Screening many configs to find ones worth confirming |
   | Confirm | 5 | 30 s | A real answer: the only length that can give *improved* or *regressed* |

3. **Close Deadlock and press Start.** The app shows how many launches and roughly how long before you start.

Each round measures your current setup, then each config in a shuffled order, then your current setup again. One config at *Confirm* length means 15 launches. While it runs:

- Don't touch the game window, and avoid heavy background work.
- You can close the browser tab or the app. The benchmark keeps going, and reopening `dpl` shows its progress.
- **Cancel and restore files** stops cleanly and restores your files. If the PC loses power mid-run, close Deadlock, open the app and press **Restore my files**.

For the first run, a *Quick look* with one config is a good smoke test.

## 3. Results

The **Results** tab lists every benchmark. **Open report** shows:

- **Baseline stability.** Check its variation (CV) and drift first. High values mean something other than the config changed.
- **Each config against the baseline:** average FPS, 1% lows, P99 frame time, the change in percent with a 95% interval, and a verdict with the reasons it was or wasn't given.
- **Frame-time traces.** Overlay any two captures to see stutters.

**Details & review** lists every capture. The lab can't see your screen, so live captures carry checks only you can clear. Confirm that the camera stayed on the player, the replay kept playing and the config visibly applied. Tick the captures you actually watched and describe how you checked. Verdicts stay *inconclusive* until the relevant captures are confirmed. The app can't clear malformed data, missing settings or failed cvar readback.

**Share ZIP** downloads `index.html`, `summary.md`, `summary.json` and `runs.csv`, which open offline. Raw logs, backups, configs and replay paths stay on your machine. Your config names and notes are included, so check them before sharing.

Rerun a promising result as a new *Confirm* benchmark before trusting it. The [methodology](METHODOLOGY.md) explains every metric and rule.

## Terminal equivalent

```bash
dpl doctor                                   # check your PC
dpl setup                                    # print the Steam launch options line
$EDITOR ~/.local/share/deadlock-performance-lab/lab.json   # replay, tick, player, conditions
dpl profiles                                 # list configs; dpl profile show ID for details
dpl plan --cases fps-unlock --preset confirm # freeze a plan and print its schedule
dpl run --live                               # close Deadlock first
dpl review --run 002-fps-unlock --note 'Watched it: camera stayed on player 1 and the replay kept playing.'
dpl report --open
dpl export --output report.zip
```

`dpl plan --cases baseline --rounds 1` followed by `dpl run --live` is a quick smoke test. The plan freezes configs, replay, conditions and run order. Create a new plan to change any of them.
