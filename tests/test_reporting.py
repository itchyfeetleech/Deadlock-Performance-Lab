import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadlock_perf_lab.analysis import aggregate_metrics, analyze
from deadlock_perf_lab.capture import frame_distribution, read_mangohud
from deadlock_perf_lab.imports import import_capture
from deadlock_perf_lab.planning import make_plan
from deadlock_perf_lab.profiles import add_profile
from deadlock_perf_lab.report import generate_report, markdown_report, report_payload, treatment
from deadlock_perf_lab.runner import run_session
from deadlock_perf_lab.storage import fingerprint, read_json, write_json
from deadlock_perf_lab.workspace import initialize
from tests.helpers import mangohud


class ReportingTests(unittest.TestCase):
    def test_capture_means_do_not_weight_long_runs_more(self):
        records = [{"metrics": {"avg_fps": 100, "low_1_fps": 80, "samples": 1000}},
                   {"metrics": {"avg_fps": 200, "low_1_fps": 120, "samples": 10000}}]
        metrics = aggregate_metrics(records)
        self.assertEqual(metrics["avg_fps"], 150)
        self.assertEqual(metrics["low_1_fps"], 100)

    def test_missing_tail_measurement_is_not_partial_or_zero(self):
        records = [{"metrics": {"avg_fps": 100, "low_1_fps": 80}},
                   {"metrics": {"avg_fps": 100, "low_1_fps": None}}]
        self.assertIsNone(aggregate_metrics(records)["low_1_fps"])
        self.assertIsNone(aggregate_metrics([])["avg_fps"])

    def test_frame_distribution_spans_median_to_tail(self):
        frames = [5.0] * 9989 + [50.0] * 10 + [700.0]
        points = frame_distribution(frames)
        percentiles = [p for p, _ in points]
        self.assertEqual(percentiles[0], 0)
        self.assertEqual(percentiles[10], 90)
        self.assertEqual(percentiles[20], 99)
        self.assertEqual(percentiles[30], 99.9)
        self.assertEqual(percentiles[-1], 99.99)
        values = [v for _, v in points]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 5)
        self.assertEqual(values[20], 5)
        self.assertEqual(values[30], 50)
        self.assertAlmostEqual(values[-1], 50.065)  # interpolated towards the 700 ms stall

    def test_config_changes_are_named_without_file_contents(self):
        profile = {"kind": "config", "gameinfo": {"source": "current", "overrides": {"r_shadows": "0"}},
                   "materialized": {"gameinfo": "\"GameInfo\" { secret whole file }", "video": None,
                                    "cvars": {"r_shadows": "0", "r_farz": "6000"}, "video_changes": {},
                                    "notes": ["Replaces the whole gameinfo.gi."]}}
        result = treatment(profile)
        self.assertEqual(result["changes"], [["gameinfo.gi", "r_shadows", "0"], ["gameinfo.gi", "r_farz", "6000"]])
        self.assertEqual(result["notes"], ["Replaces the whole gameinfo.gi."])
        self.assertNotIn("secret", json.dumps(result))
        console = treatment({"kind": "autoexec", "content": 'fps_max "144"\n// note\nr_farz 6000 // far'})
        self.assertEqual(console["changes"], [["console", "fps_max", "144"], ["console", "r_farz", "6000"]])


class ReportPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        with patch("deadlock_perf_lab.workspace.discover_install", return_value=None):
            initialize(self.workspace)
        config = read_json(self.workspace / "lab.json")
        config["scenario"].update(sample_s=1, warmup_s=0, cooldown_s=0, settle_s=0)
        config["conditions"] = {"resolution": "1920x1080", "graphics": "test fixture", "notes": "test conditions"}
        write_json(self.workspace / "lab.json", config)

    def demo(self, cases=("example-shadows-off",), rounds=5):
        session, plan = make_plan(self.workspace, list(cases), rounds, 47, demo=True)
        with contextlib.redirect_stdout(io.StringIO()):
            run_session(self.workspace, session)
        return session, plan

    def test_payload_carries_percentiles_changes_and_schedule(self):
        session, plan = self.demo()
        result = report_payload(session)
        self.assertTrue(all(len(r["distribution"]) == 41 for r in result["runs"]))
        self.assertEqual(result["plan"]["schedule"], plan["schedule"])
        self.assertEqual(result["plan"]["rounds"], 5)
        comparison = result["comparisons"][0]
        self.assertEqual(comparison["treatment"]["changes"], [["gameinfo.gi", "r_shadows", "0"]])
        self.assertEqual(len(comparison["round_low_1_deltas_pct"]), len(comparison["paired_rounds"]))
        self.assertIsNotNone(comparison["low_1_ci95_pct"])
        self.assertNotIn("capture_metadata", json.dumps(result["runs"]))

    def test_older_results_get_percentiles_from_their_verified_capture(self):
        session, _ = self.demo(rounds=1)
        expected = {}
        for path in (session / "runs").glob("*/result.json"):
            record = read_json(path)
            expected[record["id"]] = record.pop("distribution")
            write_json(path, record)
        result = report_payload(session)
        self.assertEqual({r["id"]: r["distribution"] for r in result["runs"]}, expected)
        # A capture that no longer matches its recorded hash gets no curve.
        record = next(iter((session / "runs").glob("*/result.json")))
        capture = record.parent / "capture.csv"
        capture.write_text(capture.read_text() + "\n")
        runs = report_payload(session)["runs"]
        self.assertEqual(len(runs), len(expected) - 1)
        self.assertTrue(all("distribution" in r for r in runs))

    def test_interval_captures_have_no_low_interval(self):
        config = read_json(self.workspace / "lab.json")
        config["scenario"]["sample_s"] = 3
        write_json(self.workspace / "lab.json", config)
        add_profile(self.workspace, {"id": "treatment", "kind": "manual", "name": "Treatment", "description": "test"})
        session, plan = make_plan(self.workspace, ["treatment"], 3, 47, manual=True)
        for item in plan["schedule"]:
            source = mangohud(self.root / f"interval-{item['index']}.csv", [5.0 + item["index"] / 100] * 40, interval_ms=100)
            import_capture(session, source, item["case"], item["round"], interval_ms=100)
        self.assertEqual(len(read_json(next((session / "runs").glob("*/result.json")))["distribution"]), 41)
        comparison = analyze(session)["comparisons"][0]
        self.assertEqual(comparison["round_low_1_deltas_pct"], [None, None, None])
        self.assertIsNone(comparison["low_1_delta_pct"])
        self.assertIsNone(comparison["low_1_ci95_pct"])
        capture = read_mangohud(source, duration_s=3, interval_ms=100)
        self.assertEqual(len(frame_distribution(capture.frames)), 41)

    def test_template_markers_in_labels_are_not_expanded(self):
        session, plan = self.demo(rounds=1)
        plan["profiles"]["example-shadows-off"]["name"] = "__DATA__ and __FALLBACK__"
        plan["plan_sha256"] = fingerprint({k: v for k, v in plan.items() if k != "plan_sha256"})
        write_json(session / "plan.json", plan)
        page = generate_report(session).read_text()
        self.assertEqual(page.count('id="report-data"'), 1)
        self.assertIn("__DATA__ and __FALLBACK__", page)
        data = page.split('id="report-data">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(data)["comparisons"][0]["name"], "__DATA__ and __FALLBACK__")

    def test_markdown_ranks_configs_and_shows_low_change(self):
        session, _ = self.demo(cases=("example-shadows-off", "example-low-video"))
        text = markdown_report(report_payload(session))
        self.assertIn("1% low change", text)
        self.assertLess(text.index("Example: low video.txt"), text.index("Example: shadows off"))
