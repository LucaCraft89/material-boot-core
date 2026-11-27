"""The core's own part of an install: the library, the build inputs and the shim in place, and the shared data built for the chosen scheme. stdlib only.

The installer treats the core like any other part (docs/installer.md): this module is its hooks. It is chosen first, every other part needs it, and it is
removed only on request (`--only core`).

  <root>/usr/share/material-boot/lib/material_boot    the library (with a VERSION file next to its modules)
  <root>/usr/share/material-boot/{scripts,assets}     what builds the shared data
  <root>/usr/share/material-boot/data                 palettes.json, classes.json, rules.json, titles.json, subtitles.json, glyphs/, fonts/ (built for SCHEME)
  <root>/usr/share/material-boot/plugins.d            where the parts' manifests go
  <root>/usr/local/bin/material-boot                  the shim (source installs; a package installs /usr/bin/material-boot itself)

A source install copies the files from the bundle (`ctx.source`); a package lays them out itself and only needs the data built (`ctx.how == "package"`).
The data is built on the target, like the theme: it depends on the scheme (palettes.json), so `core apply` rebuilds it when the scheme changed
(refresh_data). Every replacement of a directory is a swap: the new one is built beside the old one and renamed over it, so a failed build leaves the
old data in place.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from material_boot import __version__

PREFIX = "usr/share/material-boot"
SHIM = "usr/local/bin/material-boot"
COPIED = ("lib", "scripts", "assets")  # from the bundle, for a source install
DATA_FILES = ("palettes.json", "classes.json", "rules.json", "titles.json", "subtitles.json", "scheme.txt")


def prefix(root=""):
    return Path(root or "/") / PREFIX


def shim_path(root=""):
    return Path(root or "/") / SHIM


def main(argv, core):
    print("the core's own installer part: run it with `material-boot core install`")
    return 0


def part():
    """The part record the installer uses for the core (the same fields as a manifest's)."""
    me = Path(__file__).resolve()
    return SimpleNamespace(
        name="core",
        title="Material Boot core",
        version=__version__,
        summary="the shared code, the shared data and the material-boot command",
        entry=str(me),
        module=sys.modules[__name__],  # plugins.load hands this back instead of importing a file
        commands={},
        menu=[],
        conf=[],
        hooks=("detect", "plan", "install", "verify", "uninstall"),
        default=True,
        needs=[],
        options=[],
        questions=[],
        layouts=[],
        package="material-boot-core",
        source=None,
        core_min=None,
        path=me,
        problem=None,
        warnings=[],
        shadows=[],
    )


# ---------------------------------------------------------------- helpers
def missing_tools():
    """What the data build needs and this system lacks (sentences with the package names)."""
    out = []
    try:
        import PIL  # noqa: F401
    except ImportError:
        out.append("Pillow (python3-pillow, python3-pil or python-pillow)")
    if not (shutil.which("rsvg-convert") or shutil.which("magick") or shutil.which("convert")):
        out.append("rsvg-convert (librsvg2-tools, librsvg2-bin or librsvg)")
    return out


# What the data build needs, by package manager: Pillow and something that rasterises SVG. (The old Material GRUB installer installed these too.)
DEP_COMMANDS = {
    "dnf": [["dnf", "install", "-y", "python3-pillow", "librsvg2-tools"]],
    "apt-get": [["apt-get", "update"], ["apt-get", "install", "-y", "python3-pil", "librsvg2-bin"]],
    "pacman": [["pacman", "-S", "--needed", "--noconfirm", "python-pillow", "librsvg"]],
    "zypper": [["zypper", "--non-interactive", "install", "python3-Pillow", "rsvg-convert"]],
    "apk": [["apk", "add", "py3-pillow", "rsvg-convert"]],
    "xbps-install": [["xbps-install", "-Sy", "python3-Pillow", "librsvg-utils"]],
}


def install_missing_tools(root="", runner=None, env=None):
    """Install what `missing_tools()` reports with the system's package manager. Returns (True, sentence) when nothing is missing afterwards, else (False, why).
    Only on the real system: a staged root has no package manager to ask, and a distribution package declares its dependencies itself."""
    runner = runner or subprocess.run
    if root:
        return False, "a staged root: nothing is installed"
    pm = next((m for m in DEP_COMMANDS if shutil.which(m)), None)
    if pm is None:
        return False, "no supported package manager was found (dnf, apt-get, pacman, zypper, apk, xbps-install)"
    env = dict(os.environ if env is None else env, DEBIAN_FRONTEND="noninteractive")
    for cmd in DEP_COMMANDS[pm]:
        if runner(cmd, env=env).returncode != 0:
            return False, f"`{' '.join(cmd)}` failed"
    import importlib

    importlib.invalidate_caches()
    left = missing_tools()
    if left:
        return False, "still missing for this Python (" + sys.executable + "): " + ", ".join(left)
    return True, f"installed the build dependencies with {pm}"


def swap_dir(new, dst):
    """Put the directory `new` in place of `dst`; the old one is kept until the new one is there, and put back if the rename fails."""
    new, dst = Path(new), Path(dst)
    old = dst.with_name(dst.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if dst.exists():
        os.replace(dst, old)
    try:
        os.replace(new, dst)
    except BaseException:
        if old.exists():
            os.replace(old, dst)
        raise
    shutil.rmtree(old, ignore_errors=True)


def copy_dir(src, dst):
    dst = Path(dst)
    new = dst.with_name(dst.name + ".new")
    if new.exists():
        shutil.rmtree(new)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, new, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    swap_dir(new, dst)


def write_file(src, dst, mode):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".new")
    shutil.copyfile(src, tmp)
    os.chmod(tmp, mode)
    os.replace(tmp, dst)


def build_data(root, scheme):
    """Build the shared data into data.new and swap it in. Raises RuntimeError with what the build said when it fails (the old data stays)."""
    p = prefix(root)
    new = p / "data.new"
    if new.exists():
        shutil.rmtree(new)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(p / "lib"), os.environ.get("PYTHONPATH", "")]))
    r = subprocess.run(
        [sys.executable, str(p / "scripts/build_data.py"), "--out", str(new), "--scheme", scheme],
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode:
        shutil.rmtree(new, ignore_errors=True)
        lines = [x for x in (r.stderr or r.stdout).strip().splitlines() if x.strip()]
        raise RuntimeError("building the shared data failed: " + (lines[-1] if lines else f"status {r.returncode}"))
    swap_dir(new, p / "data")


def scheme_of(ctx):
    s = (ctx.conf or {}).get("SCHEME")
    return s if s in ("dark", "light") else "dark"


def data_scheme(root=""):
    try:
        return (prefix(root) / "data/scheme.txt").read_text().strip()
    except OSError:
        return None


def refresh_data(root="", scheme=None):
    """Rebuild the shared data when it was built for another scheme (called by `core apply`). Returns a sentence, or None when nothing was needed or
    possible (the build inputs are not installed)."""
    p = prefix(root)
    if scheme not in ("dark", "light") or not (p / "scripts/build_data.py").is_file() or data_scheme(root) == scheme:
        return None
    gone = missing_tools()
    if gone:
        return (
            "the shared data is for the "
            + str(data_scheme(root))
            + f" scheme but {scheme} is set, and cannot be rebuilt: missing {', '.join(gone)}"
        )
    build_data(root, scheme)
    return f"rebuilt the shared data for the {scheme} scheme"


# ---------------------------------------------------------------- the hooks
def installed_version(root=""):
    try:
        return (prefix(root) / "lib/material_boot/VERSION").read_text().strip() or None
    except OSError:
        return None


def hook_detect(ctx):
    p = prefix(ctx.root)
    if not (p / "lib/material_boot").is_dir():
        return {"found": False}
    gone = [d for d in COPIED if not (p / d).is_dir()]
    gone += [f"data/{f}" for f in DATA_FILES if not (p / "data" / f).is_file()]
    if ctx.how != "package" and not shim_path(ctx.root).is_file():
        gone.append("command")
    how = "unknown"
    if not ctx.root:
        from material_boot import state

        how = state.owner_of(p / "lib/material_boot/__init__.py")
    return {"found": True, "version": installed_version(ctx.root), "how": how, "missing": gone}


def hook_plan(ctx):
    p = prefix(ctx.root)
    out = []
    if ctx.how != "package" and ctx.source:
        out.append(f"copy the library, the build scripts and the assets to {p}")
        out.append(f"install the command {shim_path(ctx.root)}")
    out.append(f"build the shared data for the {scheme_of(ctx)} scheme in {p / 'data'}")
    out.append(f"create {p / 'plugins.d'} for the parts' manifests")
    gone = missing_tools()
    if gone:
        out.append(
            "MISSING: "
            + ", ".join(gone)
            + (
                " (installed with the package manager)"
                if ctx.how != "package" and not ctx.root
                else ": install them, the data cannot be built without"
            )
        )
    return out


def hook_install(ctx):
    p = prefix(ctx.root)
    gone = missing_tools()
    notes, copied = [], False
    if gone and not ctx.dry_run and ctx.how != "package":
        ok, what = install_missing_tools(ctx.root)
        if ok:
            notes.append(what)
            gone = []
        else:
            raise RuntimeError(
                "cannot build the shared data, missing: "
                + ", ".join(gone)
                + f" ({what}); install them and run this again"
            )
    if gone:
        raise RuntimeError("cannot build the shared data, missing: " + ", ".join(gone))
    src = Path(ctx.source) if ctx.source else None
    if ctx.how != "package" and src is not None:
        if not (src / "lib/material_boot").is_dir():
            raise RuntimeError(f"{src} has no lib/material_boot: run the installer from a bundle")
        for d in COPIED:
            copy_dir(src / d, p / d)
        (p / "lib/material_boot/VERSION").write_text(__version__ + "\n")
        write_file(src / "bin/material-boot", shim_path(ctx.root), 0o755)
        notes.append(f"installed the library in {p / 'lib'} and the command {shim_path(ctx.root)}")
        copied = True
    (p / "plugins.d").mkdir(parents=True, exist_ok=True)
    scheme = scheme_of(ctx)
    if copied or data_scheme(ctx.root) != scheme or not all((p / "data" / f).is_file() for f in DATA_FILES):
        build_data(ctx.root, scheme)
        notes.append(f"built the shared data for the {scheme} scheme")
    return {"changed": copied or bool(notes), "notes": notes}


def hook_verify(ctx):
    p = prefix(ctx.root)
    problems = []
    if not (p / "lib/material_boot/__init__.py").is_file():
        problems.append(f"{p / 'lib/material_boot'} is missing")
    problems += [f"{p / 'data' / f} is missing" for f in DATA_FILES if not (p / "data" / f).is_file()]
    if not (p / "data/glyphs").is_dir() or not (p / "data/fonts").is_dir():
        problems.append(f"{p / 'data'} has no glyphs or fonts")
    elif data_scheme(ctx.root) != scheme_of(ctx):
        problems.append(f"the shared data is for the {data_scheme(ctx.root)} scheme, not {scheme_of(ctx)}")
    if ctx.how != "package" and ctx.source and not shim_path(ctx.root).is_file():
        problems.append(f"{shim_path(ctx.root)} is missing")
    return problems


def hook_uninstall(ctx):
    p = prefix(ctx.root)
    if ctx.how == "package":
        # the package manager removes the files it owns; what it does not know is what was generated here
        for d in ("data", "data.new", "data.old"):
            shutil.rmtree(p / d, ignore_errors=True)
        # python wrote bytecode caches next to the package's modules when root ran the command; the package manager does not own them, so it could not
        # remove the directories that hold them
        for d in (p / "lib", p / "scripts"):
            for cache in list(d.rglob("__pycache__")):
                shutil.rmtree(cache, ignore_errors=True)
        return {"changed": True}
    for f in (shim_path(ctx.root),):
        try:
            f.unlink()
        except OSError:
            pass
    for d in (*COPIED, "data"):
        shutil.rmtree(p / d, ignore_errors=True)
    try:
        (p / "plugins.d").rmdir()  # only when no part is left in it
        p.rmdir()
    except OSError:
        pass
    return {"changed": True}
