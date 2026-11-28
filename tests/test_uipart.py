"""The editor's own part (material_boot/uipart.py): when it is on by default, and what it installs and removes."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from material_boot import uipart  # noqa: E402


def ctx(root, source=None, how="source"):
    return SimpleNamespace(root=str(root), source=source, how=how, dry_run=False)


class Graphical(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_session_in_the_environment_counts(self):
        for env in ({"DISPLAY": ":0"}, {"WAYLAND_DISPLAY": "wayland-0"}, {"XDG_SESSION_TYPE": "wayland"}):
            self.assertTrue(uipart.graphical(env, self.root), env)

    def test_a_tty_session_is_not_graphical(self):
        self.assertFalse(uipart.graphical({"XDG_SESSION_TYPE": "tty"}, self.root))
        self.assertFalse(uipart.graphical({}, self.root))

    def test_sudo_strips_the_environment_so_the_machine_is_looked_at(self):
        d = self.root / "etc/systemd/system"
        d.mkdir(parents=True)
        (d / "default.target").symlink_to("/usr/lib/systemd/system/graphical.target")
        self.assertTrue(uipart.graphical({}, self.root))

    def test_installed_sessions_count_too(self):
        d = self.root / "usr/share/wayland-sessions"
        d.mkdir(parents=True)
        self.assertFalse(uipart.graphical({}, self.root))
        (d / "gnome.desktop").write_text("[Desktop Entry]\n")
        self.assertTrue(uipart.graphical({}, self.root))

    def test_on_by_default_only_on_a_desktop_and_a_normal_layout(self):
        self.assertTrue(uipart.part(layout="normal", env={"DISPLAY": ":0"}).default)
        self.assertFalse(uipart.part(layout="normal", env={}, root=self.root).default)
        self.assertFalse(uipart.part(layout="immutable", env={"DISPLAY": ":0"}).default)

    def test_it_needs_the_core_and_the_normal_layout(self):
        p = uipart.part(env={})
        self.assertEqual((p.needs, p.layouts), (["core"], ["normal"]))


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.root, self.src = t / "root", t / "bundle"
        shutil.copytree(ROOT / "packaging/ui", self.src / "ui")

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_puts_the_three_files_where_the_system_looks_for_them(self):
        r = uipart.hook_install(ctx(self.root, self.src))
        self.assertTrue(r["changed"])
        helper = self.root / "usr/libexec/material-boot-ui-helper"
        self.assertTrue(helper.is_file() and helper.stat().st_mode & 0o111)
        self.assertTrue((self.root / "usr/share/polkit-1/actions/org.material-boot.ui.policy").is_file())
        self.assertIn("Exec=material-boot ui", (self.root / "usr/share/applications/material-boot.desktop").read_text())
        self.assertEqual(uipart.hook_verify(ctx(self.root, self.src)), [])
        self.assertTrue(uipart.hook_detect(ctx(self.root))["found"])

    def test_the_policy_names_the_helper_it_installs(self):
        uipart.hook_install(ctx(self.root, self.src))
        policy = (self.root / "usr/share/polkit-1/actions/org.material-boot.ui.policy").read_text()
        self.assertIn("/usr/libexec/material-boot-ui-helper", policy)

    def test_nothing_installed_means_not_found_and_verify_says_what_is_missing(self):
        self.assertEqual(uipart.hook_detect(ctx(self.root)), {"found": False})
        self.assertEqual(len(uipart.hook_verify(ctx(self.root))), 3)

    def test_uninstall_removes_what_install_put(self):
        uipart.hook_install(ctx(self.root, self.src))
        uipart.hook_uninstall(ctx(self.root))
        self.assertEqual(len(uipart.hook_verify(ctx(self.root))), 3)

    def test_a_package_install_leaves_the_files_to_the_package_manager(self):
        uipart.hook_install(ctx(self.root, self.src))
        r = uipart.hook_uninstall(ctx(self.root, how="package"))
        self.assertFalse(r["changed"])
        self.assertEqual(uipart.hook_verify(ctx(self.root)), [])
        self.assertFalse(uipart.hook_install(ctx(self.root, self.src, how="package"))["changed"])


if __name__ == "__main__":
    unittest.main()
