"""The render snapshot: proof that moving code into material-boot-core changes no pixel.

It runs the real `material-grub-static`, `-classes` and `-scenes` commands on throw-away copies of two real grub.cfg files, over a matrix of style,
colour scheme, cookie, hints and overrides (none, and one with a colour, a name, an icon and a hidden entry), and records a hash of the decoded pixels of
every scene picture plus a hash of the entry state. The result is `golden.json`. It was taken from material-grub's release/0.8.0 BEFORE any module moved;
every pull request that moves code runs this again and must reproduce it exactly.

  python3 tests/snapshot/snapshot.py --bin <dir with the material-grub-* commands> --pkg-dark DIR --pkg-light DIR [--path DIR ...] [--update]

  --bin       material-grub's install/bin (a checkout) or <package>/bin
  --pkg-dark  a built package (scripts/package.py --res 1920x1080), --pkg-light the same built with --scheme light
  --path      extra directories put on PYTHONPATH
  --core      THE GATE for a move: use this repository's modules instead of material-grub's own. A temporary copy of --bin is made with the moved modules
              (MOVED below) replaced by one-line shims that hand out the material_boot module, which is exactly what material-grub's own switch-over
              does. The result must equal golden.json.
  --update    write golden.json instead of comparing

Needs Pillow. Takes a few minutes: it is a matrix of real renders.
"""

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden.json"
ROOT = HERE.parent.parent
# material-grub module -> the material_boot module that replaces it. Grow this list with every module that moves; the gate then covers it.
MOVED = {
    "mgoverrides": "overrides",
    "mgseeds": "seeds",
    "mgpalette": "palette",
    "mgscenes": "scenes",
    "mgcustom": "custom",
}
STYLES = ("rail", "clean", "list", "split")
CFGS = ("fedora", "ubuntu")
OVERRIDES = {
    "none": None,
    "custom": {
        "version": 1,
        "seed": {"mode": "single", "color": "#7B1FA2"},
        "groups": [],
        "order": [],
        "entries": [
            {"match": {"key": "fedora"}, "name": "Work laptop", "color": "#C2185B"},
            {"match": {"key": "ubuntu"}, "icon": "debian"},
            {"match": {"title": "UEFI Firmware Settings"}, "hidden": True},
        ],
    },
}


def cases():
    """(name, cfg, scheme, style, conf, overrides) for the whole matrix."""
    out = []
    for cfg in CFGS:
        for scheme in ("dark", "light"):
            for style in STYLES:
                for ov in OVERRIDES:
                    out.append((f"{cfg}-{scheme}-{style}-cookie-hints-{ov}", cfg, scheme, style, {}, ov))
    for style in STYLES:  # the options that change the drawing, once per style
        out.append(
            (
                f"fedora-dark-{style}-nocookie-nohints-none",
                "fedora",
                "dark",
                style,
                {"COOKIE": "off", "HINTS": "off"},
                "none",
            )
        )
    return out


def pixels(path):
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    h = hashlib.sha256()
    h.update(f"{im.size[0]}x{im.size[1]}".encode())
    h.update(im.tobytes())
    return h.hexdigest()


