"""The installer screen of `material-boot core install` (docs/plans/tui.md). stdlib only: curses, with a plain-prompt fallback.

It only COLLECTS answers: they are written into the installer's options (`o`), exactly as if the equivalent flags had been given (the summary prints them),
and nothing is touched until the last confirmation. A question that a flag already answered is not asked again.

  steps = build_steps(parts, installed, o)        the questions: which parts, the shared look, then each part's own (`install.questions` of its manifest)
  flow = Flow(steps)                              the state machine: `flow.key("down")`, `flow.rows(w, h)` (pure: no terminal needed, tests drive it)
  run(parts, installed, o, ...) -> True | False   shows the screen (curses on a terminal, else plain prompts), applies the answers to `o`; False = cancelled

The drawing is a function of the Flow (`Flow.rows`): lists of segments (text, style), a style being a name ("title", "sel", "dim", ...) or a (fg, bg)
pair of '#RRGGBB' for the preview. Curses paints them; the plain mode and the tests read the same text.
"""

import os
import re
import sys

from . import seeds as mgseeds

BACK, CANCEL = "\0back", "\0cancel"
TEXT = "__text__"  # the value of the option that asks for typed text
LOGO_MAP = {
    "both": {"COOKIE": "on", "LOGO": "on"},
    "cookie": {"COOKIE": "on", "LOGO": "off"},
    "none": {"COOKIE": "off", "LOGO": "off"},
}


# ---------------------------------------------------------------- the questions
def _opt(value, label, help=""):
    return {"value": value, "label": label, "help": help}


def _step(id, title, kind, **kw):
    s = {
        "id": id,
        "title": title,
        "kind": kind,
        "help": "",
        "options": [],
        "default": None,
        "part": None,
        "allow_text": False,
        "pattern": None,
        "when": lambda values: True,
        "apply": lambda o, v: None,
        "flags": lambda v: [],
        "settings": lambda v: {},  # conf keys written without a flag of their own
        "show": lambda v: str(v),
    }
    s.update(kw)
    return s


def look_steps(o, current=None):
    """The shared look: the keys every part reads. Only what no flag answered. `current` ({"conf": {...}, "seed": {"mode", "color"}}) pre-fills the answers
    with what is set now, for a person who chose to edit."""
    steps = []
    cur = (current or {}).get("conf") or {}
    cur_seed = (current or {}).get("seed") or {}

    def conf_step(key, title, options, help="", default=None):
        def apply(o_, v):
            o_.look[key] = v

        flag = "--" + key.lower()
        return _step(
            key,
            title,
            "choice",
            help=help,
            options=options,
            default=(cur.get(key) if cur.get(key) in [x["value"] for x in options] else None)
            or default
            or options[0]["value"],
            apply=apply,
            flags=lambda v: [flag, v],
            show=lambda v, opts=options: next((x["label"] for x in opts if x["value"] == v), v),
        )

    if "STYLE" not in o.look:
        steps.append(
            conf_step(
                "STYLE",
                "Style",
                [
                    _opt(
                        "rail",
                        "Full screen with a left rail",
                        "The default: a big hero panel for the selected entry and a rail of icons on the left, grouped Linux | Windows | System.",
                    ),
                    _opt(
                        "clean",
                        "Full screen, no rail",
                        "A big panel per entry, with the previous and next entry peeking in above and below in their own colours.",
                    ),
                    _opt(
                        "list",
                        "Centered list",
                        "The whole menu as a centred list: each entry an icon in a Material shape plus its name in a pill; the selected row is highlighted.",
                    ),
                    _opt(
                        "split",
                        "Split: hero left, list right",
                        "Like the centred list, moved to the right so the distro's big logo and name fill the left half.",
                    ),
                ],
            )
        )
    if "SCHEME" not in o.look:
        steps.append(
            conf_step(
                "SCHEME",
                "Colour scheme",
                [
                    _opt("dark", "Dark", "Deep Material 3 surfaces, easy on the eyes in a dark room."),
                    _opt(
                        "light",
                        "Light",
                        "Light Material 3 surfaces. The scheme is chosen when the images are built, so switching later means installing again.",
                    ),
                ],
            )
        )
    if o.seed is None and o.seed_mode is None:
        opts = [
            _opt(
                "multi",
                "Every entry its own colour",
                "The default: each distro keeps the colour of its brand (Fedora blue, Ubuntu orange, Debian red, ...), so the entries tell apart at a glance.",
            )
        ]
        opts += [
            _opt(h, f"{n}  {h}", "One Material 3 palette for the whole theme, made from this seed colour.")
            for n, h in mgseeds.SEEDS
        ]
        opts.append(_opt(TEXT, "Another colour...", "Type any #RRGGBB."))

        def apply_seed(o_, v):
            if v == "multi":
                o_.seed_mode = "multi"
            else:
                o_.seed, o_.seed_mode = v.upper(), "single"

        steps.append(
            _step(
                "SEED",
                "Colours",
                "choice",
                help="One colour for the whole theme, or every distro in its own colour.",
                options=opts,
                default=(
                    cur_seed.get("color") if cur_seed.get("mode") == "single" and cur_seed.get("color") else "multi"
                ),
                allow_text=True,
                pattern=mgseeds.HEX.pattern,
                apply=apply_seed,
                flags=lambda v: ["--seed-mode", "multi"] if v == "multi" else ["--seed", v.upper()],
                show=lambda v: "every entry its own colour" if v == "multi" else f"one seed colour {v.upper()}",
            )
        )
    if "COOKIE" not in o.look and "LOGO" not in o.look:

        def apply_logo(o_, v):
            o_.look.update(LOGO_MAP[v])

        steps.append(
            _step(
                "LOGO",
                "Cookie and firmware logo",
                "choice",
                options=[
                    _opt(
                        "both",
                        "Cookie with the firmware logo",
                        "The cookie shape at the top right with your machine's own boot logo inside it.",
                    ),
                    _opt("cookie", "Cookie only", "The cookie shape without the firmware logo."),
                    _opt("none", "Neither", "No cookie and no logo: the top right stays empty."),
                ],
                default=(
                    "both"
                    if cur.get("COOKIE", "on") == "on" and cur.get("LOGO", "on") == "on"
                    else "cookie"
                    if cur.get("COOKIE", "on") == "on"
                    else "none"
                ),
                apply=apply_logo,
                flags=lambda v: {"both": [], "cookie": ["--no-logo"], "none": ["--no-cookie", "--no-logo"]}[v],
                show=lambda v: {"both": "cookie with the firmware logo", "cookie": "cookie only", "none": "neither"}[v],
            )
        )
    if "HINTS" not in o.look:

        def apply_hints(o_, v):
            o_.look["HINTS"] = v

        steps.append(
            _step(
                "HINTS",
                "Key hints",
                "choice",
                options=[
                    _opt(
                        "on",
                        "Show key hints",
                        "Small pills at the bottom: Arrows select, Enter boot, E edit, C console.",
                    ),
                    _opt("off", "No key hints", "A cleaner screen; the keys keep working."),
                ],
                default=cur.get("HINTS", "on") if cur.get("HINTS") in ("on", "off") else "on",
                apply=apply_hints,
                flags=lambda v: ["--hints"] if v == "on" else ["--no-hints"],
                show=lambda v: "shown" if v == "on" else "hidden",
            )
        )
    return steps


