import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from deadlock_perf_lab import configs
from deadlock_perf_lab.cli import main
from deadlock_perf_lab.gui import App
from deadlock_perf_lab.planning import make_plan
from deadlock_perf_lab.profiles import add_profile, catalog
from deadlock_perf_lab.storage import LabError, read_json, write_json
from deadlock_perf_lab.workspace import initialize

CURRENT_GI = '''"GameInfo"
{
    game "citadel"
    PGIVersion "AAAA"
    ConVars
    {
        rate { min "1" max "2" }
        fps_max    "400"
        r_shadows  "1"
    }
}
'''
PRESET_GI = '''"GameInfo"
{
    game "citadel"
    PGIVersion "BBBB"
    DistanceField "0"
    ConVars
    {
        // -------- Performance Config! Example -------- \\\\
        // IF YOU ARE MODIFYING A COMMAND AND NOTHING IS CHANGING SEE BELOW
        //this_is_an_example_comment "true"
        // ================ Shadows ================
        r_shadows                "0"    // Disables dynamic shadows.     [def: "1"]
        r_citadel_shadow_quality "0"    // Shadow quality (0 = lowest).  [def: "2"]
        r_shadows                "0"    // duplicate definition
        // --- 3. Particles ---
        // r_particle_timescale  "1"    // Speeds up particles. [def: "1"]
        // These commands both affect fov but do so in different ways.
        // ================ Convars You Shouldn't/Can't Mess With ================
        ai_disable "1"
        // --------------------------------- END OF CONFIG Example ------------------------------- \\\\
        fps_max "400"
    }
}
'''
VIDEO = '''"video.cfg"
{
	"Version"		"20"
	"VendorID"		"4098"
	"DeviceID"		"30032"
	"setting.defaultres"		"2560"
	"setting.mat_vsync"		"1"
	"setting.r_citadel_ssao_quality"		"2"
}
'''
PRESET_VIDEO = '''"video.cfg"
{
	"Version"		"19"
	"VendorID"		""
	"DeviceID"		""
	"setting.defaultres"		"1920"
	"setting.mat_vsync"		"0"
	"setting.r_citadel_ssao_quality"		"0"
	"setting.r_citadel_ssao_quality"		"0"
}
'''


def fake_fetch(workspace, path, *, refresh=False):
    text = PRESET_VIDEO if path.endswith("video.txt") else PRESET_GI
    return text, {"sha256": "x", "fetched_at": "2026-09-28T00:00:00+00:00", "source": "https://github.com/x", "url": "u"}


class ConfigFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "Deadlock"
        (self.install / "game/citadel/cfg").mkdir(parents=True)
        (self.install / "game/citadel/gameinfo.gi").write_text(CURRENT_GI)
        (self.install / "game/citadel/cfg/video.txt").write_text(VIDEO)
        (self.install / "game/citadel/replay.dem").write_bytes(b"replay")
        self.workspace = self.root / "ws"
        initialize(self.workspace, str(self.install), "replay.dem")
        config = read_json(self.workspace / "lab.json")
        config["conditions"].update(resolution="2560x1440", graphics_preset="High", proton_version="9",
                                    display_mode="Fullscreen")
        write_json(self.workspace / "lab.json", config)
        fetch = patch("deadlock_perf_lab.configs.fetch", side_effect=fake_fetch)
        fetch.start()
        self.addCleanup(fetch.stop)


