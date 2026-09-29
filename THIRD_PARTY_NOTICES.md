# Third-party notices

## OptimizationLock presets

The app can download community `gameinfo.gi` and `video.txt` presets, and the cvar reference list, from [Sqooky/OptimizationLock](https://github.com/Sqooky/OptimizationLock), licensed GPL-3.0. Nothing from that repository is bundled or redistributed with this project. Files are fetched from GitHub only when you choose a preset, cached in your workspace, and frozen unchanged into configs you save. The app keeps your own `VendorID`, `DeviceID`, format version and (optionally) display settings when it combines a `video.txt` preset with your file, and applies the settings you tick on top.

Credit: Sqooky, Boot, Kaizuchaneru, Liah, Piggy and the many contributors acknowledged in the [upstream README](https://github.com/Sqooky/OptimizationLock/blob/main/README.md). The preset names and paths mirror OptimizationLock's own `gameinfo_updater.py`. Mentioning them does not imply endorsement of this tool or its measurements.

Application code is licensed GPL-3.0-only. Copyright © 2026 Deadlock Performance Lab contributors.

## Protocol and format references

The minimal VConsole implementation is new code based on the public Source 2 protocol structure. Reference: [theokyr/CS2RemoteConsole libvconsole](https://github.com/theokyr/CS2RemoteConsole).

MangoHud capture support follows its [logging source](https://github.com/flightlessmango/MangoHud/blob/master/src/logging.cpp) and [configuration reference](https://github.com/flightlessmango/MangoHud/blob/master/data/MangoHud.conf). MangoHud is a separately installed dependency and is not redistributed here.

## Names and game content

Deadlock and Steam are Valve products. This project is independent and unaffiliated. It includes no game executables, replay recordings, user account data, screenshots of gameplay or original game artwork. The report preview uses synthetic data and the project's own interface.
