#!/usr/bin/env python3
"""The strong gate for a move: material-grub's OWN unit suites, run on a copy of its checkout whose moved modules come from this repository.

  python3 tests/gate/grub_suites.py --grub CHECKOUT [--pkg BUILT_PACKAGE_DIR] [--suites test_upgrade,test_cli,...]

For every suite it runs the unmodified copy first (a baseline: some suites fail in some environments, whatever the code) and then the copy with the moved
modules replaced (tests/gate/moves.py). A suite that passes on the baseline and fails with the core is a regression of the move, and the gate fails;
a suite that fails in both is reported, not blamed on the move. Needs Pillow for the suites that draw (and the built package for those that need one).
`test_gui_server` is never run here: as root its helper writes the real /etc.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import moves  # noqa: E402

SUITES = (
    "mgrub overrides presets palette panel custom customise cli plugins monitors tui ventoy mgtheme grubscript safety dryrun installer doctor preview windows "
    "upgrade pipeline"
).split()


def copy_checkout(grub, pkg, dest):
    ignore = shutil.ignore_patterns(".git", "__pycache__", "screenshots", "build", "dist", ".venv", ".ruff_cache")
    shutil.copytree(grub, dest, ignore=ignore)
    if pkg:
        shutil.copytree(pkg, dest / "dist/material-grub")


def run_suite(tree, name, python, core):
    env = dict(os.environ, MATERIAL_OVERRIDES="/nonexistent/material-grub/overrides.json")
    env["PYTHONPATH"] = os.pathsep.join([str(core), env.get("PYTHONPATH", "")]) if core else env.get("PYTHONPATH", "")
    f = tree / "tests" / f"test_{name}.py"
    if not f.is_file():
        return None, "missing"
    r = subprocess.run([python, str(f)], cwd=tree, env=env, capture_output=True, text=True)
    last = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
    return r.returncode, last[0][:80]


def main(argv):
    def opt(n, d=None):
        return argv[argv.index(n) + 1] if n in argv else d

    grub = opt("--grub")
    if not grub:
        raise SystemExit(__doc__)
    suites = opt("--suites").split(",") if opt("--suites") else SUITES
    tmp = Path(tempfile.mkdtemp(prefix="gate-"))
    try:
        base, core = tmp / "baseline", tmp / "core"
        for t in (base, core):
            copy_checkout(grub, opt("--pkg"), t)
        moves.apply_moves(core / "install/bin")
        print(f"gate: {moves.describe()}")
        regress, both = [], []
        for s in suites:
            rb, mb = run_suite(base, s, sys.executable, None)
            rc, mc = run_suite(core, s, sys.executable, ROOT)
            if rb is None:
                print(f"{s:11s} (no such suite)")
                continue
            verdict = "same" if (rb == 0) == (rc == 0) else "REGRESSION" if rb == 0 else "fixed?"
            print(f"{s:11s} baseline rc={rb} | core rc={rc} | {verdict} | {mc}")
            if verdict == "REGRESSION":
                regress.append(s)
            elif rb != 0:
                both.append(s)
        if both:
            print(f"failing in both (not caused by the move): {', '.join(both)}")
        if regress:
            print(f"REGRESSIONS caused by the move: {', '.join(regress)}")
            return 1
        print("no suite passes on material-grub's own code and fails on the core's")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