class ConfigEngineTests(ConfigFixture):
    def test_catalog_uses_sections_descriptions_defaults_and_skips_documentation(self):
        groups = {g["name"]: g["settings"] for g in configs.catalog_from(PRESET_GI)}
        self.assertEqual(list(groups), ["Shadows", "Particles"])
        shadows = {s["name"]: s for s in groups["Shadows"]}
        self.assertEqual(shadows["r_shadows"], {"name": "r_shadows", "value": "0", "default": "1",
                                                "description": "Disables dynamic shadows.", "optional": False})
        self.assertTrue(groups["Particles"][0]["optional"])  # commented out upstream
        self.assertNotIn("ai_disable", str(groups))  # "shouldn't mess with" section
        self.assertNotIn("this_is_an_example_comment", str(groups))

    def test_set_convars_replaces_every_definition_and_appends_missing(self):
        text = configs.set_convars(PRESET_GI, {"R_SHADOWS": "1", "r_farz": "6000"})
        self.assertEqual(text.count('r_shadows                "1"'), 2)
        self.assertEqual(configs.convars(text)["r_farz"], "6000")
        self.assertEqual(configs.convars(text)["fps_max"], "400")
        inline = configs.set_convars('GameInfo { ConVars { a 1 } }', {"b": "2"})
        self.assertEqual(configs.convars(inline), {"a": "1", "b": "2"})
        for bad in ({"r_shadows": 'x" ; quit'}, {"bind": "x"}, {"1bad": "1"}):
            with self.subTest(bad=bad), self.assertRaises(LabError):
                configs.set_convars(PRESET_GI, bad)

    def test_video_parse_edit_and_validation(self):
        self.assertEqual(configs.video_settings(PRESET_VIDEO)["setting.r_citadel_ssao_quality"], "0")
        text = configs.set_video(VIDEO, {"setting.mat_vsync": "0", "setting.new": "3"})
        self.assertEqual(configs.video_settings(text)["setting.mat_vsync"], "0")
        self.assertEqual(configs.video_settings(text)["setting.new"], "3")
        for bad in ("", '"video.cfg" { "a" "b" } extra', '"video.cfg" { "a" { } }', CURRENT_GI):
            with self.subTest(bad=bad[:20]), self.assertRaises(LabError):
                configs.validate_video(bad)

    def test_preset_config_is_frozen_keeps_your_device_and_display(self):
        profile = configs.build(self.workspace, {
            "name": "Lock + shadows", "gameinfo": {"source": "sqooky", "overrides": {"r_shadows": "1"}},
            "video": {"source": "liah", "overrides": {}, "keep_display": True}})
        self.assertEqual(profile["id"], "cfg-lock-shadows")
        self.assertEqual(profile["gameinfo"]["preset"], "sqooky")
        self.assertIn("DistanceField", profile["gameinfo"]["content"])  # whole file, frozen
        files = configs.materialize(profile, self.install)
        video = configs.video_settings(files["video"])
        self.assertEqual((video["VendorID"], video["DeviceID"], video["Version"]), ("4098", "30032", "20"))
        self.assertEqual((video["setting.defaultres"], video["setting.mat_vsync"]), ("2560", "1"))
        self.assertEqual(files["video_changes"], {"setting.r_citadel_ssao_quality": "0"})
        # Only settings that differ from your installed file are read back as changes.
        self.assertNotIn("r_shadows", files["cvars"])  # preset says 0, the override puts back your 1
        self.assertEqual(files["cvars"]["r_citadel_shadow_quality"], "0")
        self.assertTrue(any("different game version" in n for n in files["notes"]))
        self.assertTrue(any("whole gameinfo.gi" in n for n in files["notes"]))
        released = configs.materialize({**profile, "video": {**profile["video"], "keep_display": False}}, self.install)
        self.assertEqual(configs.video_settings(released["video"])["setting.defaultres"], "1920")

    def test_empty_or_identical_configs_are_refused(self):
        with self.assertRaisesRegex(LabError, "doesn't change anything"):
            configs.build(self.workspace, {"name": "Nothing", "gameinfo": {"source": "current", "overrides": {}}})
        same = configs.build(self.workspace, {"name": "Same", "gameinfo": {"source": "current", "overrides": {"fps_max": "400"}}})
        with self.assertRaisesRegex(LabError, "identical"):
            configs.materialize(same, self.install)

    def test_plan_freezes_the_exact_files_and_run_settings(self):
        add_profile(self.workspace, configs.build(self.workspace, {
            "name": "Shadows off", "gameinfo": {"source": "current", "overrides": {"r_shadows": "0"}}}))
        _, plan = make_plan(self.workspace, ["cfg-shadows-off"], 1, 1, fps_max=0, renderer="dx11")
        frozen = plan["profiles"]["cfg-shadows-off"]["materialized"]
        self.assertEqual(configs.convars(frozen["gameinfo"])["r_shadows"], "0")
        self.assertIsNone(frozen["video"])
        self.assertEqual(plan["context"]["scenario"]["fps_max"], 0)
        self.assertEqual(plan["context"]["scenario"]["launch_flags"], ["-dx11"])
        for kwargs in ({"fps_max": -1}, {"fps_max": True}, {"renderer": "opengl"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(LabError):
                make_plan(self.workspace, ["cfg-shadows-off"], 1, 1, **kwargs)

    def test_cli_saves_your_own_files_as_a_config(self):
        gi = self.root / "my.gi"
        gi.write_text(configs.set_convars(CURRENT_GI, {"r_shadows": "0"}))
        video = self.root / "video.txt"
        video.write_text(PRESET_VIDEO)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--workspace", str(self.workspace), "profile", "add", "mine",
                                   "--gameinfo", str(gi), "--video", str(video)]), 0)
        profile = catalog(self.workspace)["mine"]
        self.assertEqual(profile["kind"], "config")
        self.assertEqual(profile["gameinfo"]["filename"], "my.gi")
        self.assertIn("imported video.txt", profile["description"])

    def test_offline_fetch_uses_cache_or_explains(self):
        patch.stopall()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(LabError, "internet"):
                configs.fetch(self.workspace, "x.gi")
            directory = configs.cache_dir(self.workspace)
            directory.mkdir(parents=True)
            name = __import__("hashlib").sha256(b"x.gi").hexdigest()[:16]
            (directory / f"{name}.txt").write_text("cached")
            (directory / f"{name}.json").write_text('{"fetched_epoch": 0, "sha256": "s"}')
            text, meta = configs.fetch(self.workspace, "x.gi")
        self.assertEqual((text, meta["stale"]), ("cached", True))


