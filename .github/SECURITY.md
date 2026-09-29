# Security

## Reporting a vulnerability

Use GitHub's [private vulnerability reporting](https://github.com/itchyfeetleech/Deadlock-Performance-Lab/security/advisories/new). If that isn't available, open an issue that asks for a private contact, without exploit details or private captures.

## What the tool does on your machine

- **Runs as your user** and temporarily writes game config files (`gameinfo.gi`, `video.txt`, an `autoexec_dpl.cfg`). A write-ahead journal restores them after every capture.
- **Benchmarks are local.** They play a local replay or a bot match, launched with `-insecure`, and talk to the game over its console on `127.0.0.1:29000`. Don't expose that port through a firewall or tunnel.
- **The app listens only on `127.0.0.1`.** Each launch creates a secret that the opened link turns into a `SameSite=Strict` cookie, and every change also needs a header other websites can't send, so other sites and other users can't drive it. Don't put it behind a tunnel or proxy.
- **Nothing is uploaded.** The only network access is downloading presets from `raw.githubusercontent.com/Sqooky/OptimizationLock` when you choose one; they're validated as `gameinfo.gi` / `video.txt` before use.

## Sharing results

Report exports exclude raw logs, backups, config contents and absolute replay paths, but include your config names and notes, so review those first. A raw workspace can contain account identifiers, local paths and personal configs. Share the ZIP, not the folder.
