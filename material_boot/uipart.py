"""The editor's own part: the launcher, the helper that saves as root and its polkit policy, so that `material-boot ui` works from the menu of a desktop. stdlib only.

The editor's code is in the library (material_boot/ui, part of the core); this part installs what has to live outside it, in system places:

  <root>/usr/libexec/material-boot-ui-helper                      what pkexec runs (the only thing the editor runs as root)
  <root>/usr/share/polkit-1/actions/org.material-boot.ui.policy   the policy that lets that helper ask for the password
  <root>/usr/share/applications/material-boot.desktop             the one "Material Boot" launcher

It is on by default only on a machine with a graphical session (the editor is a web page, a server has no use for it) and only on the normal layout (an
immutable system has no writable /usr/libexec or polkit directory). `--without ui` leaves it out; `--with ui` forces it. A package ships the same three
files in the same places, so for a package install this part only checks that they are there.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from material_boot import __version__

FILES = (  # (name in the bundle's ui/ directory, where it goes, mode)
    ("material-boot-ui-helper", "usr/libexec/material-boot-ui-helper", 0o755),
    ("org.material-boot.ui.policy", "usr/share/polkit-1/actions/org.material-boot.ui.policy", 0o644),
    ("material-boot.desktop", "usr/share/applications/material-boot.desktop", 0o644),
)
# what 0.7.x put there: the installer lists these as leftovers (WP7); they are not this part's
SESSION_DIRS = ("usr/share/xsessions", "usr/share/wayland-sessions")


def graphical(env=None, root=""):
    """True when this looks like a machine with a desktop: a session in the environment, else a graphical default target, else installed sessions."""
    env = os.environ if env is None else env
    if env.get("DISPLAY") or env.get("WAYLAND_DISPLAY") or env.get("XDG_SESSION_TYPE") in ("x11", "wayland"):
        return True
    r = Path(root or "/")
    try:
        if "graphical" in os.readlink(r / "etc/systemd/system/default.target"):
            return True
    except OSError:
        pass
    for d in SESSION_DIRS:
        try:
            if any((r / d).iterdir()):
                return True
        except OSError:
            pass
    return False


def part(root="", layout="normal", env=None):
    me = Path(__file__).resolve()
    return SimpleNamespace(
        name="ui",
        title="Material Boot editor",
        version=__version__,
        summary="the launcher and the permission for the editor (material-boot ui) in your applications menu",
        entry=str(me),
        module=sys.modules[__name__],
        commands={},
        menu=[],
        conf=[],
        hooks=("detect", "plan", "install", "verify", "uninstall"),
        default=layout == "normal" and graphical(env, root),
        needs=["core"],
        options=[],
        questions=[],
        layouts=["normal"],
        package="material-boot-core",
        source=None,
        core_min=None,
        path=me,
        problem=None,
        warnings=[],
        shadows=[],
    )


def targets(root=""):
    return [(src, Path(root or "/") / dst, mode) for src, dst, mode in FILES]


def hook_detect(ctx):
    here = [d.is_file() for _s, d, _m in targets(ctx.root)]
    if not any(here):
        return {"found": False}
    from material_boot import coreinstall, state

    how = "unknown"
    if not ctx.root:
        how = state.owner_of(targets(ctx.root)[0][1])
    return {
        "found": True,
        "version": coreinstall.installed_version(ctx.root),
        "how": how,
        "missing": [str(d) for _s, d, _m in targets(ctx.root) if not d.is_file()],
    }


def hook_plan(ctx):
    out = []
    if ctx.how != "package" and ctx.source:
        out += [f"install {d}" for _s, d, _m in targets(ctx.root)]
    if not any(Path(p, "pkexec").exists() for p in ("/usr/bin", "/bin")) and not ctx.root:
        out.append("NOTE: pkexec (polkit) is not installed: the editor can look, but saving needs it")
    return out


def hook_install(ctx):
    if ctx.how == "package" or not ctx.source:
        return {"changed": False, "notes": []}
    from material_boot import coreinstall

    notes = []
    for src, dst, mode in targets(ctx.root):
        coreinstall.write_file(Path(ctx.source) / "ui" / src, dst, mode)
    notes.append("installed the editor's launcher, helper and polkit policy")
    return {"changed": True, "notes": notes}


def hook_verify(ctx):
    return [f"{d} is missing" for _s, d, _m in targets(ctx.root) if not d.is_file()]


def hook_uninstall(ctx):
    if ctx.how == "package":
        return {"changed": False}  # the package manager owns the files
    for _s, d, _m in targets(ctx.root):
        try:
            d.unlink()
        except OSError:
            pass
    return {"changed": True}