class ConfigAppTests(ConfigFixture):
    """The app's config actions, against the same fixture."""

    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {"HOME": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        self.app = App(self.workspace)

    def test_sources_catalog_save_edit_preview_download_delete(self):
        current = self.app.config_source("gameinfo", "current")["settings"]
        self.assertEqual(current["r_shadows"], "1")
        self.assertEqual(self.app.config_source("gameinfo", "sqooky")["settings"]["r_shadows"], "0")
        catalog_ = self.app.config_catalog()
        self.assertEqual(catalog_["gameinfo"][0]["name"], "Shadows")
        self.assertIn("Display", [g["name"] for g in catalog_["video"]])
        imported = {"name": "Mine", "gameinfo": {"source": "file", "filename": "g.gi", "overrides": {"fps_max": "300"},
                                                 "content": configs.set_convars(CURRENT_GI, {"r_shadows": "0"})}}
        saved = self.app.save_config(imported)
        self.assertEqual(saved["id"], "cfg-mine")
        edit = self.app.saved_config("cfg-mine")
        self.assertNotIn("content", edit["gameinfo"])
        self.assertEqual(edit["gameinfo"]["base_settings"]["r_shadows"], "0")
        # Editing without re-sending the imported file keeps it; copies reuse it too.
        self.app.save_config({"id": "cfg-mine", "name": "Mine", "gameinfo": {"source": "file", "overrides": {}}})
        self.app.save_config({"name": "Mine copy", "gameinfo": {"source": "file", "copy_of": "cfg-mine", "overrides": {}}})
        for config_id in ("cfg-mine", "cfg-mine-copy"):
            self.assertEqual(configs.convars(self.app.config_file(config_id, "gameinfo.gi").decode())["r_shadows"], "0")
        shown = configs.preview(self.app.build_config(imported), self.install)
        self.assertIn('+        r_shadows  "0"', shown["gameinfo_diff"])
        self.assertEqual(shown["video_diff"], "")
        with self.assertRaisesRegex(LabError, "doesn't change video.txt"):
            self.app.config_file("cfg-mine", "video.txt")
        self.assertEqual(self.app.save_config({**imported})["id"], "cfg-mine-2")  # same name, new config
        self.app.delete_config({"id": "cfg-mine"})
        self.assertNotIn("cfg-mine", catalog(self.workspace))
        with self.assertRaises(LabError):
            self.app.delete_config({"id": "baseline"})
