"""Where the editor finds what it needs: the core's shared data (palettes, glyphs, fonts, class tables), the GRUB part's own modules (entry scenes for the preview,
Ventoy sticks) when GRUB is installed, and the state GRUB leaves for it. stdlib only."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
DATA_DIRS = ("usr/share/material-boot/data", "usr/local/share/material-boot/data", "var/lib/material-boot/data")


def data_dir():
    """The shared data directory (palettes.json, classes.json, glyphs/, fonts/ ...): $MATERIAL_DATA, else the installed one. None when it was never built."""
    cands = [os.environ.get("MATERIAL_DATA")] + ["/" + d for d in DATA_DIRS]
    for c in cands:
        if c and (Path(c) / "palettes.json").is_file():
            return Path(c)
    return None


def state_dir():
    """What GRUB's last apply left (entries.json, menu.json): /var/lib/material-grub, $MATERIAL_STATE_DIR moves it."""
    return Path(os.environ.get("MATERIAL_STATE_DIR", "/var/lib/material-grub"))


def grub_modules():
    """The directory of the GRUB part's Python modules (cmd_scenes, ventoy_sticks ...), found through its manifest, or None when GRUB is not installed."""
    from .. import plugins

    env = os.environ.get("MATERIAL_GRUB_MODULES")  # tests, and a checkout of the GRUB part
    if env and (Path(env) / "cmd_scenes.py").is_file():
        return Path(env)
    try:
        rec = plugins.find("grub")
    except Exception:
        return None
    if rec is None or rec.problem or not rec.entry:
        return None
    here = Path(rec.entry).resolve().parent
    for c in (here / "bin", here / "install/bin", here.parent / "bin"):
        if (c / "cmd_scenes.py").is_file():
            return c
    return None


def use_grub_modules():
    """Put the GRUB part's modules on sys.path (once). Returns the directory or None."""
    d = grub_modules()
    if d:
        for c in (d, d.parent):  # a checkout keeps ventoy_sticks.py in install/, the packages next to the others
            if (c / "cmd_scenes.py").is_file() or (c / "ventoy_sticks.py").is_file():
                if str(c) not in sys.path:
                    sys.path.append(str(c))
    return d