def part_steps(part, o, current=None):
    """A part's own questions, from its manifest (`install.questions`)."""
    steps = []
    for q in part.questions:
        tgt = q["target"]
        if "option" in tgt:
            name = tgt["option"]
            if name in o.part_opts.get(part.name, {}) or any(n == name for n, _ in o.raw_part):
                continue  # a flag already answered it
        elif tgt["conf"] in o.look:
            continue

        def apply(o_, v, part=part, tgt=tgt, kind=q["kind"]):
            if "option" in tgt:
                if kind == "toggle":
                    if v:
                        o_.part_opts.setdefault(part.name, {})[tgt["option"]] = True
                elif v != "":
                    o_.part_opts.setdefault(part.name, {})[tgt["option"]] = v
            elif kind == "toggle" or v != "":
                o_.look[tgt["conf"]] = ("on" if v else "off") if kind == "toggle" else v

        def flags(v, part=part, tgt=tgt, kind=q["kind"]):
            if "option" not in tgt:
                return []
            name = f"--{part.name}-{tgt['option']}"
            if kind == "toggle":
                return [name] if v else []
            return [name, v] if v != "" else []

        def settings(v, tgt=tgt, kind=q["kind"]):
            if "conf" not in tgt or (kind != "toggle" and v == ""):
                return {}
            return {tgt["conf"]: ("on" if v else "off") if kind == "toggle" else v}

        opts = q["options"]
        if q["kind"] == "toggle":
            opts = [_opt(True, "Yes", ""), _opt(False, "No", "")]
        if q["allow_text"]:
            opts = opts + [_opt(TEXT, "Another value...", "Type it.")]
        default = q["default"]
        curconf = (current or {}).get("conf") or {}
        key = tgt.get("conf")
        if key and key in curconf and curconf[key] != "":  # what is set now (a person who edits starts from it)
            default = (curconf[key] == "on") if q["kind"] == "toggle" else curconf[key]
        steps.append(
            _step(
                f"{part.name}.{q['id']}",
                q["title"],
                "choice" if q["kind"] != "text" else "text",
                help=q["help"],
                options=opts,
                default=default,
                part=part.name,
                allow_text=q["allow_text"],
                pattern=q.get("pattern"),
                apply=apply,
                flags=flags,
                settings=settings,
                show=lambda v, opts=opts: next(
                    (x["label"] for x in opts if x["value"] == v), str(v) if v != "" else "automatic"
                ),
                when=lambda values, part=part: part.name in values.get("parts", []),
            )
        )
    return steps


