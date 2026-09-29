import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from deadlock_perf_lab.runner import interruptible
from deadlock_perf_lab.storage import LabError, read_json
from deadlock_perf_lab.system import detect_conditions, doctor, find_replays, parse_vdf, steam_launch_options, vdf_get
from deadlock_perf_lab.workspace import default_workspace, ensure_workspace, save_settings

APPS = '''"UserLocalConfigStore"
{
    "Software" { "Valve" { "Steam" { "apps" {
        "1422450" { "LastPlayed" "1" "LaunchOptions" "%s" }
    } } } }
}
'''


def fake_steam(home: Path, launch: str | None = None) -> Path:
    steam = home / ".local/share/Steam"
    citadel = steam / "steamapps/common/Deadlock/game/citadel"
    (citadel / "cfg").mkdir(parents=True)
    (citadel / "replays/old").mkdir(parents=True)
    (citadel / "gameinfo.gi").write_text("GameInfo { ConVars { fps_max 400 } }")
    (citadel / "cfg/video.txt").write_text('"config"\n{\n "setting.defaultres" "1920"\n "setting.defaultresheight" "1080"\n'
                                           ' "setting.fullscreen" "0"\n "setting.nowindowborder" "1"\n}\n')
    (citadel / "replays/one.dem").write_bytes(b"1")
    (citadel / "replays/old/two.dem").write_bytes(b"2")
    (steam / "config").mkdir(parents=True)
    (steam / "config/config.vdf").write_text('"InstallConfigStore" { "Software" { "Valve" { "Steam" { "CompatToolMapping" {'
                                             ' "0" { "name" "proton_9" } } } } } }')
    if launch is not None:
        (steam / "userdata/42/config").mkdir(parents=True)
        (steam / "userdata/42/config/localconfig.vdf").write_text(APPS % launch.replace('"', '\\"'))
    return citadel.parent.parent


class SteamDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        patcher = patch.dict(os.environ, {"HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "DPL_WORKSPACE", "DEADLOCK_INSTALL_DIR"):
            os.environ.pop(key, None)  # Restored when the patch.dict above stops.

    def test_vdf_escapes_nesting_comments_and_case(self):
        data = parse_vdf('"Root" { // c { }\n "Key" "a \\"b\\" \\\\ c" "Child" { "x" "1" } [$WIN32] "y" "2" }')
        self.assertEqual(vdf_get(data, "root", "KEY"), 'a "b" \\ c')
        self.assertEqual(vdf_get(data, "ROOT", "child", "x"), "1")
        self.assertEqual(vdf_get(data, "root", "y"), "2")
        self.assertIsNone(vdf_get(data, "root", "missing", "x"))

    def test_launch_options_detection_is_advisory(self):
        fake_steam(self.home)
        workspace = self.home / "ws"
        self.assertIsNone(steam_launch_options())
        check = next(c for c in doctor(None, workspace) if c["check"] == "Steam launch options")
        self.assertFalse(check["ok"])
        self.assertFalse(check["required"])

    def test_launch_options_match_this_workspace(self):
        workspace = self.home / "my ws"
        fake_steam(self.home, f"env MANGOHUD=1 MANGOHUD_CONFIGFILE='{workspace}/capture.conf' %command% -novid")
        self.assertEqual(len(steam_launch_options()), 1)
        check = next(c for c in doctor(None, workspace) if c["check"] == "Steam launch options")
        self.assertTrue(check["ok"])
        other = next(c for c in doctor(None, self.home / "elsewhere") if c["check"] == "Steam launch options")
        self.assertIn("different workspace", other["detail"])

    def test_conditions_and_replays_detected(self):
        install = fake_steam(self.home)
        self.assertEqual(detect_conditions(install), {"resolution": "1920x1080", "display_mode": "Borderless window",
                                                      "proton_version": "proton_9"})
        self.assertEqual(sorted(find_replays(install)), ["replays/old/two.dem", "replays/one.dem"])
        self.assertEqual(find_replays(None), [])
        self.assertEqual(detect_conditions(None), {"proton_version": "proton_9"})


class WorkspaceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_default_workspace_order(self):
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.root)
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data")}):
            os.environ.pop("DPL_WORKSPACE", None)
            self.assertEqual(default_workspace(), self.root / "data/deadlock-performance-lab")
            (self.root / ".lab").mkdir()
            (self.root / ".lab/lab.json").write_text("{}")
            self.assertEqual(default_workspace(), Path(".lab"))
            with patch.dict(os.environ, {"DPL_WORKSPACE": str(self.root / "explicit")}):
                self.assertEqual(default_workspace(), self.root / "explicit")

    def test_save_settings_validates_and_keeps_game_settings_optional(self):
        install = fake_steam(self.root)
        workspace = self.root / "ws"
        with patch("deadlock_perf_lab.workspace.discover_install", return_value=None):
            config = ensure_workspace(workspace)
        self.assertEqual(config["scenario"]["player"], "1")
        self.assertEqual(set(config["conditions"].values()), {""})
        with self.assertRaisesRegex(LabError, "Not a Deadlock install"):
            save_settings(workspace, {"install": str(self.root)})
        with self.assertRaisesRegex(LabError, "Replay not found"):
            save_settings(workspace, {"install": str(install), "scenario": {"replay": "replays/missing.dem"}})
        with self.assertRaisesRegex(LabError, "quotes"):
            save_settings(workspace, {"scenario": {"player": 'a"; quit'}})
        with self.assertRaisesRegex(LabError, "between"):
            save_settings(workspace, {"scenario": {"budget_fps": "0"}})
        config = save_settings(workspace, {
            "install": str(install), "scenario": {"replay": "replays/one.dem", "tick": "1234", "budget_fps": "165"},
            "conditions": {"resolution": " 1920x1080 ", "graphics_preset": "", "proton_version": "9",
                           "display_mode": "Fullscreen"}})
        self.assertEqual(config["scenario"]["tick"], 1234)
        self.assertEqual(config["scenario"]["budget_fps"], 165)
        self.assertEqual(config["conditions"]["resolution"], "1920x1080")
        self.assertEqual(config["conditions"]["graphics_preset"], "")
        self.assertEqual(read_json(workspace / "lab.json"), config)

    def test_interruptible_is_harmless_off_the_main_thread(self):
        errors = []

        def work():
            try:
                with interruptible():
                    pass
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        thread = threading.Thread(target=work)
        thread.start()
        thread.join()
        self.assertEqual(errors, [])
