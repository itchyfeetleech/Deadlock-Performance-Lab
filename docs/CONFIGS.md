# Configs

A **config** is the `gameinfo.gi` and/or `video.txt` you want to test. DPL writes its files into the game only while a capture runs and restores yours afterwards.

| File | Where it lives | What it controls |
|---|---|---|
| `gameinfo.gi` | `steamapps/common/Deadlock/game/citadel/` | Engine settings. Its `ConVars` block holds the cvars community configs change. |
| `video.txt` | `steamapps/common/Deadlock/game/citadel/cfg/` | The in-game video options. |

## Build a config

Open **Configs → New config**. Each file has its own tab and both work the same way.

1. **Start from** a file:
   - **My current file:** your installed file.
   - **A preset** from [Sqooky's OptimizationLock](https://github.com/Sqooky/OptimizationLock): OptimizationLock, Boot's maximum FPS, Kaizuchaneru's minimum spec, the test config, Piggy's (outdated) or the clean Valve default; for `video.txt`, Liah's (test config) or Piggy's. Presets are downloaded from GitHub when you pick one and cached for an hour.
   - **Import a file…:** any `gameinfo.gi` or `video.txt` you have.
2. **Tick the settings to change.** They're grouped by OptimizationLock's categories with its descriptions. Each row shows the value in the starting file, your installed value, the engine default and OptimizationLock's value. Search finds settings by name or description, and **Add any other setting** takes any documented cvar by name.
3. **Preview file changes** shows the diff against your installed files.
4. **Save config.** It's ticked on the **Benchmark** tab.

### Test each setting separately

**Test each setting separately…** under the settings list turns every ticked setting into its own config:

- Each setting is listed with its value. Enter several values separated by commas (`0.4, 1.0, 1.6, 2.4`) to get one config per value.
- Optionally, one more config combines them all.
- **Create N configs** makes configs named `setting = value` that start from the same file and change one setting each. They're grouped under the name you typed, with select-all and delete-all.
- A value that matches the starting file changes nothing, so it's skipped.

When you start from a preset, each config is that preset plus one setting.

### How files are combined

- A preset or imported `gameinfo.gi` **replaces the whole file**, including engine sections outside `ConVars`. Ticked settings are applied on top. If a preset was made for another game version (its `PGIVersion` differs), the preview and the results say so; pick the preset again to refresh it.
- A preset or imported `video.txt` keeps your `VendorID`, `DeviceID` and format `Version`. By default it also keeps your resolution, display mode, VSync and brightness; untick **Keep my resolution…** to test those too.
- A config stores the starting file it was saved with, and each benchmark keeps its own copy, so editing or deleting a config never changes past results.
- Many `gameinfo.gi` cvars are hidden from the console, so they can't be read back. The report says how many, and lists any setting that read back a *different* value.
- The game can rewrite `video.txt` while it runs. If it does during a capture, the report lists the values it changed; your file is still restored.

## Install a config

Download its files from the config list (**gameinfo.gi ↓**, **video.txt ↓**), close Deadlock and copy them into the folders above. DPL never installs a config. After a game update, refresh the preset and benchmark again.

## Commands

```bash
dpl profile add my-config --gameinfo ~/Downloads/gameinfo.gi --video ~/Downloads/video.txt
dpl profile show my-config --diff        # what it would write, against your installed files
dpl plan --cases my-config --rounds 5 --fps-max 0
dpl run --live
```

`--video` keeps your device and display settings like the app does. `--fps-max N` sets an FPS limit for every capture (0 = uncapped; omit to keep the game's own). `--renderer vulkan|dx11` launches every capture with that API. For many single-cvar configs at once, see [Advanced use](ADVANCED.md#test-many-settings).