def parts_step(parts, installed, o):
    """Which parts: skipped when --with, --without or --only chose them."""
    cands = [p for p in parts if p.name != "core" and p.problem is None]
    if not cands or o.with_ or o.without or o.only:
        return None
    fresh = not (set(installed) - {"core"})
    chosen = [p.name for p in cands if p.name in installed or (fresh and p.default)]
    opts = []
    for p in cands:
        note = f"installed {p.version}: will be updated" if p.name in installed else "not installed"
        opts.append(_opt(p.name, p.title, f"{p.summary}  ({note})"))

    def apply(o_, v):
        o_.with_ = [n for n in v]
        o_.without = [p.name for p in cands if p.name not in v]

    return _step(
        "parts",
        "What to install",
        "multi",
        help="Space ticks or unticks, Enter goes on. The core (the shared code and the command) is always installed.",
        options=opts,
        default=chosen,
        apply=apply,
        flags=lambda v: ["--with", ",".join(v)] if v else [],
        show=lambda v: ", ".join(v) if v else "only the core",
    )


def selected_names(parts, installed, o):
    """The parts that will be installed, by the rules of installer.select (the screen only needs the names)."""
    if o.only:
        return {o.only}
    defaults = set() if o.uninstall or o.with_ else {p.name for p in parts if p.default and p.problem is None}
    chosen = set(installed) if installed else defaults
    return (chosen | set(o.with_)) - set(o.without) - {"core"}


KEEP_EDIT = "keep_edit"


def keep_edit_step():
    """On a machine that is set up already: keep what is there, or go through the questions with the current answers filled in."""
    return _step(
        KEEP_EDIT,
        "Your current look and settings",
        "choice",
        help="They are kept unless you choose to edit them here. Anything can be changed later in the editor.",
        options=[
            _opt("keep", "Keep my current look and settings", "Nothing about the look is asked or changed."),
            _opt(
                "edit",
                "Edit them now",
                "Style, colours, cookie and logo, hints and each part's questions, starting from what is set now.",
            ),
        ],
        default="keep",
        flags=lambda v: [],
        show=lambda v: "kept" if v == "keep" else "edited now",
    )


def build_steps(parts, installed, o, force=False, current=None):
    """-> the steps in order. Fresh machine (or --tui): which parts, the look, each part's questions. A machine that is set up already: which parts, then ONE
    question (keep or edit) and, only if the answer is edit, the same questions with the current answers filled in; a part that is new to the machine always
    asks its own."""
    updating = not force and bool(set(installed) - {"core"})
    editing = lambda values: values.get(KEEP_EDIT) == "edit"  # noqa: E731
    steps = []
    ps = parts_step(parts, installed, o)
    if ps:
        steps.append(ps)
    look = look_steps(o, current)
    if updating and look:
        steps.append(keep_edit_step())
    for st in look:
        if updating:
            st["when"] = editing
        steps.append(st)
    for p in parts:
        if p.name == "core":
            continue
        for st in part_steps(p, o, current):
            q = next(x for x in p.questions if f"{p.name}.{x['id']}" == st["id"])
            known = p.name in installed
            if q["when"] == "always" or not known:
                steps.append(st)  # a part new to the machine, or a question that is always asked
            elif updating:
                if not any(x["id"] == KEEP_EDIT for x in steps):
                    steps.append(keep_edit_step())
                inner = st["when"]
                st["when"] = lambda values, inner=inner: editing(values) and inner(values)
                steps.append(st)
            else:
                steps.append(st)  # --tui on an update: the whole screen
    return steps


# ---------------------------------------------------------------- what is there already, and where to go next
def _record_version(entry):
    return entry.get("version") if isinstance(entry, dict) else entry


def existing_lines(parts, installed, record=None):
    """What Material Boot already has on this system, for the top of the screen: one line per part that is installed, with its version and what this run
    would do to it, or one line saying there is nothing yet."""
    record = record or {}
    out = []
    for p in parts:
        if p.name == "core" or p.name not in installed:
            continue
        have = _record_version(record.get(p.name))
        if not have or str(have) in ("?", ""):
            out.append(f"{p.title}: installed (this run brings {p.version})")
            continue
        try:
            from .plugins import version_tuple

            order = (version_tuple(str(have)) > version_tuple(p.version)) - (
                version_tuple(str(have)) < version_tuple(p.version)
            )
        except Exception:
            order = 0 if str(have) == p.version else -1
        what = (
            "will be updated"
            if order < 0
            else "the same version: it will be installed again"
            if order == 0
            else "NEWER than this one: it will not be downgraded"
        )
        out.append(f"{p.title} {have}: {what}" + (f" to {p.version}" if order < 0 else ""))
    core = _record_version(record.get("core"))
    if out and core:
        out.append(f"Your settings (look, colours, entries, presets) are kept. The core is {core}.")
    return out or ["Nothing from Material Boot is installed yet."]


