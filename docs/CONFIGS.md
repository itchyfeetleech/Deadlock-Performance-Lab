# Custom gameinfo.gi and video.txt configs

A **config** is the `gameinfo.gi` and/or `video.txt` you want to test. The lab compares each config with your current setup on the same replay moment. It writes the config's files into the game only while a capture runs, and restores yours afterwards.

| File | Where it lives | What it controls |
|---|---|---|
| `gameinfo.gi` | `steamapps/common/Deadlock/game/citadel/` | Engine settings. Its `ConVars` block holds the performance cvars that community configs tweak. |
| `video.txt` | `steamapps/common/Deadlock/game/citadel/cfg/` | The in-game video options: resolution, shadow and fog quality, upscaling, and so on. |

## Build a config in the app

Open **Configs → New config**. Each file has its own tab (**gameinfo.gi** and **video.txt**), and both work the same way.

1. **Start from** a file:
   - **My current file**: your installed file. Nothing changes until you tick settings.
   - **A community preset** from [Sqooky's OptimizationLock](https://github.com/Sqooky/OptimizationLock): OptimizationLock, Boot's maximum FPS, Kaizuchaneru's minimum spec, the test config, Piggy's (outdated) or the clean Valve default. For `video.txt`: Liah's (test config) or Piggy's. The app downloads the file from GitHub when you pick it (and caches it for an hour), so you always get the current version. Nothing is bundled with the app.
   - **Import a file…**: any `gameinfo.gi` or `video.txt` you already have, for example one shared by a friend or your own hand-edited file.
2. **Tick the settings to change.** The settings are grouped into the same categories as OptimizationLock's documentation (Shadows, Particles, Lod & Culling, and so on), with its descriptions. Each row shows:
   - the value in the starting file,
   - your installed value (highlighted when different),
   - the engine default,
   - OptimizationLock's value.

   On/off settings get a switch; numbers get a slider and a box. Use the search box to find a setting by name or description. To test a cvar that isn't listed, type it under **Add any other setting**: the list covers every modifiable cvar documented upstream.
3. **Preview file changes** shows exactly what will be written, as a diff against your installed files.
4. **Save config.** It appears in the list and is ticked on the **Benchmark** tab.

### Test each setting separately

Ticking 20 settings and saving one config tells you whether the whole package helps, not which setting did it. To measure each on its own, press **Test each setting separately…** under the settings list:

- Every ticked setting is listed with its value. Change it, or enter several values separated by commas (`0.4, 1.0, 1.6, 2.4`) to see how the setting scales.
- Optionally save one more config with all of them together.
- Press **Create N configs**. Each starts from the same file you chose, changes exactly one setting, and is named `setting = value`. The name you typed becomes their label, and they appear as a group in the Configs and Benchmark tabs, with select-all and delete-all.
- A value that equals what's already in the starting file changes nothing, so it's skipped.

Twenty settings with one value each is 22 launches at Shortlist length, about 13 minutes. Rank them in **Results**, then use **Re-test the top N** on the best few. When you start from a preset, each config is that preset plus one setting; save the preset on its own as well, so you can see its effect separately.

Some notes on how the files are combined:

- A preset or imported `gameinfo.gi` **replaces the whole file**, including engine sections outside `ConVars`, just as installing it by hand would. Your ticked settings are applied on top, like the `overrides.gi` of OptimizationLock's own updater. If a preset was made for a different game version (its `PGIVersion` differs), the preview and the results say so. Pick the preset again to refresh it.
- A preset or imported `video.txt` always keeps your own `VendorID`, `DeviceID` and format `Version`. By default it also keeps your resolution, display mode, VSync and brightness, so only quality settings differ. Untick **Keep my resolution…** to test those too.
- The config stores the exact starting file it was saved with. Past results always keep their own frozen copy, so editing or deleting a config never changes them.

## Use the winner

After a **Confirm** benchmark shows a config you like, download its finished files from the config list (**gameinfo.gi ↓**, **video.txt ↓**). Close Deadlock, back up your files, and copy them into the folders above. The lab never installs a config permanently. After a game update, rebuild the config, or refresh its preset, and re-test.

## Tips

- Test one idea per config: a preset as it is, then the preset plus the one change you care about. A config that changes 250 settings tells you whether the whole package helps, not which setting did it.
- Keep the run settings on the Benchmark tab the same for configs you want to compare. **FPS limit** (default: uncapped) and **Graphics API** apply to every capture, including your current setup.
- Many `gameinfo.gi` cvars are hidden from the console, so the lab can't read them back. It reports how many it couldn't confirm; that doesn't invalidate the measurement of the file as a whole. Settings that read back a *different* value are listed in the report's notes.
- The game may rewrite `video.txt` (older configs had to be made read-only for this reason). If it does during a capture, the report notes which values changed, and the lab still restores your file afterwards.

## From the command line

```bash
dpl profile add my-config --gameinfo ~/Downloads/gameinfo.gi --video ~/Downloads/video.txt
dpl profile show my-config --diff        # what it would write, against your installed files
dpl plan --cases my-config --preset confirm --fps-max 0
dpl run --live
```

`--video` keeps your device and display settings in the same way as the app. `--fps-max N` sets an FPS limit for every capture (0 = uncapped; leave it out to keep the game's own). `--renderer vulkan|dx11` launches every capture with that API. To test many single-cvar values at once, see [testing many settings](ADVANCED.md).
