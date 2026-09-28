# Contributing

Bug reports should include the command, steps to reproduce, relevant versions and a short error excerpt. A report ZIP can help; avoid uploading an entire workspace, which may contain account identifiers, local paths and user configs.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -v
ruff check src tests research
python -m build
dpl --workspace /tmp/dpl-dev          # the app, with a throwaway workspace
```

Tests use temporary workspaces and fake game, Steam and console fixtures; they do not need Steam or a game installation. The app page is `src/deadlock_perf_lab/assets/app.html` (no build step, no external assets); its server is `gui.py`. Check changes to it in a browser at desktop and phone widths. See [architecture](docs/ARCHITECTURE.md) for module responsibilities and the saved-data layout.

## Pull requests

Explain the problem, resulting behavior and relevant checks. Changes to capture or analysis should preserve the [measurement rules](docs/METHODOLOGY.md). File-changing paths need failure and restoration tests. Keep runtime dependencies minimal.

New profiles need a source, snapshot date, license and known tradeoffs. Retain attribution when copying configs, and support performance claims with repeated measurements. Do not commit raw experiments, game binaries or replay files. Contributions use this project's GPL-3.0-only license.

## Releases

1. Update the version in `pyproject.toml` and `src/deadlock_perf_lab/__init__.py`, and date the changelog entry.
2. Run the tests, lint and build commands above. Install the wheel into a fresh venv outside the checkout; check `dpl --version`, `dpl profiles`, `dpl demo` and the app.
3. Walk through the app's setup, benchmark and results tabs. Check report sorting, capture selection, exports and narrow-screen layout. Keep synthetic previews labelled. Record any live smoke tests and their limits in the changelog separately from automated tests.
4. Inspect the distribution contents for package assets, licenses and accidentally included local data.
5. Push and require CI to pass, then push a `vX.Y.Z` tag on that commit. The release workflow checks the tag matches the version, builds the wheel, sdist and `dpl.pyz`, and publishes a preview GitHub release with checksums.
