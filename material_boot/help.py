"""The words of `--help`, in ONE place: every command, its options and examples are written here once and everything that explains the command is made from
this table: `material-boot help`, `material-boot <command> --help`, the installer's `--help` and the man page (scripts/gen_man.py). tests/test_help.py
checks that every option the installer accepts is documented, every documented option is accepted, and that every example runs. stdlib only.

An option is (flags, metavar, summary): `flags` are every spelling that is accepted (the first is the one shown first), `metavar` names its value or is "".
"""

PROG = "material-boot"

# ---------------------------------------------------------------- the installer's options (material_boot/installer.py parse_args)
INSTALL_GROUPS = (
    (
        "Which parts",
        [
            (
                ("--with",),
                "PART[,PART]",
                "install these parts too (on a new machine: only these; `ui` is on by default on a desktop)",
            ),
            (("--without",), "PART[,PART]", "leave these parts out (`--without ui` skips the editor's launcher)"),
            (("--only",), "PART", "do only this part (the core is added when it is missing; no other part is touched)"),
        ],
    ),
    (
        "The look (shared by every part; asked on the screen, or given here)",
        [
            (("--style",), "STYLE", "the menu layout: rail, clean, list or split"),
            (("--scheme",), "dark|light", "dark or light colours"),
            (("--seed",), "#RRGGBB", "one seed colour for everything (implies --seed-mode single)"),
            (("--seed-mode",), "multi|single", "multi: a colour per entry; single: one seed colour for all"),
            (("--cookie", "--no-cookie"), "", "the round cookie (logo badge) on the menu"),
            (("--logo", "--no-logo"), "", "the distribution's logo on it"),
            (("--hints", "--no-hints"), "", "the key hints at the bottom"),
        ],
    ),
    (
        "How it runs",
        [
            (
                ("--yes", "-y"),
                "",
                "do not ask: take the defaults and what is given here (also what scripts and packages use)",
            ),
            (
                ("--tui", "--no-tui"),
                "",
                "show the question screen even on a machine that is set up already / never show it",
            ),
            (("--dry-run",), "", "say what would be done and change nothing"),
            (("--force",), "", "install again even when up to date or when a newer version is installed"),
            (
                ("--uninstall",),
                "",
                "remove the chosen parts (the settings in /etc stay); the core goes only with `--only core`",
            ),
            (
                ("-v", "--verbose"),
                "",
                "show the details of every step (the log in /var/log/material-boot has them anyway)",
            ),
            (("-q", "--quiet"), "", "only warnings, errors and the result"),
            (("--progress",), "json", "one JSON event per line on stdout (what the editor reads)"),
        ],
    ),
    (
        "Where from, where to",
        [
            (("--bundle",), "DIR", "the unpacked bundle to install from (default: the one this was started from)"),
            (
                ("--root",),
                "DIR",
                "work on a system staged under DIR (tests, image builds); nothing outside it is touched",
            ),
            (
                ("--from-package",),
                "",
                "what a package's post-install step passes: the files are in place, only the machine-specific part is done",
            ),
            (("--keep-build",), "", "keep the temporary build directory (to debug a failed build)"),
            (("-h", "--help"), "", "this text"),
        ],
    ),
)
INSTALL_EXAMPLES = (
    ("sudo ./install.sh", "the first install (opens the question screen on a terminal)"),
    ("sudo material-boot core install --dry-run", "see what an update would do, change nothing"),
    (
        "sudo material-boot core install --yes --style list --scheme light",
        "no questions: GRUB with the list style, light colours",
    ),
    ("sudo material-boot core install --with plymouth", "add the boot splash"),
    ("sudo material-boot core install --without ui", "install without the editor's launcher"),
    ("sudo material-boot core install --uninstall --only plymouth", "remove only the boot splash"),
    ("sudo material-boot core install --tui", "the question screen again, on a machine that is set up already"),
)