def after_lines(selected=()):
    """Where to customise further once it is installed (shown in the summary and after the install)."""
    lines = [
        "material-boot core colour       one seed colour for everything, or a colour per entry",
        "material-boot core overrides    names, colours and icons of single entries, their order and which are hidden",
        "material-boot core presets      save the look under a name, apply it again, move it to another machine",
        "material-boot core conf         the shared settings (countdown, timeout, hints, Plymouth bar and motion ...)",
    ]
    if not selected or "grub" in selected:
        lines.append(
            "material-grub gui               the graphical editor with a live preview of all of it (if you installed it:"
        )
        lines.append("                                run this installer again, or `--grub-with-gui`)")
    lines.append(
        "./install.sh --tui              this screen again with every look question, on a machine that is set up already"
    )
    return lines


# ---------------------------------------------------------------- the state machine
def default_value(s):
    if s["kind"] == "multi":
        return list(s["default"] or [])
    if s["kind"] == "text":
        return s["default"] or ""
    return s["default"]


class Flow:
    """One run of the screen. `key(k)` takes a key name: up down left right enter space esc backspace quit, or a printable character; returns None,
    "done" (confirmed) or "cancel". `rows(w, h)` is what to draw."""

    def __init__(self, steps, o=None, parts_selected=None, found=None):
        self.steps = steps
        self.found = list(found or [])
        self.values = {s["id"]: default_value(s) for s in steps}
        if "parts" not in self.values:
            self.values["parts"] = sorted(parts_selected or [])
        self.i = 0
        self.cur = {}
        self.edit = None  # the text being typed, or None
        self.error = ""
        self.o = o

    # -- which steps are there now
    def visible(self):
        return [s for s in self.steps if s["when"](self.values)]

    def current(self):
        v = self.visible()
        return v[self.i] if self.i < len(v) else None  # None = the summary

    def cursor(self, s):
        if s is None:
            return self.cur.get("\0summary", 0)
        if s["id"] not in self.cur:
            val = self.values.get(s["id"])
            opts = s["options"]
            idx = next((n for n, x in enumerate(opts) if x["value"] == val), None)
            if idx is None and s["allow_text"] and val not in (None, ""):
                idx = len(opts) - 1  # a typed value sits on the "Another ..." option
            self.cur[s["id"]] = idx or 0
        return self.cur[s["id"]]

    def set_cursor(self, s, n):
        self.cur["\0summary" if s is None else s["id"]] = n

    # -- keys
    def key(self, k):
        s = self.current()
        if self.edit is not None:
            return self._edit_key(s, k)
        if k in ("quit", "q"):
            return "cancel"
        if k in ("esc", "left", "b"):
            if self.i == 0:
                return "cancel" if k == "esc" else None
            self.i -= 1
            self.error = ""
            return None
        if s is None:
            return self._summary_key(k)
        n = len(s["options"])
        if s["kind"] == "text":
            self.edit = self.values[s["id"]] or ""
            return self._edit_key(s, k) if k not in ("enter", "right") else None
        cur = self.cursor(s)
        if k in ("up", "k"):
            self.set_cursor(s, (cur - 1) % n)
        elif k in ("down", "j"):
            self.set_cursor(s, (cur + 1) % n)
        elif k == "space" and s["kind"] == "multi":
            v = s["options"][cur]["value"]
            sel = self.values[s["id"]]
            self.values[s["id"]] = [x for x in sel if x != v] if v in sel else sel + [v]
        elif k in ("enter", "right"):
            if s["kind"] == "choice":
                v = s["options"][cur]["value"]
                if v == TEXT:
                    self.edit = ""
                    return None
                self.values[s["id"]] = v
            self._advance()
        return None

    def _advance(self):
        self.i += 1
        self.error = ""
        if self.current() is None:
            self.set_cursor(None, 0)  # the summary starts on Install

    def _edit_key(self, s, k):
        if k == "enter":
            text = self.edit.strip()
            pat = s["pattern"]
            if pat and text != "" and not re.match(pat if pat.endswith("$") else pat + "$", text):
                self.error = f"'{text}' is not valid here"
                return None
            if s["kind"] == "choice" and text == "":
                self.error = "type a value, or Esc to go back"
                return None
            self.values[s["id"]] = text
            self.edit = None
            self._advance()
        elif k == "esc":
            self.edit, self.error = None, ""
        elif k == "backspace":
            self.edit = self.edit[:-1]
        elif len(k) == 1 and k.isprintable():
            self.edit += k
        elif k == "space":
            self.edit += " "
        return None

    def _summary_key(self, k):
        cur = self.cursor(None)
        if k in ("up", "k"):
            self.set_cursor(None, (cur - 1) % 3)
        elif k in ("down", "j"):
            self.set_cursor(None, (cur + 1) % 3)
        elif k in ("enter", "right"):
            if cur == 0:
                return "done"
            if cur == 1:
                self.i = max(0, self.i - 1)
            else:
                return "cancel"
        return None

    # -- what the answers mean
    def apply(self, o):
        for s in self.visible():
            s["apply"](o, self.values[s["id"]])

    def flags(self):
        out = []
        for s in self.visible():
            out += s["flags"](self.values[s["id"]])
        return out

    def summary(self):
        rows = []
        for s in self.visible():
            rows.append((s["title"], s["show"](self.values[s["id"]])))
        return rows

    def settings(self):
        out = {}
        for s in self.visible():
            out.update(s["settings"](self.values[s["id"]]))
        return out

    def command(self):
        return " ".join(["material-boot core install", *self.flags()])

    # -- what to draw
    def rows(self, w=80, h=24, color=True):
        """-> a list of rows, each a list of (text, style). Styles: title, dim, sel, ok, warn, key, or ('#fg', '#bg') for the preview."""
        s = self.current()
        vis = self.visible()
        n = len(vis) + 1
        rows = [[("Material Boot installer", "title"), (f"   step {min(self.i + 1, n)} of {n}", "dim")], []]
        if s is None:
            return rows + self._summary_rows(w)
        rows.append([(s["title"], "title")])
        if self.i == 0 and self.found:
            rows += [[("  On this system:", "dim")]] + [[("    " + ln, "item")] for ln in self.found] + [[]]
        if s["help"]:
            rows += [[(ln, "dim")] for ln in wrap(s["help"], w - 4)]
        rows.append([])
        vals = dict(self.values)
        if s["id"] in ("STYLE", "SCHEME", "SEED") and s["options"]:
            hv = s["options"][self.cursor(s)]["value"]  # the preview follows the highlighted option
            if hv != TEXT:
                vals[s["id"]] = hv
        prev = (
            preview_rows(vals, s) if color else []
        )  # the drawing is made of coloured half blocks: without 256 colours it would be noise
        if prev and w >= 100:
            pw = max(sum(len(t) for t, _ in r) for r in prev)
            lw = w - pw - 6  # the questions keep to the left of the drawing
            left = self._option_rows(s, lw, max(6, h - len(rows) - 5))
            for k in range(max(len(left), len(prev))):
                a = left[k] if k < len(left) else []
                pad = max(2, lw - sum(len(t) for t, _ in a) + 2)
                rows.append(a + [(" " * pad, "dim")] + (prev[k] if k < len(prev) else []))
        else:
            rows += self._option_rows(s, w, max(6, h - len(rows) - 5 - (len(prev) + 1 if prev and h >= 30 else 0)))
            if prev and h >= 30:
                rows += [[]] + prev
        if self.edit is not None:
            rows += [[], [("  > ", "key"), (self.edit + "_", "sel")]]
        if self.error:
            rows += [[("  " + self.error, "warn")]]
        rows += [[], [(self.footer(s), "dim")]]
        return rows

    def footer(self, s):
        if self.edit is not None:
            return "type, Enter to accept, Esc to cancel"
        if s["kind"] == "multi":
            return "Up/Down move  Space tick  Enter next  Esc back  q quit"
        return "Up/Down move  Enter select  Esc back  q quit"

    def _option_rows(self, s, w, avail=None):
        """The options as rows; with `avail` lines at most, a window that follows the cursor (with a marker when something is cut off)."""
        rows, first = [], 0
        cur = self.cursor(s)
        val = self.values.get(s["id"])
        typed = [o_["value"] for o_ in s["options"]]
        for n, x in enumerate(s["options"]):
            on = (val == x["value"]) if s["kind"] != "multi" else x["value"] in val
            mark = ("[x]" if on else "[ ]") if s["kind"] == "multi" else ("(*)" if on else "( )")
            label = x["label"]
            if x["value"] == TEXT and s["allow_text"] and val not in (None, "") and val not in typed:
                label = f"{x['label']} {val}"
            st = "sel" if n == cur else "item"
            row = [(f" {'>' if n == cur else ' '} {mark} ", st)]
            if str(x["value"]).startswith("#") and mgseeds.HEX.match(x["value"]):
                row.append(("\u2588\u2588", (x["value"], x["value"])))  # a chip of the colour
                row.append((" ", st))
            row.append((label[: max(10, w - 14)], st))
            if n == cur:
                first = len(rows)
            rows.append(row)
            if n == cur and x["help"] and s["kind"] != "text":
                rows += [[("        " + ln, "dim")] for ln in wrap(x["help"], max(20, w - 10))]
        if avail is not None and len(rows) > avail:
            start = max(0, min(first - avail // 3, len(rows) - avail))
            cut = rows[start : start + avail]
            if start > 0:
                cut[0] = [("   ... more above", "dim")]
            if start + avail < len(rows):
                cut[-1] = [("   ... more below", "dim")]
            rows = cut
        return rows

    def _summary_rows(self, w):
        rows = [[("Ready to install", "title")], []]
        if self.found:
            rows += [[("  On this system:", "dim")]] + [[("    " + ln, "item")] for ln in self.found] + [[]]
        for t, v in self.summary():
            rows.append([(f"  {t + ':':<28}", "dim"), (v, "item")])
        rows += [[], [("The same thing without this screen:", "dim")]]
        rows += [[("  " + ln, "key")] for ln in wrap(self.command(), w - 4)]
        if self.settings():
            rows += [
                [
                    (
                        "  and in /etc/material-grub.conf: " + " ".join(f"{k}={v}" for k, v in self.settings().items()),
                        "dim",
                    )
                ]
            ]
        rows += [[], [("After the install, more customisation:", "dim")]]
        rows += [[("  " + ln, "dim")] for ln in after_lines(self.values.get("parts"))]
        rows.append([])
        for n, label in enumerate(("Install", "Back", "Cancel")):
            rows.append(
                [(f" {'>' if n == self.cursor(None) else ' '} {label}", "sel" if n == self.cursor(None) else "item")]
            )
        rows += [[], [("Nothing has been changed yet.", "dim")]]
        return rows


def wrap(text, width):
    out = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split():
            if line and len(line) + 1 + len(word) > width:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        out.append(line)
    return out


# ---------------------------------------------------------------- the preview
PREVIEW_W, PREVIEW_H = 30, 16  # pixels; two pixels per terminal row (half blocks)


def _grid(bg):
    return [[bg] * PREVIEW_W for _ in range(PREVIEW_H)]


def _rect(g, x, y, w, h, c):
    for yy in range(max(0, y), min(PREVIEW_H, y + h)):
        for xx in range(max(0, x), min(PREVIEW_W, x + w)):
            g[yy][xx] = c


def mix(a, b, t):
    """'#RRGGBB' a moved t of the way to b: tones between the surface and the text, visible on any scheme."""
    pa, pb = (tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    r, g, b = (round(x + (y - x) * t) for x, y in zip(pa, pb))
    return f"#{r:02X}{g:02X}{b:02X}"


def _box(g, x, y, w, h, fill, line):
    """A panel with a one-pixel outline, so it reads on any scheme (the dark ones are nearly black on black)."""
    _rect(g, x, y, w, h, line)
    _rect(g, x + 1, y + 1, w - 2, h - 2, fill)


def mock_scene(style, roles):
    """A stylised drawing of the chosen style in the chosen colours: the layout of the real theme, not its pixels."""
    g = _grid(roles["surface"])
    pc, tx = roles["primaryContainer"], roles["onSurface"]
    hi, pill, ln = (mix(roles["surface"], tx, t) for t in (0.10, 0.20, 0.32))
    if style == "clean":
        _box(g, 6, 0, 18, 3, hi, ln)
        _box(g, 2, 4, 26, 8, hi, ln)
        _rect(g, 5, 6, 8, 4, roles["primary"])
        _rect(g, 15, 6, 10, 1, tx)
        _rect(g, 15, 8, 7, 1, roles["onSurfaceVariant"])
        _box(g, 6, 13, 18, 3, hi, ln)
    elif style == "list":
        for n in range(5):
            _rect(g, 5, 1 + n * 3, 20, 2, pc if n == 2 else pill)
            _rect(g, 7, 1 + n * 3, 2, 2, roles["primary"] if n != 2 else roles["onPrimaryContainer"])
            _rect(g, 11, 1 + n * 3, 9, 1, tx if n != 2 else roles["onPrimaryContainer"])
    elif style == "split":
        _box(g, 1, 2, 12, 11, hi, ln)
        _rect(g, 4, 4, 6, 5, roles["primary"])
        _rect(g, 3, 10, 8, 1, tx)
        for n in range(4):
            _rect(g, 15, 1 + n * 4, 14, 3, pc if n == 1 else pill)
            _rect(g, 17, 2 + n * 4, 2, 1, roles["primary"] if n != 1 else roles["onPrimaryContainer"])
            _rect(g, 21, 2 + n * 4, 6, 1, tx if n != 1 else roles["onPrimaryContainer"])
    else:  # rail
        for n in range(4):
            _rect(g, 1, 1 + n * 4, 4, 3, pc if n == 1 else pill)
        _box(g, 7, 1, 22, 13, hi, ln)
        _rect(g, 10, 3, 7, 5, roles["primary"])
        _rect(g, 10, 10, 13, 1, tx)
        _rect(g, 10, 12, 8, 1, roles["onSurfaceVariant"])
    _rect(g, 8, 15, 14, 1, ln)
    return g


def preview_rows(values, step=None):
    """The preview of the look chosen so far, as rows of (text, (fg, bg)) segments; [] when the screen has nothing to show for it."""
    if step is not None and step["id"] not in ("STYLE", "SCHEME", "SEED", "LOGO", "HINTS"):
        return []
    try:
        from . import palette

        seed = values.get("SEED")
        multi = seed in (None, "multi", "")
        style = values.get("STYLE", "rail")
        roles = palette.scheme(mgseeds.DEFAULT if multi else seed, values.get("SCHEME", "dark") != "light")
    except Exception:
        return []
    return grid_rows(mock_scene(style, roles)) + [
        [
            (
                "  " + ("shown in Forest; each entry keeps its own colour" if multi else mgseeds.name_of(seed) or seed),
                "dim",
            )
        ]
    ]


def grid_rows(g):
    rows = []
    for y in range(0, len(g), 2):
        rows.append([("▀", (g[y][x], g[y + 1][x])) for x in range(len(g[0]))])
    return rows


# ---------------------------------------------------------------- drawing
def key_name(code, curses):
    names = {
        curses.KEY_UP: "up",
        curses.KEY_DOWN: "down",
        curses.KEY_LEFT: "left",
        curses.KEY_RIGHT: "right",
        curses.KEY_BACKSPACE: "backspace",
        127: "backspace",
        8: "backspace",
        10: "enter",
        13: "enter",
        curses.KEY_ENTER: "enter",
        27: "esc",
        32: "space",
    }
    if code in names:
        return names[code]
    if 32 < code < 127:
        return chr(code)
    return None


def run_curses(flow):
    """Draw the flow with curses until it is confirmed or cancelled. Returns "done" or "cancel"."""
    import curses

    os.environ.setdefault("ESCDELAY", "25")  # a lone Esc should not wait a second

    def main(scr):
        curses.curs_set(0)
        scr.keypad(True)
        curses.use_default_colors()
        pairs, styles = {}, {}
        big = curses.has_colors() and curses.COLORS >= 256

        def idx(c):
            return mgseeds.xterm256(c) if big else 0

        def attr(style):
            if isinstance(style, tuple):
                if not big:
                    return 0
                key = (style[0], style[1])
                if key not in pairs:
                    if len(pairs) >= curses.COLOR_PAIRS - 10:
                        return 0
                    curses.init_pair(len(pairs) + 20, idx(style[0]), idx(style[1]))
                    pairs[key] = len(pairs) + 20
                return curses.color_pair(pairs[key])
            if style not in styles:
                n = {"title": 1, "sel": 2, "dim": 3, "warn": 4, "key": 5, "item": 6}.get(style, 6)
                if curses.has_colors():
                    fg = {"title": 14, "sel": 0, "dim": 8, "warn": 9, "key": 11, "item": -1}[
                        style if style in ("title", "sel", "dim", "warn", "key", "item") else "item"
                    ]
                    bg = 14 if style == "sel" else -1
                    if not big:
                        fg = {
                            14: curses.COLOR_CYAN,
                            0: curses.COLOR_BLACK,
                            8: curses.COLOR_WHITE,
                            9: curses.COLOR_RED,
                            11: curses.COLOR_YELLOW,
                        }.get(fg, -1)
                        bg = curses.COLOR_CYAN if style == "sel" else -1
                    curses.init_pair(n, fg, bg)
                    styles[style] = curses.color_pair(n) | (curses.A_BOLD if style == "title" else 0)
                else:
                    styles[style] = {"title": curses.A_BOLD, "sel": curses.A_REVERSE, "dim": curses.A_DIM}.get(style, 0)
            return styles[style]

        while True:
            h, w = scr.getmaxyx()
            # curses sends only the cells that changed, which splits the texts a test is waiting for: MATERIAL_BOOT_TUI_REPAINT=1 repaints everything every time
            scr.clear() if os.environ.get("MATERIAL_BOOT_TUI_REPAINT") == "1" else scr.erase()
            if h < 12 or w < 50:
                scr.addstr(0, 0, "Make the terminal bigger (50x12 at least), or q to quit"[: w - 1])
            else:
                rows = flow.rows(w, h, color=big)
                for y, row in enumerate(rows[: h - 1]):
                    x = 1
                    for text, style in row:
                        if not text or x >= w - 1:
                            continue
                        try:
                            scr.addstr(y, x, text[: w - 1 - x], attr(style))
                        except curses.error:
                            pass
                        x += len(text)
            scr.refresh()
            name = key_name(scr.getch(), curses)
            if name is None:
                continue
            r = flow.key(name)
            if r:
                return r

    return curses.wrapper(main)


def run_plain(flow, inp=input, out=print):
    """The same questions as plain prompts (no colours, no curses: a pipe, TERM=dumb, a tiny terminal). Empty answer = the default; `b` = back; `q` = quit."""
    if flow.found:
        out("On this system:")
        for ln in flow.found:
            out("  " + ln)
    while True:
        s = flow.current()
        if s is None:
            out("")
            out("Ready to install:")
            for t, v in flow.summary():
                out(f"  {t}: {v}")
            out("The same thing without this screen:")
            out("  " + flow.command())
            out("After the install, more customisation:")
            for ln in after_lines(flow.values.get("parts")):
                out("  " + ln)
            if flow.settings():
                out("  and in /etc/material-grub.conf: " + " ".join(f"{k}={v}" for k, v in flow.settings().items()))
            try:
                a = inp("Install? [Y/n/b] ").strip().lower()
            except EOFError:
                return "cancel"
            if a in ("", "y", "yes"):
                return "done"
            if a == "b":
                flow.i = max(0, flow.i - 1)
                continue
            return "cancel"
        out("")
        out(f"{s['title']}")
        for ln in wrap(s["help"], 76) if s["help"] else []:
            out("  " + ln)
        default = flow.values[s["id"]]
        if s["kind"] == "text":
            ans = inp(f"  {s['title']} [{default or 'default'}]: ")
        else:
            for n, x in enumerate(s["options"], 1):
                on = (x["value"] in default) if s["kind"] == "multi" else x["value"] == default
                out(f"  {n}) {x['label']}{'  *' if on else ''}")
            ask = (
                "  numbers, comma separated (empty = as marked)"
                if s["kind"] == "multi"
                else "  number (empty = marked *)"
            )
            try:
                ans = inp(ask + ": ")
            except EOFError:
                return "cancel"
        a = ans.strip()
        if a.lower() == "q":
            return "cancel"
        if a.lower() == "b":
            flow.i = max(0, flow.i - 1)
            continue
        if s["kind"] == "text":
            if a:
                if s["pattern"] and not re.match(s["pattern"] if s["pattern"].endswith("$") else s["pattern"] + "$", a):
                    out(f"  '{a}' is not valid here")
                    continue
                flow.values[s["id"]] = a
            flow.i += 1
        elif s["kind"] == "multi":
            if a:
                try:
                    picks = [s["options"][int(x) - 1]["value"] for x in a.replace(",", " ").split()]
                except (ValueError, IndexError):
                    out("  not a list of the numbers above")
                    continue
                flow.values[s["id"]] = picks
            flow.i += 1
        else:
            if a:
                if not a.isdigit() or not 1 <= int(a) <= len(s["options"]):
                    out("  not one of the numbers above")
                    continue
                v = s["options"][int(a) - 1]["value"]
                if v == TEXT:
                    t = inp("  value: ").strip()
                    if not t or (
                        s["pattern"]
                        and not re.match(s["pattern"] if s["pattern"].endswith("$") else s["pattern"] + "$", t)
                    ):
                        out("  not valid here")
                        continue
                    v = t
                flow.values[s["id"]] = v
            flow.i += 1


# ---------------------------------------------------------------- the entry point
def wanted(o, tty=None):
    """Whether to show the screen: on a terminal, for a real install that nobody scripted."""
    if o.tui is False or os.environ.get("MATERIAL_BOOT_TUI") == "0":
        return False
    if o.yes or o.json or o.dry_run or o.from_package or o.uninstall or o.root or o.help:
        return False
    if tty is None:
        tty = sys.stdin.isatty() and sys.stdout.isatty()
    return bool(tty)


def run(parts, installed, o, say=print, inp=input, plain=None, tty=None, record=None, current=None):
    """Ask, apply the answers to `o`. -> True to go on, False when cancelled. Nothing is written here."""
    steps = build_steps(parts, installed, o, force=o.tui is True, current=current)
    if not steps:
        return True
    flow = Flow(steps, o, selected_names(parts, installed, o), existing_lines(parts, installed, record))
    use_plain = plain
    if use_plain is None:
        use_plain = os.environ.get("TERM", "dumb") in ("dumb", "") or not (sys.stdin.isatty() and sys.stdout.isatty())
        if not use_plain:
            try:
                import curses  # noqa: F401
            except ImportError:
                use_plain = True
                say(
                    "(this Python has no curses module, so the questions are plain prompts; openSUSE: zypper install python3-curses)"
                )
    if use_plain:
        r = run_plain(flow, inp, say)
    else:
        try:
            r = run_curses(flow)
        except Exception as e:  # a terminal curses cannot drive: fall back, do not die
            say(f"(the screen could not start: {e}; plain questions instead)")
            r = run_plain(flow, inp, say)
    if r != "done":
        say("nothing changed")
        return False
    flow.apply(o)
    o.confirmed = True  # the summary was the confirmation: the installer does not ask `Continue?` again
    if not use_plain:  # a curses screen leaves nothing behind: what was chosen is written to the scrollback
        say("")
        say("What you chose:")
        for title, value in flow.summary():
            say(f"  {title + ':':<30}{value}")
        if flow.settings():
            say("  also written to the settings: " + " ".join(f"{k}={v}" for k, v in flow.settings().items()))
    return True
