"""The installer screen (material_boot/tui.py, docs/plans/tui.md): the questions, the state machine, the preview, the plain prompts, the golden screens,
and the screen inside `material-boot core install`."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_installer import Base as InstallerBase  # noqa: E402

from material_boot import installer, plugins, tui  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden"

GRUB_Q = [
    {
        "id": "res",
        "title": "Resolution",
        "kind": "choice",
        "help": "The size of your screen.",
        "options": [{"value": "", "label": "Detected automatically"}, {"value": "1920x1080", "label": "1920x1080"}],
        "allow_text": True,
        "pattern": "[0-9]{3,5}x[0-9]{3,5}",
        "target": {"option": "res"},
    },
    {"id": "gui", "title": "Graphical editor", "kind": "toggle", "default": False, "target": {"option": "with-gui"}},
    {"id": "countdown", "title": "Countdown bar", "kind": "toggle", "default": True, "target": {"conf": "COUNTDOWN"}},
    {"id": "timeout", "title": "Timeout", "kind": "text", "pattern": "[0-9]*", "target": {"conf": "TIMEOUT"}},
]
PLY_Q = [
    {
        "id": "no-cmdline",
        "title": "Kernel command line",
        "kind": "toggle",
        "default": False,
        "target": {"option": "no-cmdline"},
    }
]


def make_parts(tmp=None):
    def part(name, title, default, options, questions, version="1.0.0"):
        warnings = []
        qs = plugins.read_questions(questions, options, name, warnings)
        assert not warnings, warnings
        return SimpleNamespace(
            name=name,
            title=title,
            summary=f"the {name} part",
            version=version,
            default=default,
            problem=None,
            needs=[],
            options=options,
            questions=qs,
        )

    core = SimpleNamespace(
        name="core",
        title="Core",
        summary="",
        version="1.0.0",
        default=True,
        problem=None,
        needs=[],
        options=[],
        questions=[],
    )
    grub = part(
        "grub",
        "Material GRUB",
        True,
        [{"name": "res", "takes": "value"}, {"name": "with-gui", "takes": "flag"}],
        GRUB_Q,
    )
    ply = part("plymouth", "Material Plymouth", False, [{"name": "no-cmdline", "takes": "flag"}], PLY_Q)
    return [core, grub, ply]


def options(*argv):
    o, errors = installer.parse_args(list(argv), make_parts())
    assert not errors, errors
    return o


def press(flow, *keys):
    r = None
    for k in keys:
        r = flow.key(k)
        if r:
            return r
    return r


def text_of(rows):
    return "\n".join("".join(t for t, _ in r).rstrip() for r in rows)


class Manifest(unittest.TestCase):
    def test_a_good_question_is_read_and_a_bad_one_is_dropped_with_a_warning(self):
        w = []
        opts = [{"name": "res", "takes": "value"}]
        qs = plugins.read_questions(
            [
                GRUB_Q[0],
                {
                    "id": "x",
                    "title": "x",
                    "kind": "choice",
                    "options": [{"value": "a", "label": "A"}],
                    "target": {"option": "nope"},
                },  # not declared
                {"id": "y", "title": "y", "kind": "dial", "target": {"conf": "STYLE"}},  # unknown kind
                {"id": "z", "title": "z", "kind": "choice", "options": [], "target": {"conf": "STYLE"}},  # no options
                {"id": "res", "title": "dup", "kind": "text", "target": {"conf": "TIMEOUT"}},  # duplicate id
                "junk",
            ],
            opts,
            "grub",
            w,
        )
        self.assertEqual([q["id"] for q in qs], ["res"])
        self.assertEqual(len(w), 5)
        self.assertEqual(qs[0]["when"], "fresh")

    def test_a_bad_pattern_is_dropped_not_fatal(self):
        w = []
        q = plugins.read_questions(
            [{"id": "t", "title": "T", "kind": "text", "pattern": "([", "target": {"conf": "TIMEOUT"}}], [], "p", w
        )
        self.assertEqual(len(q), 1)
        self.assertIsNone(q[0]["pattern"])

    def test_a_manifest_with_questions_reaches_the_part(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as t:
            m = Path(t) / "grub.json"
            (Path(t) / "x.py").write_text("")
            m.write_text(
                json.dumps(
                    {
                        "manifest": 2,
                        "name": "grub",
                        "version": "1.0.0",
                        "core_api": 2,
                        "entry": "x.py",
                        "install": {"options": [{"name": "res", "takes": "value"}], "questions": [GRUB_Q[0]]},
                    }
                )
            )
            p = plugins.read_manifest(m)
        self.assertEqual([q["id"] for q in p.questions], ["res"])


class Steps(unittest.TestCase):
    def ids(self, o, installed=(), force=False):
        return [s["id"] for s in tui.build_steps(make_parts(), set(installed), o, force)]

    def test_a_fresh_system_asks_the_parts_the_look_and_every_part_s_questions(self):
        self.assertEqual(
            self.ids(options()),
            [
                "parts",
                "STYLE",
                "SCHEME",
                "SEED",
                "LOGO",
                "HINTS",
                "grub.res",
                "grub.gui",
                "grub.countdown",
                "grub.timeout",
                "plymouth.no-cmdline",
            ],
        )

    def test_what_a_flag_answered_is_not_asked(self):
        ids = self.ids(
            options(
                "--style",
                "split",
                "--seed",
                "#FF0000",
                "--grub-res",
                "1920x1080",
                "--no-cookie",
                "--no-logo",
                "--no-hints",
                "--scheme",
                "light",
            )
        )
        self.assertEqual(ids, ["parts", "grub.gui", "grub.countdown", "grub.timeout", "plymouth.no-cmdline"])

    def test_with_or_without_or_only_skips_the_parts_question(self):
        for argv in (["--with", "plymouth"], ["--without", "plymouth"], ["--only", "grub"]):
            self.assertNotIn("parts", self.ids(options(*argv)), argv)

    def visible(self, o, installed=(), force=False, current=None, values=None):
        parts = make_parts()
        f = tui.Flow(
            tui.build_steps(parts, set(installed), o, force, current), o, tui.selected_names(parts, set(installed), o)
        )
        if values:
            f.values.update(values)
        return [x["id"] for x in f.visible()], f

    def test_an_update_asks_which_parts_then_keep_or_edit_and_the_questions_of_a_part_that_is_new(self):
        ids, f = self.visible(options(), installed={"core", "grub"})
        self.assertEqual(
            ids, ["parts", "keep_edit"]
        )  # kept: nothing about the look; Plymouth is not ticked, so it asks nothing
        self.assertEqual(f.values["keep_edit"], "keep")  # the default
        ids, _f = self.visible(options(), installed={"core", "grub"}, values={"parts": ["grub", "plymouth"]})
        self.assertEqual(
            ids, ["parts", "keep_edit", "plymouth.no-cmdline"]
        )  # ticked: a part new to the machine asks its own question even when kept

    def test_choosing_to_edit_asks_everything_again_for_what_is_installed(self):
        ids, _f = self.visible(options(), installed={"core", "grub"}, values={"keep_edit": "edit"})
        self.assertEqual(
            ids,
            [
                "parts",
                "keep_edit",
                "STYLE",
                "SCHEME",
                "SEED",
                "LOGO",
                "HINTS",
                "grub.res",
                "grub.gui",
                "grub.countdown",
                "grub.timeout",
            ],
        )

    def test_editing_starts_from_what_is_set_now(self):
        current = {
            "conf": {
                "STYLE": "split",
                "SCHEME": "light",
                "COOKIE": "on",
                "LOGO": "off",
                "HINTS": "off",
                "COUNTDOWN": "off",
                "TIMEOUT": "7",
            },
            "seed": {"mode": "single", "color": "#C62828"},
        }
        _ids, f = self.visible(options(), installed={"core", "grub"}, current=current, values={"keep_edit": "edit"})
        self.assertEqual(
            {k: f.values[k] for k in ("STYLE", "SCHEME", "SEED", "LOGO", "HINTS", "grub.countdown", "grub.timeout")},
            {
                "STYLE": "split",
                "SCHEME": "light",
                "SEED": "#C62828",
                "LOGO": "cookie",
                "HINTS": "off",
                "grub.countdown": False,
                "grub.timeout": "7",
            },
        )

    def test_keeping_changes_nothing_about_the_look(self):
        o = options()
        _ids, f = self.visible(o, installed={"core", "grub"})
        f.apply(o)
        self.assertEqual((o.look, o.seed, o.seed_mode), ({}, None, None))
        self.assertEqual(o.part_opts, {})

    def test_editing_sends_the_answers_to_the_options(self):
        o = options()
        _ids, f = self.visible(
            o, installed={"core", "grub"}, values={"keep_edit": "edit", "STYLE": "clean", "grub.timeout": "9"}
        )
        f.apply(o)
        self.assertEqual(o.look["STYLE"], "clean")
        self.assertEqual(o.look["TIMEOUT"], "9")

    def test_a_fresh_machine_has_no_keep_or_edit_question(self):
        ids, _f = self.visible(options(), installed=set())
        self.assertNotIn("keep_edit", ids)

    def test_tui_forces_the_whole_screen_on_an_update(self):
        self.assertIn("STYLE", self.ids(options("--tui"), installed={"core", "grub"}, force=True))

    def test_a_part_that_is_not_chosen_asks_nothing(self):
        o = options()
        flow = tui.Flow(tui.build_steps(make_parts(), set(), o), o, tui.selected_names(make_parts(), set(), o))
        self.assertNotIn("plymouth.no-cmdline", [s["id"] for s in flow.visible()])
        press(flow, "down", "space")  # tick Plymouth in the parts step
        self.assertIn("plymouth.no-cmdline", [s["id"] for s in flow.visible()])
        self.assertIn("grub.res", [s["id"] for s in flow.visible()])

    def test_selected_names_follows_the_installers_rules(self):
        parts = make_parts()
        self.assertEqual(tui.selected_names(parts, set(), options()), {"grub"})
        self.assertEqual(
            tui.selected_names(parts, set(), options("--with", "plymouth")), {"plymouth"}
        )  # --with replaces the defaults
        self.assertEqual(
            tui.selected_names(parts, {"core", "grub"}, options("--with", "plymouth")), {"grub", "plymouth"}
        )
        self.assertEqual(tui.selected_names(parts, set(), options("--only", "plymouth")), {"plymouth"})


class Machine(unittest.TestCase):
    def flow(self, *argv, installed=()):
        o = options(*argv)
        parts = make_parts()
        return o, tui.Flow(tui.build_steps(parts, set(installed), o), o, tui.selected_names(parts, set(installed), o))

    def test_enter_through_the_defaults_gives_the_defaults(self):
        o, f = self.flow()
        r = press(f, *["enter"] * 11)  # eleven steps, the last enter goes to the summary
        self.assertIsNone(r)
        self.assertIsNone(f.current())  # the summary
        press(f, "enter")  # Install
        f.apply(o)
        self.assertEqual(o.with_, ["grub"])
        self.assertEqual(o.without, ["plymouth"])
        self.assertEqual(o.look["STYLE"], "rail")
        self.assertEqual(o.seed_mode, "multi")
        self.assertEqual(o.look["COOKIE"], "on")
        self.assertEqual(o.look["COUNTDOWN"], "on")
        self.assertEqual(o.part_opts, {})  # defaults pass no option

    def test_a_choice_a_toggle_and_a_typed_value_reach_the_options(self):
        o, f = self.flow("--with", "grub,plymouth")  # no parts step
        # STYLE: down twice = list
        press(f, "down", "down", "enter")
        self.assertEqual(f.values["STYLE"], "list")
        press(f, "down", "enter")  # light
        self.assertEqual(f.values["SCHEME"], "light")
        # SEED: down to "Crimson" (first named seed), enter
        press(f, "down", "enter")
        self.assertEqual(f.values["SEED"], "#C62828")
        press(f, "enter", "enter")  # LOGO, HINTS defaults
        # resolution: the typed option is the last one
        s = f.current()
        self.assertEqual(s["id"], "grub.res")
        press(f, "down", "down", "enter")  # "Another value..." -> edit
        self.assertEqual(f.edit, "")
        for ch in "2560x1440":
            f.key(ch)
        press(f, "enter")
        self.assertEqual(f.values["grub.res"], "2560x1440")
        press(f, "down", "enter")  # the graphical editor: No -> Yes? (options are [Yes, No]; default No is the cursor)
        press(f, "enter")  # countdown: default Yes
        press(f, "enter", "5", "enter")  # timeout: enter starts editing, 5, enter accepts
        self.assertEqual(f.values["grub.timeout"], "5")
        press(f, "enter")  # plymouth: no-cmdline default No
        self.assertIsNone(f.current())
        f.apply(o)
        self.assertEqual(o.look["STYLE"], "list")
        self.assertEqual(o.look["SCHEME"], "light")
        self.assertEqual((o.seed, o.seed_mode), ("#C62828", "single"))
        self.assertEqual(o.part_opts["grub"]["res"], "2560x1440")
        self.assertEqual(o.look["TIMEOUT"], "5")

    def test_an_invalid_typed_value_is_refused_with_a_message(self):
        o, f = self.flow(
            "--with",
            "grub",
            "--style",
            "rail",
            "--scheme",
            "dark",
            "--seed-mode",
            "multi",
            "--no-cookie",
            "--no-logo",
            "--no-hints",
        )
        self.assertEqual(f.current()["id"], "grub.res")
        press(f, "down", "down", "enter")
        for ch in "big":
            f.key(ch)
        f.key("enter")
        self.assertIn("not valid", f.error)
        self.assertEqual(f.current()["id"], "grub.res")  # still here
        press(f, "backspace", "backspace", "backspace")
        for ch in "1366x768":
            f.key(ch)
        f.key("enter")
        self.assertEqual(f.values["grub.res"], "1366x768")

    def test_the_equivalent_command_line_and_settings(self):
        o, f = self.flow(
            "--with", "grub,plymouth", "--style", "split", "--scheme", "dark", "--no-cookie", "--no-logo", "--hints"
        )
        f.values["SEED"] = "#C62828"
        f.values["grub.res"] = "1920x1080"
        f.values["grub.gui"] = True
        f.values["grub.countdown"] = False
        f.values["plymouth.no-cmdline"] = True
        cmd = f.command()
        self.assertIn("--seed #C62828", cmd)
        self.assertIn("--grub-res 1920x1080", cmd)
        self.assertIn("--grub-with-gui", cmd)
        self.assertIn("--plymouth-no-cmdline", cmd)
        self.assertNotIn("COUNTDOWN", cmd)
        self.assertEqual(f.settings(), {"COUNTDOWN": "off"})

    def test_the_command_line_the_screen_prints_gives_the_same_options_when_parsed(self):
        o, f = self.flow("--with", "grub,plymouth")
        f.values.update(
            {
                "STYLE": "clean",
                "SCHEME": "light",
                "SEED": "#00897B",
                "LOGO": "none",
                "HINTS": "off",
                "grub.res": "2560x1440",
                "grub.gui": True,
            }
        )
        f.apply(o)
        o2, errors = installer.parse_args(f.command().split()[3:], make_parts())
        self.assertEqual(errors, [])
        self.assertEqual(o2.look["STYLE"], o.look["STYLE"])
        self.assertEqual(
            {k: o2.look[k] for k in ("COOKIE", "LOGO", "HINTS")}, {k: o.look[k] for k in ("COOKIE", "LOGO", "HINTS")}
        )
        self.assertEqual((o2.seed, o2.seed_mode), (o.seed, o.seed_mode))
        self.assertEqual(o2.part_opts.get("grub"), {"res": "2560x1440", "with-gui": True})

    def test_escape_goes_back_then_cancels_and_q_quits(self):
        o, f = self.flow()
        press(f, "enter", "enter")
        self.assertEqual(f.current()["id"], "SCHEME")
        f.key("esc")
        self.assertEqual(f.current()["id"], "STYLE")
        f.key("esc")
        self.assertEqual(f.current()["id"], "parts")
        self.assertEqual(f.key("esc"), "cancel")
        self.assertEqual(self.flow()[1].key("q"), "cancel")

    def test_the_summary_installs_goes_back_or_cancels(self):
        o, f = self.flow(
            "--only",
            "grub",
            "--style",
            "rail",
            "--scheme",
            "dark",
            "--seed-mode",
            "multi",
            "--no-cookie",
            "--no-logo",
            "--no-hints",
        )
        for _ in range(5):
            f.key("enter")
        self.assertIsNone(f.current())
        f.key("down")
        f.key("enter")  # Back
        self.assertIsNotNone(f.current())
        self.assertEqual(f.current()["id"], "grub.timeout")  # Back lands on the last question, a text one
        press(f, "enter", "enter")  # start editing, accept: the summary again, on Install
        self.assertIsNone(f.current())
        self.assertEqual(press(f, "down", "down", "enter"), "cancel")
        o, f = self.flow(
            "--only",
            "grub",
            "--style",
            "rail",
            "--scheme",
            "dark",
            "--seed-mode",
            "multi",
            "--no-cookie",
            "--no-logo",
            "--no-hints",
        )
        for _ in range(5):
            f.key("enter")
        self.assertEqual(f.key("enter"), "done")

    def test_the_parts_step_ticks_with_space_and_keeps_the_core_out_of_the_list(self):
        o, f = self.flow()
        s = f.current()
        self.assertEqual([x["value"] for x in s["options"]], ["grub", "plymouth"])
        press(f, "space")  # untick grub
        self.assertEqual(f.values["parts"], [])
        press(f, "space", "down", "space")
        self.assertEqual(sorted(f.values["parts"]), ["grub", "plymouth"])


class Preview(unittest.TestCase):
    def values(self, **kw):
        return {"STYLE": "rail", "SCHEME": "dark", "SEED": "multi", **kw}

    def step(self, id="STYLE"):
        return {"id": id}

    def test_every_style_has_its_own_drawing(self):
        drawings = {s: tui.preview_rows(self.values(STYLE=s), self.step()) for s in ("rail", "clean", "list", "split")}
        self.assertTrue(all(drawings.values()))
        self.assertEqual(len({repr(d) for d in drawings.values()}), 4)

    def test_the_colours_follow_the_seed_and_the_scheme(self):
        # the drawing only: the caption under it names the seed, which would make a test of the colours pass by itself
        a = tui.preview_rows(self.values(SEED="#C62828"), self.step("SEED"))[:-1]
        b = tui.preview_rows(self.values(SEED="#1565C0"), self.step("SEED"))[:-1]
        c = tui.preview_rows(self.values(SEED="#C62828", SCHEME="light"), self.step("SCHEME"))[:-1]
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)

    def test_a_row_is_two_pixels_per_cell_and_the_drawing_has_the_expected_size(self):
        rows = tui.preview_rows(self.values(), self.step())
        self.assertEqual(len(rows) - 1, tui.PREVIEW_H // 2)  # the last row is the caption
        self.assertTrue(all(len(r) == tui.PREVIEW_W for r in rows[:-1]))
        self.assertTrue(all(isinstance(s, tuple) and len(s) == 2 for r in rows[:-1] for _, s in r))

    def test_a_terminal_without_256_colours_gets_no_preview_instead_of_noise(self):
        parts = make_parts()
        o = options("--with", "grub")
        f = tui.Flow(tui.build_steps(parts, set(), o), o, {"grub"})
        coloured = [
            st
            for r in f.rows(120, 40)
            for _, st in r
            if isinstance(st, tuple) and len(st) == 2 and st[0].startswith("#") and st[1].startswith("#")
        ]
        self.assertTrue(coloured)
        plain = [st for r in f.rows(120, 40, color=False) for _, st in r if isinstance(st, tuple)]
        self.assertEqual(plain, [])  # no drawing (the seed chips are drawn in colour too, but only on their own step)
        self.assertNotIn("\u2580", text_of(f.rows(120, 40, color=False)))

    def test_no_preview_for_a_question_about_something_else(self):
        self.assertEqual(tui.preview_rows(self.values(), {"id": "grub.res"}), [])

    def test_the_preview_follows_the_highlighted_option(self):
        parts = make_parts()
        o = options("--with", "grub")
        f = tui.Flow(tui.build_steps(parts, set(), o), o, {"grub"})
        a = text_of(f.rows(120, 40))
        f.key("down")  # highlight "clean"
        b = text_of(f.rows(120, 40))
        self.assertNotEqual(a, b)
        self.assertEqual(f.values["STYLE"], "rail")  # highlighted, not chosen


class OnThisSystem(unittest.TestCase):
    """The screen says what is installed already (the installer's own notice comes only after the screen)."""

    def parts(self):
        return make_parts()

    def test_an_update_lists_what_is_installed_and_what_will_happen_to_it(self):
        lines = tui.existing_lines(self.parts(), {"core", "grub"}, {"core": "1.1.0", "grub": "1.0.0"})
        self.assertTrue(
            any("Material GRUB 1.0.0" in x and "will be updated to 1.0.0" not in x for x in lines)
            or any("Material GRUB 1.0.0" in x for x in lines)
        )
        self.assertTrue(any("settings" in x and "kept" in x and "1.1.0" in x for x in lines))
        self.assertFalse(any("Plymouth" in x for x in lines))  # not installed: not listed

    def test_the_versions_decide_the_wording(self):
        p = self.parts()
        newer = tui.existing_lines(p, {"core", "grub"}, {"core": "1.1.0", "grub": "0.7.1"})
        same = tui.existing_lines(p, {"core", "grub"}, {"core": "1.1.0", "grub": "1.0.0"})
        older = tui.existing_lines(p, {"core", "grub"}, {"core": "1.1.0", "grub": "2.0.0"})
        self.assertTrue(any("will be updated" in x for x in newer), newer)
        self.assertTrue(any("same version" in x for x in same), same)
        self.assertTrue(any("NEWER" in x and "not be downgraded" in x for x in older), older)

    def test_a_fresh_system_says_nothing_is_installed(self):
        self.assertEqual(
            tui.existing_lines(self.parts(), {"core"}, {}), ["Nothing from Material Boot is installed yet."]
        )

    def test_the_first_screen_and_the_summary_show_it(self):
        o = options()
        parts = self.parts()
        found = tui.existing_lines(parts, {"core", "grub"}, {"core": "1.1.0", "grub": "1.0.0"})
        f = tui.Flow(
            tui.build_steps(parts, {"core", "grub"}, o), o, tui.selected_names(parts, {"core", "grub"}, o), found
        )
        first = text_of(f.rows(80, 30))
        self.assertIn("On this system:", first)
        self.assertIn("Material GRUB 1.0.0", first)
        while f.current() is not None:
            press(f, *(["enter", "enter"] if f.current()["kind"] == "text" else ["enter"]))
        summary = text_of(f.rows(100, 40))
        self.assertIn("On this system:", summary)
        self.assertIn("After the install, more customisation:", summary)
        self.assertIn("material-boot core overrides", summary)
        self.assertIn("--tui", summary)

    def test_the_plain_prompts_say_it_too(self):
        o = options("--with", "grub")
        parts = self.parts()
        out = io.StringIO()
        found = tui.existing_lines(parts, {"core", "grub"}, {"core": "1.1.0", "grub": "1.0.0"})
        f = tui.Flow(
            tui.build_steps(parts, {"core", "grub"}, o), o, tui.selected_names(parts, {"core", "grub"}, o), found
        )
        with redirect_stdout(out):
            tui.run_plain(f, inp=lambda prompt="": "q", out=print)
        self.assertIn("On this system:", out.getvalue())

    def test_the_customisation_lines_name_real_core_commands(self):
        from material_boot import commands

        for ln in tui.after_lines(["grub"]):
            if ln.startswith("material-boot core "):
                self.assertIn(ln.split()[2], commands.COMMANDS, ln)

    def test_the_gui_line_is_for_grub_only(self):
        self.assertTrue(any("material-grub gui" in x for x in tui.after_lines(["grub"])))
        self.assertFalse(any("material-grub gui" in x for x in tui.after_lines(["plymouth"])))


class Scrolling(unittest.TestCase):
    def flow_at_the_seeds(self, *extra):
        o = options("--with", "grub", "--style", "rail", "--scheme", "dark", *extra)
        parts = make_parts()
        return tui.Flow(tui.build_steps(parts, set(), o), o, {"grub"})

    def test_the_highlighted_option_is_always_on_the_screen(self):
        f = self.flow_at_the_seeds()
        self.assertEqual(f.current()["id"], "SEED")
        for n in range(len(f.current()["options"]) + 2):  # all the way down, and round again
            lines = text_of(f.rows(80, 24)).splitlines()
            self.assertLessEqual(len(lines), 24, n)
            self.assertTrue(
                any(ln.startswith(" > ") for ln in lines), f"no highlighted row after {n} downs:\n" + "\n".join(lines)
            )
            f.key("down")

    def test_a_cut_list_says_so(self):
        f = self.flow_at_the_seeds()
        text = text_of(f.rows(80, 24))
        self.assertIn("more below", text)
        for _ in range(10):
            f.key("down")
        text = text_of(f.rows(80, 24))
        self.assertIn("more above", text)
        self.assertIn("more below", text)

    def test_a_seed_has_a_colour_chip(self):
        f = self.flow_at_the_seeds()
        f.key("down")  # Crimson
        chips = [(t, st) for r in f.rows(80, 24) for t, st in r if t == "\u2588\u2588"]
        self.assertTrue(chips)
        self.assertEqual(chips[0][1], ("#C62828", "#C62828"))


class Plain(unittest.TestCase):
    def run_plain(self, answers, *argv):
        o = options(*argv)
        parts = make_parts()
        out = io.StringIO()
        it = iter(answers)
        with redirect_stdout(out):
            ok = tui.run(parts, set(), o, say=print, inp=lambda prompt="": next(it), plain=True)
        return ok, o, out.getvalue()

    def test_scripted_answers(self):
        ok, o, text = self.run_plain(
            ["1,2", "3", "2", "", "2", "", "", "", "", "", "", "", "", "y"],
            # parts: grub and plymouth; style 3 (list); scheme 2 (light); seed: default; logo default; hints 2 (off)...
        )
        self.assertTrue(ok, text)
        self.assertEqual(sorted(o.with_), ["grub", "plymouth"])
        self.assertEqual(o.look["STYLE"], "list")
        self.assertEqual(o.look["SCHEME"], "light")
        self.assertIn("Ready to install:", text)
        self.assertIn("material-boot core install --with grub,plymouth", text)

    def test_a_python_without_curses_says_so_and_asks_plainly(self):
        o = options(
            "--with",
            "grub",
            "--style",
            "rail",
            "--scheme",
            "dark",
            "--seed-mode",
            "multi",
            "--no-cookie",
            "--no-logo",
            "--no-hints",
        )
        out = io.StringIO()
        answers = iter(
            ["", "", "", "", "", "y"]
        )  # res, raw names, countdown, timeout, editor are all the defaults; then Install
        with (
            redirect_stdout(out),
            mock.patch.dict(sys.modules, {"curses": None}),  # `import curses` raises ImportError
            mock.patch.dict(os.environ, {"TERM": "xterm-256color"}),
            mock.patch.object(sys.stdin, "isatty", return_value=True),
            mock.patch.object(sys.stdout, "isatty", return_value=True),
        ):
            ok = tui.run(make_parts(), set(), o, say=print, inp=lambda prompt="": next(answers))
        self.assertTrue(ok, out.getvalue())
        self.assertIn("no curses module", out.getvalue())
        self.assertIn("Ready to install:", out.getvalue())

    def test_q_cancels_and_changes_nothing(self):
        ok, o, text = self.run_plain(["q"])
        self.assertFalse(ok)
        self.assertEqual(o.look, {})
        self.assertEqual(o.with_, [])
        self.assertIn("nothing changed", text)

    def test_a_bad_number_is_asked_again(self):
        ok, o, text = self.run_plain(["", "9", "1", "", "", "", "", "", "", "", "", "", "", "y"])
        self.assertIn("not one of the numbers", text)
        self.assertEqual(o.look["STYLE"], "rail")

    def test_end_of_input_cancels(self):
        o = options()
        with redirect_stdout(io.StringIO()):
            ok = tui.run(make_parts(), set(), o, inp=mock.Mock(side_effect=EOFError), plain=True)
        self.assertFalse(ok)


class RealTerminal(unittest.TestCase):
    """The curses screen on a real pty (xterm-256color, 120x40), driven by key presses: what a person at a terminal sees and does."""

    CODE = (
        f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parent.parent)!r}); sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
        "from test_tui import make_parts, options\n"
        "from material_boot import tui\n"
        "o = options(*sys.argv[1:]); parts = make_parts()\n"
        "ok = tui.run(parts, set(), o, plain=False)\n"
        "print('RESULT', ok, sorted(o.with_), o.look.get('STYLE'), o.seed_mode, o.seed, o.part_opts, flush=True)\n"
    )

    def session(self, argv, steps, rows=40, cols=120):
        """steps: [(text to wait for, keys to send)]; returns everything that was printed."""
        import fcntl
        import pty
        import select
        import struct
        import subprocess
        import termios
        import time

        m, sl = pty.openpty()
        fcntl.ioctl(sl, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        env = dict(os.environ, TERM="xterm-256color", LINES=str(rows), COLUMNS=str(cols), MATERIAL_BOOT_TUI_REPAINT="1")
        proc = subprocess.Popen(
            [sys.executable, "-c", self.CODE, *argv], stdin=sl, stdout=sl, stderr=sl, env=env, close_fds=True
        )
        os.close(sl)
        seen = b""

        def read_until(text, timeout=15):
            nonlocal seen
            end = time.time() + timeout
            while time.time() < end:
                if text.encode() in seen:
                    return True
                r, _, _ = select.select([m], [], [], 0.2)
                if r:
                    try:
                        chunk = os.read(m, 65536)
                    except OSError:
                        return text.encode() in seen
                    if not chunk:
                        return text.encode() in seen
                    seen += chunk
            return text.encode() in seen

        try:
            for wait, keys in steps:
                self.assertTrue(read_until(wait), f"never saw {wait!r}; got:\n{seen.decode(errors='replace')[-1500:]}")
                time.sleep(0.15)  # the screen is drawn; keys that arrive in the middle of a redraw are still queued
                seen_before = len(seen)
                os.write(m, keys.encode())
                if keys:
                    time.sleep(0.15)
                    del seen_before
            read_until("RESULT", 15)
            proc.wait(timeout=15)
        finally:
            if proc.poll() is None:
                proc.kill()
            os.close(m)
        return seen.decode(errors="replace")

    DOWN, ENTER, ESC = "\x1bOB", "\r", "\x1b"  # the arrow key as an xterm sends it in keypad mode

    def test_the_whole_screen_with_keys(self):
        out = self.session(
            [
                "--with",
                "grub",
                "--style",
                "rail",
                "--scheme",
                "dark",
                "--seed-mode",
                "multi",
                "--no-cookie",
                "--no-logo",
                "--no-hints",
            ],
            [
                ("Resolution", self.ENTER),  # automatic
                ("Graphical editor", self.ENTER),  # No
                ("Countdown bar", self.ENTER),  # Yes
                ("Timeout", self.ENTER + self.ENTER),  # edit, accept empty
                ("Ready to install", self.ENTER),  # Install
            ],
        )
        self.assertIn("RESULT True ['grub'] rail multi None {}", out)

    def test_the_look_is_drawn_in_colour_and_the_choice_reaches_the_options(self):
        out = self.session(
            [
                "--with",
                "grub",
                "--grub-res",
                "1920x1080",
                "--no-cookie",
                "--no-logo",
                "--no-hints",
                "--scheme",
                "dark",
                "--seed-mode",
                "multi",
            ],
            [
                ("Full screen with a left rail", self.DOWN + self.DOWN + self.ENTER),  # style: list
                ("Graphical editor", self.ENTER),
                ("Countdown bar", self.ENTER),
                ("Timeout", self.ENTER + self.ENTER),
                ("Ready to install", self.ENTER),
            ],
        )
        self.assertRegex(
            out, r"\x1b\[[0-9;]*38;5;\d+"
        )  # 256-colour foreground: the preview and the chips are really coloured
        self.assertRegex(out, r"\x1b\[[0-9;]*48;5;\d+")
        self.assertIn("\u2580", out)  # the half blocks of the drawing
        self.assertIn("RESULT True ['grub'] list multi None {'grub': {'res': '1920x1080'}}", out)

    def test_q_cancels_and_the_terminal_is_given_back(self):
        out = self.session(["--with", "grub"], [("Style", "q")])
        self.assertIn("RESULT False", out)
        self.assertIn("nothing changed", out)

    def test_a_terminal_that_is_too_small_says_so(self):
        out = self.session(["--with", "grub"], [("Make the terminal bigger", "q")], rows=8, cols=40)
        self.assertIn("RESULT False", out)


class Wanted(unittest.TestCase):
    def o(self, *argv):
        return options(*argv)

    def test_only_a_terminal_and_nobody_scripting(self):
        self.assertTrue(tui.wanted(self.o(), tty=True))
        self.assertFalse(tui.wanted(self.o(), tty=False))
        for argv in (
            ["--yes"],
            ["--dry-run"],
            ["--from-package"],
            ["--uninstall"],
            ["--progress", "json"],
            ["--no-tui"],
            ["--root", "/r"],
        ):
            self.assertFalse(tui.wanted(self.o(*argv), tty=True), argv)
        self.assertTrue(tui.wanted(self.o("--tui"), tty=True))
        with mock.patch.dict(os.environ, {"MATERIAL_BOOT_TUI": "0"}):
            self.assertFalse(tui.wanted(self.o(), tty=True))


class Golden(unittest.TestCase):
    """Each screen at a fixed size, as text, compared with a stored copy: a change of wording or layout is a deliberate diff (UPDATE_GOLDEN=1 rewrites them)."""

    def check(self, name, text):
        path = GOLDEN / f"tui_{name}.txt"
        if os.environ.get("UPDATE_GOLDEN") == "1":
            GOLDEN.mkdir(exist_ok=True)
            path.write_text(text + "\n")
        self.assertEqual(path.read_text().rstrip("\n"), text, f"{path.name} differs (UPDATE_GOLDEN=1 to rewrite)")

    def flow(self, *argv):
        o = options(*argv)
        parts = make_parts()
        return tui.Flow(tui.build_steps(parts, set(), o), o, tui.selected_names(parts, set(), o))

    def test_screens(self):
        f = self.flow()
        self.check("parts_80x24", text_of(f.rows(80, 24)))
        press(f, "enter")
        self.check("style_80x24", text_of(f.rows(80, 24)))
        self.check("style_120x40", text_of(f.rows(120, 40)))
        press(f, "down", "down", "enter")
        self.check("scheme_80x24", text_of(f.rows(80, 24)))
        press(f, "enter")
        self.check("seed_120x40", text_of(f.rows(120, 40)))

    def test_questions_and_summary(self):
        f = self.flow(
            "--with",
            "grub,plymouth",
            "--style",
            "split",
            "--scheme",
            "dark",
            "--seed-mode",
            "multi",
            "--no-cookie",
            "--no-logo",
            "--no-hints",
        )
        self.check("res_80x24", text_of(f.rows(80, 24)))
        while (
            f.current() is not None
        ):  # the defaults all the way: a text question takes one more Enter (start typing, accept)
            press(f, *(["enter", "enter"] if f.current()["kind"] == "text" else ["enter"]))
        self.assertIsNone(f.current(), "the walk must end on the summary")
        self.check("summary_80x24", text_of(f.rows(80, 24)))
        self.check("summary_120x40", text_of(f.rows(120, 40)))


class InTheInstaller(InstallerBase):
    """`material-boot core install` with the screen (the plain prompts: stdin is not a terminal here)."""

    def parts(self):
        self.part(
            "grub",
            install={"default": True, "options": [{"name": "res", "takes": "value"}], "questions": [GRUB_Q[0]]},
        )
        self.part("plymouth", install={"options": [{"name": "no-cmdline", "takes": "flag"}], "questions": PLY_Q})

    def run_screen(self, answers, *argv):
        self.parts()
        out = io.StringIO()
        with (
            redirect_stdout(out),
            mock.patch("builtins.input", side_effect=list(answers)),
            mock.patch.object(tui, "wanted", return_value=True),
        ):
            rc = installer.main(["--bundle", str(self.bundle), "--root", str(self.rootdir), *argv])
        return rc, out.getvalue()

    def test_the_answers_drive_what_is_installed_and_how(self):
        # parts: both; style 4 (split); scheme default; seed default; logo default; hints default; resolution 2 (1920x1080); plymouth: no-cmdline yes (1)
        rc, out = self.run_screen(["1,2", "4", "", "", "", "", "2", "1", "y"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(self.hooks_of("install")), ["grub", "plymouth"])
        inst = {c["part"]: c for c in self.calls() if c["hook"] == "install"}
        self.assertEqual(inst["grub"]["options"], {"res": "1920x1080"})
        self.assertEqual(inst["plymouth"]["options"], {"no-cmdline": True})
        self.assertEqual(inst["grub"]["style"], "split")

    def test_the_summary_is_the_confirmation_so_the_installer_does_not_ask_again(self):
        # core and grub are installed already: the installer prints the notice of the existing install, but `Continue?` would be asked twice
        from material_boot import state

        state.record(str(self.rootdir), "1.0.0", "source", "normal", parts={"core": "1.0.0", "grub": "1.0.0"})
        self.part("grub", install={"default": True, "options": [], "questions": []})
        out = io.StringIO()
        with (
            redirect_stdout(out),
            # the parts step, keep or edit, then the summary: there is no fourth answer to give
            mock.patch("builtins.input", side_effect=["", "", "y"]) as asked,
            mock.patch.object(tui, "wanted", return_value=True),
        ):
            rc = installer.main(["--bundle", str(self.bundle), "--root", str(self.rootdir)])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn("Existing install", out.getvalue())
        self.assertFalse([c for c in asked.call_args_list if "Continue?" in str(c)], asked.call_args_list)

    def test_without_the_screen_the_installer_still_asks_continue(self):
        from material_boot import state

        state.record(str(self.rootdir), "1.0.0", "source", "normal", parts={"core": "1.0.0", "grub": "1.0.0"})
        self.part("grub", install={"default": True, "options": []})
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("builtins.input", side_effect=["y"]) as asked:
            rc = installer.main(["--bundle", str(self.bundle), "--root", str(self.rootdir)])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertTrue([c for c in asked.call_args_list if "Continue?" in str(c)], asked.call_args_list)

    def test_cancelling_the_screen_installs_nothing(self):
        rc, out = self.run_screen(["q"])
        self.assertEqual(rc, 1)
        self.assertIn("nothing changed", out)
        self.assertEqual(self.hooks_of("install", core=True), [])

    def test_yes_never_shows_the_screen(self):
        self.parts()
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("builtins.input", side_effect=AssertionError("asked")):
            rc = installer.main(["--bundle", str(self.bundle), "--root", str(self.rootdir), "--yes"])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertEqual(self.hooks_of("install"), ["grub"])  # the defaults, as before


if __name__ == "__main__":
    unittest.main()