# ---------------------------------------------------------------- the commands
# name -> dict(usage, summary, text (paragraphs), options [(flags, metavar, summary)], examples [(command, what it does)])
CORE = {
    "conf": dict(
        usage="core conf [KEY=VALUE ...]",
        summary="show or change the shared settings (/etc/material-grub.conf)",
        text=(
            "Without arguments it prints every setting and its value. KEY=VALUE changes it (a value that is not allowed is refused and nothing is written). "
            "The settings are shared by every part; the keys are STYLE, SCHEME, COOKIE, LOGO, HINTS, RAW_NAME, COUNTDOWN, TIMEOUT, MODE and the PLYMOUTH_* ones. "
            "Run `apply` afterwards to draw the new look."
        ),
        options=[],
        examples=[
            ("material-boot core conf", "show the settings"),
            ("sudo material-boot core conf STYLE=list HINTS=off", "two changes at once"),
        ],
    ),
    "colour": dict(
        usage="core colour [#RRGGBB | NAME | multi] [--apply]",
        summary="one seed colour for the whole look, or a colour per entry",
        text=(
            "Without arguments it shows the current choice. A colour (#RRGGBB, or one of the preset names such as forest or tangerine) makes every entry use the "
            "Material 3 palette of that one seed; `multi` goes back to a colour per entry. The colour is saved in the overrides file."
        ),
        options=[(("--apply",), "", "apply the look right after saving the colour")],
        examples=[
            ("material-boot core colour", "show the current choice"),
            ("sudo material-boot core colour '#7E57C2' --apply", "lavender everywhere, applied now"),
            ("sudo material-boot core colour multi", "a colour per entry again"),
        ],
    ),
    "presets": dict(
        usage="core presets [list | save NAME | apply NAME [--apply] | delete NAME | export NAME FILE | import FILE]",
        summary="save a look under a name, bring it back, move it to another machine",
        text=(
            "A preset is the shared settings and the overrides (colours, names, icons, order) under one name. `list` is the default. "
            "`export` writes a single file you can copy to another machine and `import` reads it."
        ),
        options=[(("--apply",), "", "with `apply NAME`: apply the look right after loading the preset")],
        examples=[
            ("material-boot core presets", "list the presets"),
            ("sudo material-boot core presets save work", 'keep the current look as "work"'),
            ("sudo material-boot core presets apply work --apply", "bring it back and apply it"),
        ],
    ),
    "overrides": dict(
        usage="core overrides [show | check | path | edit]",
        summary="colours, names and icons per entry, their order and which are hidden",
        text=(
            "The overrides file (/etc/material-grub/overrides.json) holds what you changed about single menu entries. `show` prints it, `check` validates it "
            "(a broken file is ignored at boot, never fatal), `path` prints where it is and `edit` opens it in $EDITOR and validates before saving. "
            "The editor (`material-boot ui`) does the same with pictures."
        ),
        options=[],
        examples=[
            ("material-boot core overrides check", "is the file valid?"),
            ("sudo material-boot core overrides edit", "edit it in $EDITOR"),
        ],
    ),
    "apply": dict(
        usage="core apply [--only PART] [ARGS for the parts]",
        summary="draw the look again: the `apply` of every installed part",
        text=(
            "Rebuilds the shared data when the colour scheme changed, then runs the `apply` command of every installed part that has one, in name order (GRUB: "
            "grub.cfg and the scenes; Plymouth: the splash and the initramfs). One part failing does not stop the others, and the exit status says so. "
            "Anything else on the line is passed on to each part's own apply."
        ),
        options=[(("--only",), "PART", "apply only this part (`core` rebuilds only the shared data)")],
        examples=[
            ("sudo material-boot core apply", "everything"),
            ("sudo material-boot core apply --only grub", "only the boot menu"),
        ],
    ),
    "doctor": dict(
        usage="core doctor",
        summary="the state of the core and of every part",
        text="Checks the core, then each installed part runs its own checks. Nothing is changed. Paste the output into a bug report. The exit status is 1 when something failed.",
        options=[],
        examples=[("material-boot core doctor", "the report")],
    ),
    "parts": dict(
        usage="core parts",
        summary="which parts are installed, and why one cannot be used",
        text="One line per part with its version and whether it is usable; a part that is not usable says why (an incompatible version, a broken manifest).",
        options=[],
        examples=[("material-boot core parts", "the list")],
    ),
    "install": dict(
        usage="core install [OPTIONS]",
        summary="install, update or remove parts",
        text="",  # the installer prints its own, from INSTALL_GROUPS
        options=[],
        examples=[],
    ),
}
TOP = {
    "ui": dict(
        usage="ui [--port N] [--no-browser] [--idle SECONDS]",
        summary="the editor in your browser: every setting of every part, with a live preview",
        text=(
            "Opens the Material Boot editor in your default browser: the boot menu and the boot splash, in one place, with a live preview. It listens on this "
            "computer only (127.0.0.1) with a one-time key in the address, and stops by itself when the tab is closed. Saving asks for your password once "
            "(polkit); nothing is changed before that. The pages are the installed parts': Style, Entries and Ventoy exist with GRUB, Boot splash with Plymouth."
        ),
        options=[
            (("--port",), "N", "listen on port N (default: any free port)"),
            (("--no-browser",), "", "only print the address"),
            (("--idle",), "SECONDS", "stop after this long without a browser (default 120; 0 = never)"),
        ],
        examples=[
            ("material-boot ui", "open the editor"),
            ("material-boot ui --no-browser --port 8765", "only print the address, on a fixed port"),
        ],
    ),
}


