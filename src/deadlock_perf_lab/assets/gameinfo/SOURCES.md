# Community snapshot provenance

Source: [Sqooky/OptimizationLock](https://github.com/Sqooky/OptimizationLock).
The existing research workspace fetched these files on 2026-09-04.
Upstream main observed during release preparation: `3167965cae607c24fd04c1df021178f1536c58a3`.
The upstream SHA-256 identifies the bytes as fetched; this is not a claim that every file is current.

License: GPL-3.0-only; the accompanying LICENSE reproduces the upstream license text.
Credit belongs to Sqooky, Boot, Kaizuchaneru and the contributors acknowledged by OptimizationLock.

| Bundled file | Upstream path | Upstream bytes | Upstream SHA-256 |
|---|---|---:|---|
| `sqooky-default.gi` | `Sqooky's .gi/gameinfo.gi` | 86824 | `946a430112370dafcbeb8c2b72374bb68c1fe7e0e7d2e5c7238a1bd2002a6067` |
| `sqooky-maxfps-test.gi` | `test_cfg/gameinfo.gi` | 88208 | `362c7c577c37f821cf9f484f4505c7a21afecc014e3064e77798ede620189d55` |
| `boot-maxfps.gi` | `boot's maxium fps config/gameinfo.gi` | 71537 | `6dbc82150afe2ec409646025b2437b093aab18d852a7329b80aded2ffb7cf0e5` |
| `kaizu-minspec.gi` | `kaizuchanerus minimum spec/gameinfo.gi` | 52281 | `16e9e739b90941543f2fabeea8161fd15327df5f16d812377fbd2bf4e75a98a4` |

## Modifications

On 2026-09-06 this project removed one credit comment line (for a video by Dacooder) from `sqooky-default.gi`,
`sqooky-maxfps-test.gi` and `boot-maxfps.gi` (twice in `boot-maxfps.gi`). No settings were changed.
`kaizu-minspec.gi` is unmodified. SHA-256 of the bundled bytes:

| Bundled file | Bytes | SHA-256 |
|---|---:|---|
| `sqooky-default.gi` | 86754 | `aa9bbcf2921a80e8e76ae630cb9e7ee2047dd3f3402beb4b5857c487eeefc42f` |
| `sqooky-maxfps-test.gi` | 88138 | `ef078ee96e5733550950a5082356f8b2e1560b8c3940e4c036d49c46d3e39365` |
| `boot-maxfps.gi` | 71371 | `caa752c598cb8b3a9f63530bd8ed2cb9de93113afd498c14ec6f083026a801c6` |
| `kaizu-minspec.gi` | 52281 | `16e9e739b90941543f2fabeea8161fd15327df5f16d812377fbd2bf4e75a98a4` |

These are whole-file experimental replacements, not single-cvar patches.
Boot is described upstream as unmaintained. The test and minimum-spec variants have substantial compatibility/visual tradeoffs.
The package never auto-downloads, auto-updates or persistently installs these files.
Review the actual diff against your current installation before use. New game builds can invalidate assumptions.
