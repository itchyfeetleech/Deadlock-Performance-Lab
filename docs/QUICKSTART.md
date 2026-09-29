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
| Player to follow | The player slot (1–12) the camera follows. |
| Target FPS | Frames slower than this count as over budget. |
| Your game settings | Optional: resolution, graphics quality, Proton version and display mode, saved with each result. |

A **bot match** can replace the replay. Bots behave differently in every capture, so results vary more.

Your baseline ("current setup") is the game as installed, including changes you've already made to `gameinfo.gi` or `autoexec.cfg`. To compare against stock, build a config from the **Clean Valve default** preset.

## 2. Build a config

**Configs → New config:** choose what to start from (your file, an OptimizationLock preset or an imported file), tick the settings to change and press **Save config**. **Test each setting separately…** makes one config per ticked setting and value. See [Configs](CONFIGS.md).

## 3. Benchmark

On **Benchmark**, tick configs, set the benchmark up and press **Start** with Deadlock closed.

| Setting | |
|---|---|
| Rounds | Each round measures your current setup, every config in shuffled order, then your current setup again. 3 or more give a 95% interval. |
| Capture length | Time recorded per capture. |
| Warm-up | Replay time before seeking back to the start tick. |
| Settle | Pause on the start tick before recording. |
| Cooldown | Wait between captures. |
| FPS limit | Uncapped, the game's own setting, or a limit you pick. |
| Graphics API | Game default, Vulkan or DirectX 11. |

Rounds start at 3 and the timings at your `lab.json` values (30 s capture, 45 s warm-up, 5 s settle, 5 s cooldown). The app remembers your changes; **Reset** puts the defaults back. The FPS limit and graphics API apply to every capture, including your current setup. Every capture is a separate game launch, and the app shows the number of launches and the time before you start.

While it runs, leave the game window alone. Closing the browser tab doesn't stop the benchmark. **Cancel and restore files** stops it and restores your files. After a power cut, close Deadlock and press **Restore my files**.

## 4. Results

**Results** lists every benchmark. **Details** has the ranking by change in average FPS (changes within your baseline variation are marked *≈ noise*) and every capture. **Benchmark the top N again** ticks the best configs on the Benchmark tab and loads this benchmark's settings, to adjust and start.

**Open report** shows each config's change with its 95% interval, per-round results, frame-time percentiles and traces, and every capture. **Share ZIP** downloads the report (`index.html`, `summary.md`, `summary.json`, `runs.csv`) without raw logs, game files or replay paths. Config names and notes are included.

How changes and intervals are calculated: [methodology](METHODOLOGY.md).

## Commands

```bash
dpl doctor                                   # check your PC
dpl setup                                    # print the Steam launch options line
$EDITOR ~/.local/share/deadlock-performance-lab/lab.json   # replay, tick, player, conditions
dpl profile add my-config --gameinfo ~/Downloads/gameinfo.gi   # and/or --video FILE
dpl plan --cases my-config --rounds 5 --fps-max 0   # freeze a plan and print its schedule
dpl run --live                               # close Deadlock first
dpl report --open
dpl export --output report.zip
```

A plan freezes the config files, run settings, replay, conditions and run order. Create a new plan to change any of them.
