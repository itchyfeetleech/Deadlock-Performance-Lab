# First benchmark

This follows the app (`dpl`). The same steps as commands are at the end.

## Requirements

- Linux with Python 3.11+ ([install](../README.md#install)).
- Native Steam (not Flatpak) with Deadlock installed and a working Proton.
- [MangoHud](https://github.com/flightlessmango/MangoHud#installation) from your distribution's packages. Some setups also need its 32-bit package.
- A downloaded match replay (`.dem`).

The example report works without any of these.

## 1. Set up

Run `dpl`. The **Set up** tab has three steps.

**Check your PC** lists anything missing. Press **Check again** after installing it.

**Let Steam record frame times:** in Steam, right-click Deadlock → *Properties…* → *General* → *Launch Options* and paste the line the app shows:

```text
env -u MANGOHUD_CONFIG MANGOHUD=1 MANGOHUD_CONFIGFILE=/home/you/.local/share/deadlock-performance-lab/capture.conf %command%
```

Put any options you already use after `%command%`, and don't repeat `%command%`. MangoHud stays hidden and only records during a benchmark. Steam may not save launch options until it closes, so the app can show "not detected" until then; the first capture fails with a clear message if MangoHud isn't recording. If you delete the workspace, remove the line from Steam.

**Choose the test scene:**

| Field | |
|---|---|
| Deadlock folder | Usually found automatically. It contains `game/citadel`. |
| Replay file | Replays under `game/citadel`, newest first. *Other file…* takes any path inside that folder. |
| Start at tick | Where each capture starts. The replay has to run for the warm-up plus capture time after it. |
| Player to follow | The player slot the camera follows. |
| Target FPS | Frames slower than this count as over budget. |
| Your game settings | Resolution, graphics quality, Proton version and display mode, saved with each result. Required before benchmarking. |

A **bot match** can replace the replay. Bots behave differently in every capture, so bot results never get a verdict.

Your baseline ("current setup") is the game as installed, including changes you've already made to `gameinfo.gi` or `autoexec.cfg`. To compare against stock, build a config from the **Clean Valve default** preset.

## 2. Build a config

**Configs → New config:** choose what to start from (your file, an OptimizationLock preset or an imported file), tick the settings to change and press **Save config**. **Test each setting separately…** makes one config per ticked setting and value. See [Configs](CONFIGS.md).

## 3. Benchmark

On **Benchmark**, tick configs, choose a length and press **Start** with Deadlock closed.

| Length | Rounds | Capture |
|---|---:|---:|
| Quick look | 1 | 5 s |
| Shortlist | 1 | 10 s |
| Confirm | 5 | 30 s |

*FPS limit* (default uncapped) and *Graphics API* apply to every capture, including your current setup.

Each round measures your current setup, each config in shuffled order, then your current setup again, and every capture is a separate game launch. The app shows the number of launches and the time before you start.

While it runs, leave the game window alone. Closing the browser tab doesn't stop the benchmark. **Cancel and restore files** stops it and restores your files. After a power cut, close Deadlock and press **Restore my files**.

## 4. Results

**Results** lists every benchmark. **Details & review** has the ranking by change in average FPS (changes within your baseline variation are marked *≈ noise*) and every capture. **Re-test the top N** runs the best configs again at Confirm length with the same run settings.

Live captures need a manual check, because the app can't see whether the camera stayed on the player and the replay kept playing. Tick the captures you watched; comparisons that include unchecked captures get no verdict.

**Open report** shows each config's change with its 95% interval, per-round results, frame-time percentiles and traces, and every capture. **Share ZIP** downloads the report (`index.html`, `summary.md`, `summary.json`, `runs.csv`) without raw logs, game files or replay paths. Config names and notes are included.

Metrics and verdict rules are in the [methodology](METHODOLOGY.md).

## Commands

```bash
dpl doctor                                   # check your PC
dpl setup                                    # print the Steam launch options line
$EDITOR ~/.local/share/deadlock-performance-lab/lab.json   # replay, tick, player, conditions
dpl profile add my-config --gameinfo ~/Downloads/gameinfo.gi   # and/or --video FILE
dpl plan --cases my-config --preset confirm --fps-max 0   # freeze a plan and print its schedule
dpl run --live                               # close Deadlock first
dpl review --run 002-my-config --note 'Camera stayed on player 1 and the replay kept playing.'
dpl report --open
dpl export --output report.zip
```

A plan freezes the config files, run settings, replay, conditions and run order. Create a new plan to change any of them.
