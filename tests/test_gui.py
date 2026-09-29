import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from deadlock_perf_lab.cli import main
from deadlock_perf_lab.gui import App, Server, install_shortcut
from deadlock_perf_lab.planning import make_plan
from deadlock_perf_lab.storage import read_json
from deadlock_perf_lab.workspace import initialize


class GuiServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {"HOME": str(self.root), "XDG_DATA_HOME": str(self.root / "data"),
                                      "XDG_CACHE_HOME": str(self.root / "cache")})
        env.start()
        self.addCleanup(env.stop)
        discover = patch("deadlock_perf_lab.workspace.discover_install", return_value=None)
        discover.start()
        self.addCleanup(discover.stop)
        for name in ("deadlock_perf_lab.gui.discover_install",):
            p = patch(name, return_value=None)
            p.start()
            self.addCleanup(p.stop)
        self.workspace = self.root / "ws"
        initialize(self.workspace)
        self.server = Server(App(self.workspace))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.host = f"127.0.0.1:{self.server.port}"
        self.cookie = f"{self.server.cookie_name}={self.server.token}"

    def request(self, method, path, body=None, *, cookie=True, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=20)
        all_headers = {"Host": self.host}
        if cookie:
            all_headers["Cookie"] = self.cookie
        if method == "POST":
            all_headers.update({"X-DPL": "1", "Content-Type": "application/json"})
        all_headers.update(headers or {})
        connection.request(method, path, json.dumps(body or {}) if method == "POST" else None, all_headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data, response

    def api(self, method, path, body=None):
        status, data, _ = self.request(method, path, body)
        return status, json.loads(data)

    def test_access_requires_token_cookie_host_and_header(self):
        self.assertEqual(self.request("GET", "/api/state", cookie=False)[0], 403)
        self.assertEqual(self.request("GET", "/?token=wrong", cookie=False)[0], 403)
        status, _, response = self.request("GET", f"/?token={self.server.token}", cookie=False)
        self.assertEqual(status, 303)
        self.assertIn("SameSite=Strict", response.getheader("Set-Cookie"))
        self.assertIn("HttpOnly", response.getheader("Set-Cookie"))
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/demo", headers={"X-DPL": "0"})[0], 403)
        self.assertEqual(self.request("POST", "/api/demo", headers={"Origin": "https://evil.example"})[0], 403)
        status, page, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Deadlock Performance Lab", page)
        self.assertEqual(self.request("GET", "/api/ping", cookie=False)[0], 200)

    def test_state_demo_report_export_and_path_safety(self):
        status, state = self.api("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["workspace"], str(self.workspace.resolve()))
        self.assertFalse(state["ready"]["scene"])
        self.assertEqual(state["benchmark"]["rounds"], 3)
        self.assertEqual(state["benchmark"]["sample_s"], 30)
        self.assertEqual(state["profiles"], [])  # nothing bundled; configs are the user's own
        status, demo = self.api("POST", "/api/demo")
        self.assertEqual(status, 200, demo)
        status, page, _ = self.request("GET", f"/report/{demo['session']}/")
        self.assertEqual(status, 200)
        self.assertIn(b"DEMO DATA", page)
        status, detail = self.api("GET", f"/api/session/{demo['session']}")
        self.assertEqual(detail["runs"][0]["notes"], [])
        self.assertNotIn("reviewable", detail["runs"][0])
        status, ranking = self.api("GET", f"/api/session/{demo['session']}/ranking")
        self.assertNotIn("verdict", ranking["rows"][0])
        self.assertIsNotNone(ranking["rows"][0]["ci"])
        status, archive, response = self.request("GET", f"/export/{demo['session']}.zip")
        self.assertEqual(response.getheader("Content-Type"), "application/zip")
        self.assertEqual(len(zipfile.ZipFile(io.BytesIO(archive)).namelist()), 4)
        status, state = self.api("GET", "/api/state")
        self.assertIsNone(state["running"])
        self.assertEqual(state["sessions"][0]["status"]["state"], "complete")
        self.assertEqual(self.api("GET", "/api/session/..%2F..%2Fetc")[0], 400)
        self.assertEqual(self.request("GET", "/report/../../etc/")[0], 404)

    def test_actions_validate_input(self):
        status, result = self.api("POST", "/api/benchmark", {"cases": []})
        self.assertEqual(status, 400)
        self.assertIn("Pick at least one", result["error"])
        status, result = self.api("POST", "/api/benchmark", {"cases": ["cfg-anything"], "rounds": 1, "sample_s": 5})
        self.assertEqual(status, 400)
        self.assertIn("Not ready yet", result["error"])
        status, result = self.api("POST", "/api/settings", {"conditions": {"resolution": "1280x720"}})
        self.assertEqual(result["config"]["conditions"]["resolution"], "1280x720")
        self.assertEqual(self.api("POST", "/api/cancel", {"session": "nope"})[0], 400)

    def test_started_session_runs_in_background_and_reports_progress(self):
        session, _ = make_plan(self.workspace, ["example-shadows-off"], 2, 47, demo=True)
        status, result = self.api("POST", "/api/start", {"session": session.name})
        self.assertEqual(status, 200, result)
        self.assertEqual(self.api("POST", "/api/start", {"session": session.name})[0], 400)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            _, detail = self.api("GET", f"/api/session/{session.name}")
            if detail["status"]["state"] == "complete" and not detail["alive"] and not detail["starting"]:
                break
            time.sleep(.2)
        self.assertEqual(detail["status"]["state"], "complete", (session / "runner.log").read_text())
        self.assertEqual(len(detail["runs"]), 6)
        self.assertFalse((session / "runner.json").exists())
        self.assertTrue(detail["events"])
        self.assertIsNone(self.api("GET", "/api/state")[1]["running"])

    def test_shortcut_points_at_this_workspace(self):
        entry = install_shortcut(self.workspace)
        text = entry.read_text()
        self.assertIn("Name=Deadlock Performance Lab", text)
        self.assertIn(str(self.workspace.resolve()), text)
        self.assertTrue(text.rstrip().endswith("Categories=Game;Utility;"))
        self.assertTrue((self.root / "data/icons/hicolor/scalable/apps/deadlock-performance-lab.svg").is_file())

    def test_plain_dpl_opens_the_app(self):
        with patch("deadlock_perf_lab.gui.serve", return_value=0) as serve:
            self.assertEqual(main(["--workspace", str(self.workspace)]), 0)
        serve.assert_called_once()
        self.assertEqual(serve.call_args.args[0], self.workspace.resolve())
        self.assertEqual(read_json(self.workspace / "lab.json")["schema"], 1)
