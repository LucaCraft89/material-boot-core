"""How the editor finds what it needs outside the core: the shared data, and the GRUB part's modules in each way GRUB can be installed."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from material_boot.ui import paths  # noqa: E402


class GrubModules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        (self.t / "plugins").mkdir()
        env = {"MATERIAL_PLUGIN_PATH": str(self.t / "plugins")}
        env.pop("MATERIAL_GRUB_MODULES", None)
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("MATERIAL_GRUB_MODULES", None)

    def tearDown(self):
        self.tmp.cleanup()

    def part(self, entry):
        (self.t / "plugins/grub.json").write_text(
            json.dumps(
                {"manifest": 2, "name": "grub", "title": "GRUB", "version": "1.2.0", "core_api": 2, "entry": str(entry)}
            )
        )

    def tree(self, where):
        d = self.t / where
        d.mkdir(parents=True)
        (d / "cmd_scenes.py").write_text("")
        return d

    def test_without_the_part_there_are_no_modules(self):
        self.assertIsNone(paths.grub_modules())

    def test_a_package_install(self):  # entry: .../material-grub-src/install/part_grub.py, tools in install/bin
        bin_ = self.tree("share/material-grub-src/install/bin")
        (bin_.parent / "part_grub.py").write_text("def main(a, c):\n    return 0\n")
        self.part(bin_.parent / "part_grub.py")
        self.assertEqual(paths.grub_modules(), bin_.resolve())

    def test_a_bundle_install(self):  # entry: .../material-grub/bin/part_grub.py, the tools beside it
        bin_ = self.tree("share/material-grub/bin")
        (bin_ / "part_grub.py").write_text("def main(a, c):\n    return 0\n")
        self.part(bin_ / "part_grub.py")
        self.assertEqual(paths.grub_modules(), bin_.resolve())

    def test_a_checkout(self):  # entry: <repo>/install/part_grub.py, tools in <repo>/install/bin
        bin_ = self.tree("grub/install/bin")
        (bin_.parent / "part_grub.py").write_text("def main(a, c):\n    return 0\n")
        self.part(bin_.parent / "part_grub.py")
        self.assertEqual(paths.grub_modules(), bin_.resolve())

    def test_a_part_that_cannot_be_used_gives_nothing(self):
        bin_ = self.tree("share/material-grub/bin")
        self.part(bin_ / "missing.py")
        self.assertIsNone(paths.grub_modules())

    def test_the_environment_wins(self):
        bin_ = self.tree("elsewhere")
        with mock.patch.dict(os.environ, {"MATERIAL_GRUB_MODULES": str(bin_)}):
            self.assertEqual(paths.grub_modules(), bin_)


class PartInfo(unittest.TestCase):
    """What the editor tells its page about the parts: the page shows GRUB's pages (and the menu preview) only when GRUB is there."""

    def test_installed_or_not(self):
        from material_boot.ui import state

        with tempfile.TemporaryDirectory() as t:
            with mock.patch.dict(os.environ, {"MATERIAL_PLUGIN_PATH": t}):
                self.assertFalse(state.part_info("grub")["installed"])
                (Path(t) / "entry.py").write_text("def main(a, c):\n    return 0\n")
                (Path(t) / "grub.json").write_text(
                    json.dumps(
                        {
                            "manifest": 2,
                            "name": "grub",
                            "title": "GRUB",
                            "version": "1.2.0",
                            "core_api": 2,
                            "entry": str(Path(t) / "entry.py"),
                        }
                    )
                )
                info = state.part_info("grub")
                self.assertEqual((info["installed"], info["version"]), (True, "1.2.0"))
                self.assertFalse(state.part_info("plymouth")["installed"])


if __name__ == "__main__":
    unittest.main()
