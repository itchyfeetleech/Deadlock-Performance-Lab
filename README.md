<div align="center">

<img src="src/deadlock_perf_lab/assets/icon.svg" width="72" alt="" />

# DPL · Deadlock Performance Lab

**Find out which `gameinfo.gi` and `video.txt` settings really change your FPS in Deadlock on Linux.**

[![CI](https://github.com/itchyfeetleech/Deadlock-Performance-Lab/actions/workflows/ci.yml/badge.svg)](https://github.com/itchyfeetleech/Deadlock-Performance-Lab/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-d0df9c)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-Linux-d0df9c)](docs/QUICKSTART.md)
[![GPL v3](https://img.shields.io/badge/license-GPLv3-d0df9c)](LICENSE)

[Install](#install) · [First benchmark](docs/QUICKSTART.md) · [Configs guide](docs/CONFIGS.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

<img src="docs/images/app-configs.png" width="860" alt="The config builder: a preset from Sqooky's OptimizationLock with settings grouped by category, switches and sliders" />

</div>

Config guides tell you what to change. DPL measures what each change does on **your** machine. Tick the settings you want to try, press start, and it launches Deadlock, plays the same replay moment for every config, records every frame with MangoHud, and compares each config with your current setup.

- **Build configs your way.** Start from your own files, a [Sqooky OptimizationLock](https://github.com/Sqooky/OptimizationLock) preset (fetched from GitHub when you pick it), or a file you import. Tick settings, grouped and described, with switches and sliders.
- **Test many settings separately.** *Test each setting separately* turns every ticked setting (and every value you list) into its own config, so you see what each one does alone.
- **Trust the numbers.** Your current setup is measured before and after every round, so noise and drift show up. Results are ranked with the noise floor marked, and a verdict needs repeated rounds.
- **Nothing is left changed.** Game files are backed up, used for the capture, and restored, even after a crash.

## Install

You need Linux and Python 3.11 or newer, which most distributions already have.

```bash
pipx install git+https://github.com/itchyfeetleech/Deadlock-Performance-Lab.git
dpl
```

`dpl` opens the app in your browser. **See an example report** shows what you'll get, using made-up data, no game needed. **Add to app menu** puts a launcher in your desktop so you don't need the terminal again.

<details>
<summary>No <code>pipx</code>, or want to update?</summary>

- Install pipx: `sudo apt install pipx` (Debian/Ubuntu), `sudo pacman -S python-pipx` (Arch) or `sudo dnf install pipx` (Fedora), then `pipx ensurepath` and open a new terminal.
- Or use [uv](https://docs.astral.sh/uv/): `uv tool install git+https://github.com/itchyfeetleech/Deadlock-Performance-Lab.git`.
- Or download `dpl.pyz` from the [latest release](https://github.com/itchyfeetleech/Deadlock-Performance-Lab/releases/latest) and run `python3 dpl.pyz` (releases from 0.3.0).
- Update with `pipx upgrade deadlock-perf-lab`.

</details>

Real benchmarks also need native (non-Flatpak) Steam, Deadlock, [MangoHud](https://github.com/flightlessmango/MangoHud#installation) and a downloaded match replay. The app checks all of this for you.

## Use it in four steps

1. **Set up.** Paste one line into Deadlock's Steam launch options, then pick a replay and the moment to measure. Your resolution, display mode and Proton version are filled in.
2. **Configs.** Build what you want to test. Preview the exact file changes before saving.
3. **Benchmark.** Tick configs, choose **Quick look**, **Shortlist** or **Confirm**, and press **Start**. You're told up front how many launches and how long it will take.
4. **Results.** Read the ranking, open the full report, confirm the captures you watched, re-test the best few at Confirm length, and share a ZIP.

<img src="docs/images/app-results.png" width="860" alt="Results ranking: configs sorted by FPS change against the baseline, with a re-test button" />

<details>
<summary>The full report (example data)</summary>

<img src="docs/images/report-desktop.png" width="860" alt="The offline report: baseline stability, each config's FPS change with its interval, and frame-time comparisons. All values are synthetic." />

</details>

Then download the winning config's files from the Configs tab and install them yourself. DPL never installs a config permanently.

## Is it safe?

- **Your files come back.** `gameinfo.gi`, `video.txt` and a temporary `autoexec` are backed up first, restored after every capture, and recovered with one click (or `dpl recover`) after a power cut.
- **It only runs local replays** (or a bot match), launched with `-insecure`, which turns VAC off for that launch. It never joins online matches.
- **It stays on your machine.** The app listens only on `127.0.0.1` and downloads only the presets you pick. Shared ZIPs contain the report, not raw logs, game files or replay paths.
- **It won't touch Steam settings, drivers or a game you started yourself.**

A verdict of *improved* or *regressed* needs five rounds, stable baselines and your confirmation that captures looked right. Shorter runs give numbers and a ranking, not proof. See [how results are measured](docs/METHODOLOGY.md).

## Command line

Everything in the app is also a command.

| Command | What it does |
|---|---|
| `dpl` | Open the app (`dpl gui --no-browser` prints the address instead) |
| `dpl demo --open` | Build and open the example report |
| `dpl doctor` · `dpl setup` | Check your PC · print the Steam launch line |
| `dpl profile add NAME --gameinfo FILE --video FILE` | Save your own files as a config |
| `dpl profile sweep tests.csv` | One config per `id,cvar,value` row |
| `dpl plan --cases A,B --preset confirm --fps-max 0` → `dpl run --live` | Plan and run a benchmark |
| `dpl report --open` · `dpl export --output report.zip` | Open or share a report |
| `dpl recover` | Put game files back after an interrupted run |

`dpl --help` lists everything. Settings and results live in `~/.local/share/deadlock-performance-lab` (change with `--workspace` or `DPL_WORKSPACE`).

## Documentation

| | |
|---|---|
| [First benchmark](docs/QUICKSTART.md) | Set up and run your first comparison |
| [Configs](docs/CONFIGS.md) | Presets, ticking settings, `video.txt`, imports, installing a winner |
| [Advanced use](docs/ADVANCED.md) | Testing many settings, run lengths, console cvars, Proton and driver tests |
| [Methodology](docs/METHODOLOGY.md) | Metrics, rounds, verdict rules and their limits |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common problems and recovery |
| [Changelog](CHANGELOG.md) | What changed in each version |

## Contributing

Bug reports, tested presets and docs fixes are welcome. See [CONTRIBUTING](.github/CONTRIBUTING.md) for development setup and how the code is organised, and [SECURITY](.github/SECURITY.md) to report a vulnerability.

[GPL-3.0-only](LICENSE). Presets come from [Sqooky/OptimizationLock](https://github.com/Sqooky/OptimizationLock) (GPL-3.0) at your request; credits are in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). An independent community project, not affiliated with Valve.
