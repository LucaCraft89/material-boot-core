#!/usr/bin/env python3
"""Write docs/material-boot.1, the man page, from the same table as `--help` (material_boot/help.py). CI regenerates it and fails when it differs.
usage: python3 scripts/gen_man.py [--check]"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from material_boot import __version__, help  # noqa: E402

OUT = ROOT / "docs/material-boot.1"


def esc(t):
    return t.replace("\\", "\\\\").replace("-", "\\-").replace("\n.", "\n\\&.")


def options(opts):
    out = []
    for flags, meta, summary in opts:
        shown = ", ".join(f"\\fB{esc(f)}\\fR" for f in flags) + (f" \\fI{esc(meta)}\\fR" if meta else "")
        out += [".TP", shown, esc(summary)]
    return out


def examples(exs):
    out = []
    for cmd, what in exs:
        out += [".TP", f"\\fB{esc(cmd)}\\fR", esc(what)]
    return out


def build():
    o = [
        f'.TH MATERIAL\\-BOOT 1 "" "material-boot {__version__}" "Material Boot"',
        ".SH NAME",
        "material\\-boot \\- the look of your boot menu and boot splash, from one command",
        ".SH SYNOPSIS",
        ".B material\\-boot",
        "[\\fIcommand\\fR] [\\fIoptions\\fR]",
        ".SH DESCRIPTION",
        esc(
            "Material Boot themes the GRUB boot menu and the Plymouth boot splash with one look: a Material 3 palette, a style, per-entry colours, names and icons. "
            "`material-boot` alone opens a menu. The editor (`material-boot ui`) changes everything in your browser with a live preview; the commands below do the same in a terminal."
        ),
        ".SH COMMANDS",
        ".TP",
        "\\fBmaterial\\-boot ui\\fR",
        esc(help.TOP["ui"]["summary"]),
        ".TP",
        "\\fBmaterial\\-boot help\\fR [\\fItopic\\fR]",
        "Everything, or one command (\\fBhelp core install\\fR, \\fBhelp ui\\fR, \\fBhelp grub\\fR).",
        ".TP",
        "\\fBmaterial\\-boot version\\fR",
        "The version of the core and of every installed part.",
    ]
    for c in help.CORE.values():
        o += [".TP", f"\\fBmaterial\\-boot {esc(c['usage'])}\\fR", esc(c["summary"])]
    o += [
        ".TP",
        "\\fBmaterial\\-boot\\fR \\fIpart\\fR \\fIcommand\\fR",
        "A command of an installed part (grub, plymouth). \\fBmaterial\\-boot help\\fR \\fIpart\\fR lists them.",
    ]
    for name, c in help.CORE.items():
        o += [f".SH {name.upper()}", f".B material\\-boot {esc(c['usage'])}", ".PP"]
        if name == "install":
            o += [
                esc(
                    help.wrap("Installs, updates or removes the parts of Material Boot (the core, grub, plymouth, ui).")
                )
            ]
            for title, opts in help.INSTALL_GROUPS:
                o += [f".SS {esc(title)}"] + options(opts)
            o += [".SS Examples"] + examples(help.INSTALL_EXAMPLES)
            continue
        o += [esc(c["text"])]
        if c["options"]:
            o += [".SS Options"] + options(c["options"])
        o += [".SS Examples"] + examples(c["examples"])
    ui = help.TOP["ui"]
    o += (
        [".SH UI", f".B material\\-boot {esc(ui['usage'])}", ".PP", esc(ui["text"]), ".SS Options"]
        + options(ui["options"])
        + [".SS Examples"]
        + examples(ui["examples"])
    )
    o += [
        ".SH FILES",
        ".TP",
        "\\fI/etc/material\\-grub.conf\\fR",
        "The shared settings (style, scheme, ...).",
        ".TP",
        "\\fI/etc/material\\-grub/overrides.json\\fR",
        "Colours, names, icons and order per entry; the pictures are in \\fIicons/\\fR next to it.",
        ".TP",
        "\\fI/var/log/material\\-boot/install.log\\fR",
        "What every install did, with the details.",
        ".TP",
        "\\fI/var/backups/material\\-grub/\\fR",
        "Backups made before anything is changed.",
        ".SH SEE ALSO",
        "https://github.com/LucaCraft89/material\\-boot\\-core",
    ]
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv:
        sys.exit(
            0 if OUT.is_file() and OUT.read_text() == text else f"{OUT} is out of date: run python3 scripts/gen_man.py"
        )
    OUT.write_text(text)
    print(f"wrote {OUT}")