def option_lines(options, indent="  ", width=30, total=100):
    """One block per option: the flags in a column, the summary wrapped beside it."""
    import textwrap

    out = []
    for flags, meta, summary in options:
        shown = ", ".join(flags) + (f" {meta}" if meta else "")
        lines = textwrap.wrap(summary, width=max(total - len(indent) - width, 30)) or [""]
        if len(shown) < width:
            out.append(f"{indent}{shown:<{width}}{lines[0]}")
            rest = lines[1:]
        else:
            out.append(f"{indent}{shown}")
            rest = lines
        out += [f"{indent}{'':<{width}}{ln}" for ln in rest]
    return out


def wrap(text, width=78, indent=""):
    import textwrap

    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def install_text(parts=()):
    """`material-boot core install --help`: the options by group, the options the parts declare, examples."""
    out = [
        f"usage: {PROG} core install [OPTIONS]",
        "",
        wrap(
            "Installs, updates or removes the parts of Material Boot (the core, grub, plymouth, ui). With no options on a terminal it shows a screen of questions; with --yes it asks nothing."
        ),
    ]
    for title, options in INSTALL_GROUPS:
        out += ["", f"{title}:"] + option_lines(options)
    opts = [(p, x) for p in parts for x in getattr(p, "options", [])]
    if opts:
        out += ["", "Options of the parts (--PART-NAME always works; plain --NAME when only one chosen part has it):"]
        for p, x in opts:
            meta = "VALUE" if x.get("takes") == "value" else ""
            out += option_lines([((f"--{p.name}-{x['name']}",), meta, x["summary"])], width=34)
    if parts:
        out += ["", "Parts: " + ", ".join(p.name for p in parts)]
    out += ["", "Examples:"]
    for cmd, what in INSTALL_EXAMPLES:
        out += [f"  {cmd}", f"      {what}"]
    out += ["", f"More: {PROG} help"]
    return "\n".join(out)


def command_text(name, table=None):
    """`material-boot core <name> --help` (or `<name> --help` for the top-level ones)."""
    table = table or (CORE if name in CORE else TOP)
    c = table[name]
    scope = "" if table is TOP else ""
    out = [f"usage: {PROG} {c['usage']}", "", c["summary"][0].upper() + c["summary"][1:] + "."]
    if c["text"]:
        out += ["", wrap(c["text"])]
    if c["options"]:
        out += ["", "Options:"] + option_lines(c["options"])
    if c["examples"]:
        out += ["", "Examples:"]
        for cmd, what in c["examples"]:
            out += [f"  {cmd}", f"      {what}"]
    return "\n".join(out) + scope


def wants_help(argv):
    return any(a in ("-h", "--help") for a in argv)


def all_examples():
    """Every example command line in the table (the test runs them)."""
    out = [cmd for cmd, _ in INSTALL_EXAMPLES]
    for table in (CORE, TOP):
        for c in table.values():
            out += [cmd for cmd, _ in c["examples"]]
    return out


def documented_install_flags():
    return {f for _title, options in INSTALL_GROUPS for flags, _m, _s in options for f in flags}
