# Troubleshooting

| Symptom | Action |
|---|---|
| `dpl` not found | Run `pipx ensurepath` and open a new terminal (or activate your venv). `python3 -m deadlock_perf_lab` is an equivalent entry point. |
| The app doesn't open in a browser | Open the `http://127.0.0.1:…` address that `dpl` prints. Over SSH, use `dpl gui --no-browser --port 8765` with `ssh -L 8765:127.0.0.1:8765`. |
| "This link has expired" | The app was closed, or it quit after 30 idle minutes. Run `dpl` again. |
| Steam launch options "not detected" | Steam may save them only when it closes. If you pasted the line from the app, carry on: the first capture fails with a clear message if MangoHud isn't recording. "Points elsewhere" means the line was pasted from another workspace; paste it again. |
| Where are my results? | In `~/.local/share/deadlock-performance-lab` (shown at the bottom of the app), or `./.lab` for workspaces made by earlier versions. `dpl --workspace PATH` picks another. |
| Game install not discovered | Type the folder into the app's **Set up** tab (or set `install` in `lab.json`); it contains `game/citadel/gameinfo.gi`. Native Steam is the supported launcher. |
| No game within 180 seconds | Sign into Steam, launch Deadlock once normally, finish updates and shader processing, close it, then retry with a new plan. See the run's `steam.log` and Steam's own logs. |
| No MangoHud file | Paste the launch options line from the app (or `dpl setup`) into Deadlock's Steam properties; environment variables given to an already-running Steam client don't reach the game. Confirm MangoHud works in your Proton game. |
| Old 100 ms / 10 Hz logs | Import/inspect with `--interval-ms 100`; never relabel them `0`. True 1%/0.1% lows and directional verdicts are unavailable. |
| Missing measurement window | Check logging duration and replay length. The parser rejects partial windows instead of treating them as the full test. |
| No VConsole / missing seek confirmation | Game protocol or console output may have changed. Inspect `vconsole.log`; test a local replay using `-dev -vconsole -insecure`. Never expose port 29000 beyond localhost. |
| Replay appears frozen or camera changed | Reject or leave the run unreviewed; choose a valid tick and live target. Do not approve it based only on an FPS number. |
| Cvar readback differs | The current build may reject, rename or protect it. The result stays blocked. Create a compatible treatment instead of waiving the check. |
| Baseline drift or variation | Stabilize thermal state, shader caches, scene and background load, then start a new session. |
| Planned file / system fingerprint changed | Make a new plan. This is an intentional comparison boundary. |
| Experiment already started | Partial sessions remain inspectable. This release starts a new session instead of resuming a partly changed experiment. |
| Workspace path rejected | Avoid commas, equals signs and newlines: MangoHud uses them as config syntax. Ordinary spaces are supported. |

## Slow Steam launches

`dpl timings` separates launch time from capture time. Steam's `shader_log.txt` can identify Vulkan pipeline preparation during a long wait. Let preparation finish and keep the renderer and cache state consistent between trials. Avoid toggling shader pre-caching to speed a run: [Valve notes that toggling flushes locally built shaders](https://github.com/ValveSoftware/steam-for-linux/issues/8973).

## Recover after interruption

Ctrl+C and SIGTERM request cleanup. SIGKILL, host shutdown and power loss cannot run a handler, so file operations use a durable journal. The backup and original checksum are persisted before each write. A per-install lock prevents simultaneous lab instances, including separate workspaces; a pending journal must be recovered before a new suite.

Close Deadlock, then press **Restore my files** in the app, or:

```bash
dpl --workspace /path/to/workspace recover
dpl --workspace /path/to/workspace doctor
```

An existing game is never stopped by the recovery command. Restoration preserves original contents, file mode and absence of files that did not exist before the run. Symlinks are refused. Corrupt/missing backups fail loudly.

If someone edited a file during the benchmark, automatic restoration stops to avoid overwriting that edit. Inspect the current file and journal. To deliberately keep a conflict copy and restore the verified original:

```bash
dpl recover --force
```

Conflict copies live beside the run's backup, under `conflicts/`. Keep the workspace until restoration is verified. Do not delete lock files to bypass another running experiment; the operating system releases the lock when its owner exits.

## Reporting a bug

Include version (`dpl --version`), Linux/Steam/Proton/MangoHud versions, the command, status, reproduction steps and a redacted error excerpt. Use the issue template. Share a report ZIP if useful. Do not upload an entire workspace: raw logs and backups can contain local paths, account identifiers, user configs or other private data.
