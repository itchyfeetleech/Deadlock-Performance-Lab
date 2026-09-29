# Troubleshooting

| Problem | Fix |
|---|---|
| `dpl` not found | Run `pipx ensurepath` and open a new terminal (or activate your venv). `python3 -m deadlock_perf_lab` also works. |
| The app doesn't open in a browser | Open the `http://127.0.0.1:…` address `dpl` prints. Over SSH: `dpl gui --no-browser --port 8765` with `ssh -L 8765:127.0.0.1:8765`. |
| "This link has expired" or "This window has expired" | The app was closed, or quit after 30 idle minutes. Run `dpl` again. |
| Steam launch options "not detected" | Steam may save them only when it closes. The first capture fails with a clear message if MangoHud isn't recording. "Points elsewhere" means the line came from another workspace; paste it again. |
| Presets "couldn't download" | Presets come from `raw.githubusercontent.com`. Check your connection or proxy and press **Refresh**/**Try again**. A previously downloaded copy is used offline. |
| "Made for a different game version" | The preset's `PGIVersion` differs from your installed `gameinfo.gi`, usually after a game update. Pick the preset again. |
| "The game rewrote video.txt" | The game normalized or rejected some video settings. The listed values are what it actually used; your file was still restored. |
| Settings "hidden from the console" | Normal for `gameinfo.gi` cvars. The whole file was applied and measured; those settings just couldn't be read back. |
| Where are my results? | `~/.local/share/deadlock-performance-lab` (shown at the bottom of the app), or `./.lab` for workspaces from earlier versions. `dpl --workspace PATH` picks another. |
| Game folder not found | Enter it in **Set up** (or `install` in `lab.json`); it contains `game/citadel/gameinfo.gi`. |
| No game within 180 seconds | Sign in to Steam, launch Deadlock once normally, let updates and shader processing finish, close it and start a new benchmark. See the run's `steam.log`. |
| No MangoHud file | Paste the launch options line from the app (or `dpl setup`) into Deadlock's Steam properties, and check MangoHud works in your Proton games. |
| Old 100 ms / 10 Hz logs | Import with `--interval-ms 100`. They have no 1%/0.1% lows. |
| Missing measurement window | The log or the replay is shorter than warm-up plus capture time. Pick an earlier tick or capture longer. |
| No VConsole / missing seek confirmation | The game's console output may have changed. Check the run's `vconsole.log`. Don't expose port 29000 beyond localhost. |
| Replay froze or the camera changed | Pick a different tick or player and run again. |
| Cvar readback differs | The game rejected, renamed or protected that cvar. The capture lists it in its notes. |
| High baseline variation or drift | Something besides the config changed between captures (heat, background load, shader compilation). Run again. |
| "Plan changed after creation" or a fingerprint mismatch | Make a new plan. |
| Workspace path rejected | Avoid commas, equals signs and newlines, which MangoHud treats as config syntax. Spaces are fine. |

## Slow Steam launches

`dpl timings` separates launch time from capture time. Steam's `shader_log.txt` shows Vulkan pipeline preparation during long waits. Toggling shader pre-caching [flushes locally built shaders](https://github.com/ValveSoftware/steam-for-linux/issues/8973).

## Recover after an interruption

Close Deadlock, then press **Restore my files** in the app, or:

```bash
dpl recover
dpl doctor
```

Every file write is journaled with its backup and checksum first, so a crash, SIGKILL or power loss can be recovered. Recovery restores contents, file modes and files that didn't exist before, and never stops a game it didn't start. Only one benchmark can run per game install, across workspaces.

If a file was edited during the benchmark, recovery stops rather than overwrite the edit. `dpl recover --force` keeps the edited file under the run's `conflicts/` folder and restores the original.

## Reporting a bug

Use the [bug report template](https://github.com/itchyfeetleech/Deadlock-Performance-Lab/issues/new?template=bug_report.yml). A share ZIP helps; a whole workspace can contain private paths and account IDs.
