"""The help is made from one table (material_boot/help.py) and must not drift from what the commands accept: every option the installer accepts is documented, every
documented option is accepted, every example runs, and `--help` explains instead of doing."""

import ast
import contextlib
import io
import json
import os
import re
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from material_boot import cli, commands, help, installer  # noqa: E402

SAMPLE = {  # a value for each metavar, to try an option
    "PART[,PART]": "core",
    "PART": "core",
    "STYLE": "list",
    "dark|light": "dark",
    "#RRGGBB": "#7E57C2",
    "multi|single": "single",
    "json": "json",
    "DIR": "/tmp",
}


def run_main(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            rc = cli.main(argv)
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue()


class InstallerOptions(unittest.TestCase):
    def test_every_documented_option_is_accepted(self):
        for _title, options in help.INSTALL_GROUPS:
            for flags, meta, _summary in options:
                for flag in flags:
                    args = [flag] + ([SAMPLE[meta]] if meta else [])
                    _o, errors = installer.parse_args(args, [])
                    self.assertEqual(errors, [], f"{flag} is documented but not accepted")

    def test_every_option_the_installer_accepts_is_documented(self):
        tree = ast.parse((ROOT / "material_boot/installer.py").read_text())
        accepted = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "parse_args":
                accepted |= {
                    n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                }
            if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") in ("FLAG_ATTR", "LOOK_FLAG") for t in node.targets
            ):
                accepted |= {k.value for k in node.value.keys}
        accepted = {a for a in accepted if re.fullmatch(r"--?[a-z][a-z-]*", a)}
        self.assertTrue({"--with", "--dry-run", "--no-cookie", "-q"} <= accepted, accepted)
        self.assertEqual(
            accepted - help.documented_install_flags(), set(), "accepted by the installer but not documented"
        )
        self.assertEqual(
            help.documented_install_flags() - accepted, set(), "documented but the installer does not know it"
        )

    def test_the_install_help_lists_every_flag_and_the_parts_options(self):
        part = mock.Mock(options=[{"name": "res", "takes": "value", "summary": "resolution WxH"}])
        part.name = "grub"
        text = help.install_text([part])
        for flag in help.documented_install_flags():
            self.assertIn(flag, text)
        self.assertIn("--grub-res", text)
        self.assertIn("resolution WxH", text)

    def test_the_installer_prints_it_for_help(self):
        out = io.StringIO()
        rc = installer.main(["--help"], say=lambda t="": out.write(t + "\n"))
        self.assertEqual(rc, 0)
        self.assertIn("Which parts:", out.getvalue())
        self.assertIn("Examples:", out.getvalue())


class Examples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        env = {
            "MATERIAL_CONF": str(t / "mg.conf"),
            "MATERIAL_OVERRIDES": str(t / "etc/material-grub/overrides.json"),
            "MATERIAL_PLUGIN_PATH": str(t / "plugins"),
            "EDITOR": "true",
        }
        (t / "plugins").mkdir()
        (t / "stub.py").write_text("def main(argv, core):\n    return 0\n")
        for name in ("grub", "plymouth"):  # the parts the examples name: stand-ins whose apply does nothing
            (t / f"plugins/{name}.json").write_text(
                json.dumps(
                    {
                        "manifest": 2,
                        "name": name,
                        "title": name,
                        "version": "1.0.0",
                        "core_api": 2,
                        "entry": str(t / "stub.py"),
                        "commands": {"apply": "x"},
                    }
                )
            )
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def words(self, example):
        w = shlex.split(example)
        if w[0] == "sudo":
            w = w[1:]
        if w[0] == "./install.sh":
            w = ["material-boot", "core", "install", *w[1:]]
        assert w[0] == "material-boot", example
        return w[1:]

    def test_every_example_runs(self):
        seen = 0
        for example in help.all_examples():
            argv = self.words(example)
            seen += 1
            if argv[:2] == ["core", "install"]:
                _o, errors = installer.parse_args(argv[2:], [])
                self.assertEqual(errors, [], example)  # installs are checked, not run
            elif argv[0] == "ui":
                self.assertEqual(argv[0], "ui")  # starts a server: its options are checked below
            elif argv[:2] == ["core", "overrides"] and "edit" in argv:
                continue  # opens $EDITOR on a file that does not exist here
            else:
                rc, out = run_main(argv)
                self.assertIn(rc, (0, None), f"{example}\n{out}")
        self.assertGreater(seen, 15)

    def test_the_ui_options_are_the_ones_it_accepts(self):
        from material_boot.ui import command

        for flags, meta, _s in help.TOP["ui"]["options"]:
            with mock.patch("material_boot.ui.server.serve", return_value=0) as serve:
                self.assertEqual(
                    command.main([flags[0]] + ([{"N": "8765", "SECONDS": "5"}[meta]] if meta else [])), 0, flags
                )
                serve.assert_called_once()
        self.assertEqual(run_main(["ui", "--bogus"])[0], 2)

    def test_every_core_command_has_help_and_every_help_has_a_command(self):
        self.assertEqual(set(commands.COMMANDS), set(help.CORE))
        for name in commands.COMMANDS:
            rc, out = run_main(["core", name, "--help"])
            self.assertEqual(rc, 0, name)
            self.assertIn(f"usage: material-boot {help.CORE[name]['usage']}", out)
            rc2, out2 = run_main(["help", "core", name])
            self.assertEqual((rc2, out2), (0, out) if name != "install" else (0, out2), name)
            for flags, _m, _s in help.CORE[name]["options"]:
                for f in flags:
                    self.assertIn(f, out, f"{name}: {f}")

    def test_help_explains_it_does_not_run_the_command(self):
        """`apply --help` must never apply: a part that records its calls is installed and must stay unused."""
        t = Path(self.tmp.name)
        log = t / "calls"
        (t / "p.py").write_text(f"def main(argv, core):\n    open({str(log)!r}, 'a').write(repr(argv))\n    return 0\n")
        (t / "plugins/demo.json").write_text(
            json.dumps(
                {
                    "manifest": 2,
                    "name": "demo",
                    "title": "Demo",
                    "version": "1.0.0",
                    "core_api": 2,
                    "entry": str(t / "p.py"),
                    "commands": {"apply": "x"},
                }
            )
        )
        for argv in (
            ["core", "apply", "--help"],
            ["core", "apply", "-h"],
            ["core", "colour", "--help"],
            ["core", "doctor", "--help"],
            ["core", "conf", "--help"],
        ):
            rc, out = run_main(argv)
            self.assertEqual(rc, 0, argv)
            self.assertIn("usage:", out)
        self.assertFalse(log.exists(), "a --help ran the apply of a part")
        rc, out = run_main(["core", "apply"])  # and the same part IS used without --help
        self.assertEqual(rc, 0, out)
        self.assertTrue(log.exists())

    def test_help_for_a_part_lists_its_commands(self):
        t = Path(self.tmp.name)
        (t / "plugins/demo.json").write_text(
            json.dumps(
                {
                    "manifest": 2,
                    "name": "demo",
                    "title": "Demo",
                    "version": "1.0.0",
                    "core_api": 2,
                    "entry": str(t / "p.py"),
                    "commands": {"apply": "draw it again"},
                }
            )
        )
        (t / "p.py").write_text("def main(a, c):\n    return 0\n")
        rc, out = run_main(["help", "demo"])
        self.assertEqual(rc, 0)
        self.assertIn("material-boot demo apply", out)
        self.assertIn("draw it again", out)
        self.assertEqual(run_main(["help", "nonsense"])[0], 2)


if __name__ == "__main__":
    unittest.main()
