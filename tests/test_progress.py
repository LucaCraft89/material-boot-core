"""The one view of an install (material_boot/progress.py): steps with their time, a live indicator on long steps, verbosity, the log."""

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from material_boot import progress  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def view(**kw):
    out, raw, log = [], [], io.StringIO()
    clock = Clock()
    kw.setdefault("tty", False)
    v = progress.View(write=out.append, raw=raw.append, log=log, clock=clock, **kw)
    return v, out, raw, log, clock


class Lines(unittest.TestCase):
    def test_a_step_is_two_lines_on_a_pipe_with_its_time(self):
        v, out, raw, log, clock = view()
        v.heading("Material GRUB 1.2.0")
        v.handle({"event": "step", "text": "Rendering the theme"})
        clock.advance(46)
        v.handle({"event": "step_end"})
        self.assertEqual(out, ["\n== Material GRUB 1.2.0", "  ▸ Rendering the theme", "  ✓ Rendering the theme (46 s)"])
        self.assertEqual(raw, [])  # nothing is redrawn on a pipe

    def test_a_new_step_ends_the_one_before_and_a_heading_ends_the_last(self):
        v, out, _r, _l, clock = view()
        v.begin("one")
        clock.advance(3)
        v.begin("two")
        clock.advance(65)
        v.heading("next part")
        self.assertIn("  ✓ one (3 s)", out)
        self.assertIn("  ✓ two (1m05s)", out)
        self.assertLess(out.index("  ✓ two (1m05s)"), out.index("\n== next part"))

    def test_a_short_step_shows_tenths(self):
        v, out, _r, _l, clock = view()
        v.begin("quick")
        clock.advance(0.4)
        v.end()
        self.assertEqual(out[-1], "  ✓ quick (0.4 s)")

    def test_a_failed_step_says_so_even_with_q(self):
        v, out, _r, _l, clock = view(verbosity=progress.LEVEL_QUIET)
        v.begin("rebuilding")
        clock.advance(5)
        v.handle({"event": "step_end", "ok": False, "text": "rebuilding failed"})
        self.assertEqual(out, ["  ✗ rebuilding failed (5 s)"])

    def test_ascii_marks_when_the_terminal_has_no_utf8(self):
        v, out, _r, _l, clock = view(utf8=False)
        v.begin("x")
        clock.advance(1)
        v.end()
        self.assertEqual(out, ["  > x", "  ok x (1.0 s)"])


class Verbosity(unittest.TestCase):
    EVENTS = [
        {"event": "step", "text": "a step"},
        {"event": "detail", "text": "per-image line"},
        {"event": "info", "text": "an info"},
        {"event": "warn", "text": "a warning"},
        {"event": "ok", "text": "an ok"},
        {"event": "error", "text": "an error"},
    ]

    def run_with(self, level):
        v, out, _r, log, clock = view(verbosity=level)
        for ev in self.EVENTS:
            v.handle(ev)
        clock.advance(2)
        v.close()
        return "\n".join(out), log.getvalue()

    def test_q_shows_only_warnings_and_errors(self):
        text, _ = self.run_with(progress.LEVEL_QUIET)
        self.assertIn("a warning", text)
        self.assertIn("an error", text)
        self.assertNotIn("a step", text)
        self.assertNotIn("an info", text)
        self.assertNotIn("per-image", text)

    def test_default_shows_steps_and_lines_but_not_details(self):
        text, _ = self.run_with(progress.LEVEL_NORMAL)
        self.assertIn("a step", text)
        self.assertIn("an info", text)
        self.assertNotIn("per-image", text)

    def test_v_shows_the_details(self):
        text, _ = self.run_with(progress.LEVEL_VERBOSE)
        self.assertIn("per-image line", text)

    def test_the_log_keeps_everything_whatever_is_shown(self):
        _, logged = self.run_with(progress.LEVEL_QUIET)
        for words in ("a step", "per-image line", "an info", "a warning", "an ok", "an error"):
            self.assertIn(words, logged)

    def test_the_result_is_always_shown(self):
        v, out, _r, _l, _c = view(verbosity=progress.LEVEL_QUIET)
        v.result("Installed: core, grub.")
        self.assertEqual(out, ["Installed: core, grub."])

    def test_a_plain_string_from_a_part_that_only_prints_is_an_info_line(self):
        v, out, _r, _l, _c = view()
        v.handle("hello")
        self.assertEqual(out, ["  hello"])


class Live(unittest.TestCase):
    def test_a_long_step_on_a_terminal_shows_its_clock_and_never_looks_stuck(self):
        v, out, raw, _l, clock = view(tty=True, live=True)
        v.begin("Rebuilding the initramfs")
        self.assertIn("Rebuilding the initramfs ...", raw[-1])
        self.assertNotIn(" s", raw[-1].split("...")[1])  # no clock in the first two seconds
        clock.advance(2.5)
        v.tick()
        self.assertRegex(raw[-1], r"\.\.\. 2 s")
        clock.advance(40)
        v.tick()
        self.assertIn("42 s", raw[-1])
        v.end()
        self.assertEqual(out[-1], "  ✓ Rebuilding the initramfs (42 s)")
        self.assertTrue(raw[-1].startswith("\r\x1b[K"))  # the live line is wiped before the final line
        self.assertEqual(
            out[:-1], []
        )  # nothing else was printed as a line: the live line was the only trace of the running step
        v.close()

    def test_the_indicator_moves(self):
        v, _o, raw, _l, _c = view(tty=True, live=True)
        v.begin("x")
        first = raw[-1]
        v.tick()
        self.assertNotEqual(first, raw[-1])  # the spinner frame changed, so even a silent step visibly lives
        v.close()

    def test_a_line_printed_during_a_live_step_comes_back_with_the_live_line_under_it(self):
        v, out, raw, _l, _c = view(tty=True, live=True, verbosity=progress.LEVEL_VERBOSE)
        v.begin("long step")
        v.detail("image 1 of 5")
        self.assertEqual(out[-1], "      image 1 of 5")
        self.assertIn("long step ...", raw[-1])
        v.close()

    def test_without_live_nothing_is_redrawn(self):
        v, out, raw, _l, clock = view(tty=True, live=False)
        v.begin("x")
        clock.advance(10)
        v.tick()
        self.assertEqual(raw, [])
        v.end()
        self.assertEqual(out[-1], "  ✓ x (10 s)")


if __name__ == "__main__":
    unittest.main()
