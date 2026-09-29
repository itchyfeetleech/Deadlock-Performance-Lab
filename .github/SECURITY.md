# Security

Report vulnerabilities through GitHub's private vulnerability reporting if enabled. Otherwise open a minimal issue asking for a private contact, without exploit details or private captures.

The tool runs as your user and temporarily writes game config files. Its VConsole connection uses `127.0.0.1:29000`; do not expose that port through a firewall or tunnel. Automated sessions use local replays or bots with `-insecure`.

The app listens only on `127.0.0.1`. Each launch creates a secret that the opened link turns into a `SameSite=Strict` cookie, so other websites and other users' browsers can't drive it. Don't expose its port through a tunnel or proxy. The app does not upload data. It downloads files from `raw.githubusercontent.com/Sqooky/OptimizationLock` only when you choose a preset, and validates them as `gameinfo.gi`/`video.txt` before use; preview a config's changes before benchmarking it. Report exports exclude raw logs, backups, profile contents and absolute replay paths, but include your labels and notes. Review those before sharing. Raw workspaces may contain account identifiers, local paths and personal configs.
