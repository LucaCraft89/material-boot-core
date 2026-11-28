"""The one view of an install (docs/plans/ux.md, 3.1): every part reports EVENTS while it works and this module is the only thing that draws them. stdlib only.

  {"event": "step", "text": "Rendering the theme"}      a step starts (the previous one ends)
  {"event": "step_end", "ok": True, "text": "..."}      the step ends (optional: the next step, or the end of the part, ends it too)
  {"event": "detail", "text": "..."}                    a line for people who ask for more (-v); always kept in the log
  {"event": "info" | "ok" | "warn" | "error", "text": "..."}   a line

Verbosity: 0 (-q) shows warnings, errors and the result; 1 (the default) shows the part headings and one line per step with its time, and **a live indicator on a
step that takes more than a couple of seconds** ("Rebuilding the initramfs ... 41 s"), so nothing looks stuck; 2 (-v) also shows the details.
On a terminal the running step is redrawn once a second; on a pipe or in a log it is two plain lines (start, end). Everything, details included, goes to the
log file when there is one.
"""

import sys
import threading
import time

LEVEL_QUIET, LEVEL_NORMAL, LEVEL_VERBOSE = 0, 1, 2
LIVE_AFTER = 2.0  # seconds before a running step shows its clock
SPIN_UTF8 = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPIN_ASCII = "|/-\\"


def human(seconds):
    s = int(seconds)
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s} s" if s >= 2 else f"{seconds:.1f} s"


class View:
    """`write(line)` prints a whole line (tests capture it); `raw(text)` writes without a newline (the live line, terminals only)."""

    def __init__(
        self, write=print, raw=None, verbosity=LEVEL_NORMAL, tty=False, log=None, clock=time.time, utf8=True, live=True
    ):
        self.write, self.verbosity, self.tty, self.log, self.clock = write, verbosity, bool(tty), log, clock
        self.raw = raw or (sys.stdout.write if tty else None)
        self.utf8 = utf8
        self.cur = None  # (text, started)
        self.lock = threading.RLock()
        self.spin = 0
        self.stop = threading.Event()
        self.thread = None
        self.live = bool(live and self.tty and self.raw)
        self.mark_ok, self.mark_bad, self.mark_run = ("✓", "✗", "▸") if utf8 else ("ok", "FAIL", ">")

    # -- the log and the lines
    def _log(self, kind, text):
        if self.log:
            try:
                self.log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {kind:<7} {text}\n")
                self.log.flush()
            except (OSError, ValueError):
                self.log = None

    def _line(self, text):
        with self.lock:
            self._erase_live()
            self.write(text)
            if self.cur and self.live and self.verbosity >= LEVEL_NORMAL:
                self._draw_live()  # a line printed while a step runs: the live line comes back under it

    def _erase_live(self):
        if self.cur and self.live and self._live_shown:
            self.raw("\r\x1b[K")
            self._live_shown = False

    _live_shown = False

    # -- what the installer and the parts call
    def heading(self, text):
        """A part (or a stage) begins: its steps are under it."""
        with self.lock:
            self.end()
            self._log("heading", text)
            if self.verbosity >= LEVEL_NORMAL:
                self._line(f"\n== {text}")

    def handle(self, ev):
        """An event of a part (a dict, or a plain string for a part that only prints)."""
        if not isinstance(ev, dict):
            ev = {"event": "info", "text": str(ev)}
        kind = ev.get("event", "info")
        text = str(ev.get("text") or ev.get("msg") or "")
        if kind == "step":
            self.begin(text)
        elif kind == "step_end":
            self.end(ev.get("ok", True), text or None)
        elif kind == "detail":
            self.detail(text)
        elif kind in ("info", "ok", "warn", "error"):
            self.line(kind, text)
        # other kinds (existing_install, done ...) belong to the installer's own JSON stream: not drawn here

    def begin(self, text):
        with self.lock:
            self.end()
            self._log("step", text)
            self.cur = (text, self.clock())
            if self.verbosity < LEVEL_NORMAL:
                return
            if self.live:
                self._draw_live()
                self._start_ticker()
            else:
                self._line(f"  {self.mark_run} {text}")

    def end(self, ok=True, text=None):
        """End the running step (a no-op when there is none)."""
        with self.lock:
            if not self.cur:
                return
            label, t0 = self.cur
            self.cur = None
            self._stop_ticker()
            took = self.clock() - t0
            label = text or label
            self._log("done" if ok else "failed", f"{label} ({took:.1f}s)")
            if self.verbosity >= LEVEL_NORMAL or not ok:
                mark = self.mark_ok if ok else self.mark_bad
                self._live_shown_clear()
                self._line(f"  {mark} {label} ({human(took)})")

    def detail(self, text):
        self._log("detail", text)
        if self.verbosity >= LEVEL_VERBOSE:
            self._line(f"      {text}")

    def line(self, kind, text):
        self._log(kind, text)
        if kind in ("warn", "error") or self.verbosity >= LEVEL_NORMAL:
            prefix = {"warn": "  ! ", "error": "  ! ", "ok": f"  {self.mark_ok} ", "info": "  "}[kind]
            self._line(prefix + text)

    def result(self, text):
        """The last line of a run: shown even with -q."""
        with self.lock:
            self.end()
            self._log("result", text)
            self.write(text)

    def paused(self):
        """`with view.paused():` while a question is on the screen: the live line is taken away and not redrawn (it would overwrite the question every second), and
        comes back after."""
        return _Paused(self)

    def close(self):
        with self.lock:
            self.end()
            self._stop_ticker()

    # -- the live indicator
    def _live_shown_clear(self):
        if self.live and self._live_shown:
            self.raw("\r\x1b[K")
            self._live_shown = False

    def _draw_live(self):
        """(Re)draw the running step with its clock; the clock appears after LIVE_AFTER seconds."""
        if not (self.cur and self.live):
            return
        text, t0 = self.cur
        took = self.clock() - t0
        frames = SPIN_UTF8 if self.utf8 else SPIN_ASCII
        self.spin = (self.spin + 1) % len(frames)
        clock = f" {human(took)}" if took >= LIVE_AFTER else ""
        self.raw(f"\r\x1b[K  {frames[self.spin]} {text} ...{clock}")
        self._live_shown = True

    def tick(self):
        """One redraw of the live line (the ticker thread calls it; tests call it by hand)."""
        with self.lock:
            self._draw_live()

    def _start_ticker(self):
        if self.thread:
            return
        self.stop.clear()

        def run():
            while not self.stop.wait(1.0):
                self.tick()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def _stop_ticker(self):
        if self.thread:
            self.stop.set()
            self.thread = None


class _Paused:
    def __init__(self, view):
        self.view = view

    def __enter__(self):
        v = self.view
        v.lock.acquire()
        self.was = v.live
        v._erase_live()
        v.live = False  # nothing draws the running step while the question is shown
        return v

    def __exit__(self, *_exc):
        v = self.view
        v.live = self.was
        if v.cur and v.live and v.verbosity >= LEVEL_NORMAL:
            v._draw_live()
        v.lock.release()