def run(py, script, *args, env):
    r = subprocess.run([py, str(script), *map(str, args)], env=env, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{script} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")


def render(case, bindir, pkg, paths):
    name, cfg, _scheme, style, conf, ov = case
    d = Path(tempfile.mkdtemp(prefix="snap-"))
    try:
        boot = d / "boot/grub2"
        boot.mkdir(parents=True)
        shutil.copyfile(HERE / "inputs" / f"{cfg}.cfg", boot / "grub.cfg")
        c = {"STYLE": style, "COOKIE": "on", "HINTS": "on", **conf}
        (d / "material-grub.conf").write_text("".join(f"{k}={v}\n" for k, v in c.items()))
        (d / "overrides").mkdir()
        if OVERRIDES[ov] is not None:
            (d / "overrides/overrides.json").write_text(json.dumps(OVERRIDES[ov]))
        env = dict(
            os.environ,
            MATERIAL_CONF=str(d / "material-grub.conf"),
            MATERIAL_OVERRIDES=str(d / "overrides/overrides.json"),
            MATERIAL_STATE_DIR=str(d / "state"),
            PYTHONPATH=os.pathsep.join([*map(str, paths), os.environ.get("PYTHONPATH", "")]),
            MG_PREVIEW_LOGO="0",
        )
        state = d / "state/entries.json"
        py = sys.executable
        run(
            py,
            bindir / "material-grub-static",
            boot / "grub.cfg",
            "--mode",
            "1920x1080",
            "--pkg",
            pkg,
            "--backup",
            d / "backup",
            env=env,
        )
        run(
            py,
            bindir / "material-grub-classes",
            boot / "grub.cfg",
            "--pkg",
            pkg,
            "--state",
            state,
            "--fallback-all",
            env=env,
        )
        run(
            py,
            bindir / "material-grub-scenes",
            "--theme",
            boot / "themes/material",
            "--pkg",
            pkg,
            "--state",
            state,
            env=env,
        )
        out = {"entries.json": hashlib.sha256(state.read_bytes()).hexdigest()}
        for p in sorted((boot / "themes/material/icons").glob("*.png")):
            out[f"icons/{p.name}"] = pixels(p)
        return out
    finally:
        shutil.rmtree(d, ignore_errors=True)


# Modules that were only partly moved: material-grub module -> [(material_boot module, [names that moved])]. The gate rebuilds the original file without those
# definitions and imports them from the core, which is what material-grub's own switch-over does.
PARTIAL = {
    "mgrub": [
        ("conf", ["CONF_DEFAULTS", "CONF_CHOICES", "load_conf", "_conf_ok", "write_conf"]),
        ("titles", ["load_rules", "key_for", "uid", "parse_title", "kind_of"]),
        ("catalog", ["GENERIC"]),
    ],
}


def rebuilt(source, moves):
    """`source` (a module's text) without the top-level definitions named in `moves`, plus an import of them from the core after the docstring."""
    tree = ast.parse(source)
    gone = {n for _mod, names in moves for n in names}

    def defined(node):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            return {node.name}
        if isinstance(node, ast.Assign):
            return {t.id for t in node.targets if isinstance(t, ast.Name)}
        return set()

    kept = [n for n in tree.body if not (defined(n) and defined(n) <= gone)]
    removed = {x for n in tree.body for x in defined(n)} & gone
    if removed != gone:
        raise SystemExit(f"the original no longer defines {sorted(gone - removed)}: update PARTIAL in snapshot.py")
    imports = [ast.parse(f"from material_boot.{mod} import {', '.join(names)}").body[0] for mod, names in moves]
    at = (
        1 if kept and isinstance(kept[0], ast.Expr) and isinstance(getattr(kept[0], "value", None), ast.Constant) else 0
    )
    tree.body = kept[:at] + imports + kept[at:]
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def with_core(bindir):
    """A copy of material-grub's bin directory where every moved module is a shim for the core's. Returns (new dir, temp dir to delete)."""
    tmp = Path(tempfile.mkdtemp(prefix="snap-bin-"))
    new = tmp / "bin"
    shutil.copytree(bindir, new, ignore=shutil.ignore_patterns("__pycache__", "materialyoucolor"))
    for old, mod in MOVED.items():
        (new / f"{old}.py").write_text(
            f"import sys\nfrom material_boot import {mod}\n\nsys.modules[__name__] = {mod}\n"
        )
    for old, moves in PARTIAL.items():
        (new / f"{old}.py").write_text(rebuilt((new / f"{old}.py").read_text(), moves))
    check_gate(new)
    return new, tmp


def check_gate(new):
    """The gate must really be using the core: every moved module is a shim, and every moved definition of a partial module is imported, not defined.
    (A gate that silently runs material-grub's own code would pass everything.)"""
    for old, mod in MOVED.items():
        if f"material_boot import {mod}" not in (new / f"{old}.py").read_text():
            raise SystemExit(f"gate error: {old}.py is not a shim for material_boot.{mod}")
    for old, moves in PARTIAL.items():
        tree = ast.parse((new / f"{old}.py").read_text())
        imported = {a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
        defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        for _mod, names in moves:
            for n in names:
                if n not in imported or n in defined:
                    raise SystemExit(f"gate error: {old}.{n} is not taken from the core")


def main(argv):
    def opt(n, many=False):
        v = [argv[i + 1] for i, a in enumerate(argv) if a == n]
        return v if many else (v[0] if v else None)

    bindir, dark, light = opt("--bin"), opt("--pkg-dark"), opt("--pkg-light")
    if not (bindir and dark and light):
        raise SystemExit(__doc__)
    bindir = Path(bindir)
    paths = [*map(Path, opt("--path", many=True))]
    tmp = None
    if "--core" in argv:
        bindir, tmp = with_core(bindir)
        paths.append(ROOT)
        print(
            f"using the core's {', '.join(MOVED.values())} and, from {', '.join(PARTIAL)}, "
            f"{', '.join(m for ms in PARTIAL.values() for m, _ in ms)} (shims in {bindir})"
        )
    paths.insert(0, bindir)
    only = opt("--only")
    got = {}
    for case in cases():
        if only and only not in case[0]:
            continue
        print(case[0], flush=True)
        got[case[0]] = render(case, bindir, Path(dark if case[2] == "dark" else light), paths)
    import PIL

    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    if "--update" in argv:
        if "--core" in argv:
            raise SystemExit("--update takes the golden from material-grub's own modules, never from the core")
        got["_meta"] = {
            "pillow": PIL.__version__,
            "source": "material-grub release/0.8.0 (29315f7), packages built with scripts/package.py",
        }
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n")
        print(f"wrote {GOLDEN} ({len(got)} cases, {sum(len(v) for v in got.values())} hashes)")
        return 0
    want = json.loads(GOLDEN.read_text())
    meta = want.pop("_meta", {})
    bad = [
        f"{c}/{f}"
        for c, files in got.items()
        for f in sorted(set(files) | set(want.get(c, {})))
        if files.get(f) != want.get(c, {}).get(f)
    ]
    bad += [f"{c}: not rendered" for c in want if c not in got and not only]
    if bad:
        if meta.get("pillow") != PIL.__version__:
            print(
                f"note: the golden was taken with Pillow {meta.get('pillow')}, this is {PIL.__version__}: a different drawing library can change pixels by itself"
            )
        print(f"{len(bad)} differences from golden.json, for example:\n  " + "\n  ".join(bad[:15]))
        return 1
    print(f"identical to golden.json ({len(got)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
