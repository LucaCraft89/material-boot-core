"""The installer draws what a part reports through the one view (progress.py): steps with their time, details only with -v, nothing but errors with -q, a log of
everything, and the --progress json stream unchanged."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_installer import Base  # noqa: E402

EVENTS = [
    {"event": "step", "text": "Rendering the theme"},
    {"event": "detail", "text": "scene 3 of 112"},
    {"event": "step", "text": "Rebuilding the initramfs"},
    {"event": "detail", "text": "image 2 of 5"},
    {"event": "warn", "text": "one image is a rescue image: skipped"},
    {"event": "step_end"},
]


class InstallView(Base):
    def setUp(self):
        super().setUp()
        self.part("alpha", install={"default": True}, progress=EVENTS)

    def log_text(self):
        return (self.rootdir / "var/log/material-boot/install.log").read_text()

    def test_the_default_shows_steps_with_their_time_and_not_the_details(self):
        rc, out = self.run_cli("--yes")
        self.assertEqual(rc, 0, out)
        self.assertIn("Rendering the theme", out)
        self.assertIn("Rebuilding the initramfs", out)
        self.assertRegex(out, r"(✓|ok) Rendering the theme \(")  # a terminal without UTF-8 gets `ok`
        self.assertIn("one image is a rescue image", out)
        self.assertNotIn("scene 3 of 112", out)

    def test_v_shows_the_details(self):
        rc, out = self.run_cli("--yes", "-v")
        self.assertEqual(rc, 0, out)
        self.assertIn("scene 3 of 112", out)
        self.assertIn("image 2 of 5", out)

    def test_q_keeps_the_warning_and_the_result_only(self):
        rc, out = self.run_cli("--yes", "-q")
        self.assertEqual(rc, 0, out)
        self.assertIn("one image is a rescue image", out)
        self.assertNotIn("Rendering the theme", out)
        self.assertNotIn("== Alpha", out)
        self.assertIn("Installed: core, alpha.", out)

    def test_the_log_has_everything_whatever_was_shown(self):
        self.run_cli("--yes", "-q")
        logged = self.log_text()
        for words in ("Rendering the theme", "scene 3 of 112", "image 2 of 5", "one image is a rescue image"):
            self.assertIn(words, logged)

    def test_a_dry_run_writes_no_log(self):
        self.run_cli("--dry-run")
        self.assertFalse((self.rootdir / "var/log/material-boot").exists())

    def test_the_json_stream_is_unchanged_and_the_view_prints_nothing_else(self):
        import io
        from contextlib import redirect_stdout

        from material_boot import cli

        buf = io.StringIO()
        import sys as _sys
        from unittest import mock

        with redirect_stdout(io.StringIO()) as visible, mock.patch.object(_sys, "__stdout__", buf):
            rc = cli.main(
                [
                    "core",
                    "install",
                    "--bundle",
                    str(self.bundle),
                    "--root",
                    str(self.rootdir),
                    "--progress",
                    "json",
                    "--yes",
                ]
            )
        self.assertEqual(rc, 0)
        events = [json.loads(x) for x in buf.getvalue().splitlines() if x.strip()]
        steps = [e for e in events if e.get("part") == "alpha" and e["event"] == "step"]
        self.assertEqual([e["text"] for e in steps], ["Rendering the theme", "Rebuilding the initramfs"])
        self.assertTrue(any(e["event"] == "detail" and e["text"] == "image 2 of 5" for e in events))
        self.assertEqual(visible.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
