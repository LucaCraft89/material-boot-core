"""The screen against the REAL parts of a built bundle: their manifests' questions are read without warnings, the screen builds from them, answering with
the defaults gives options the installer accepts, and the equivalent command line it prints parses to the same choices.   usage: check_bundle_questions.py BUNDLE_DIR"""

import sys
from pathlib import Path

bundle = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(bundle / "lib"))

from material_boot import installer, plugins, tui  # noqa: E402

parts = plugins.discover_bundle(bundle)
by = {p.name: p for p in parts}
fail = []
for p in parts:
    print(f"{p.name} {p.version}: {len(p.questions)} questions, {len(p.warnings)} warnings, problem: {p.problem}")
    if p.warnings or p.problem:
        fail.append(f"{p.name}: warnings {p.warnings} problem {p.problem}")
    if plugins.version_tuple(p.version) >= (1, 1, 0) and p.name in ("grub", "plymouth") and not p.questions:
        fail.append(f"{p.name} {p.version} asks nothing on the screen")
all_parts = [installer.coreinstall.part(), *parts]
o, errors = installer.parse_args(["--with", ",".join(by)], all_parts)
assert not errors, errors
steps = tui.build_steps(all_parts, set(), o)
flow = tui.Flow(steps, o, tui.selected_names(all_parts, set(), o))
ids = [s["id"] for s in flow.visible()]
print("steps:", ", ".join(ids))
for q in (q for p in parts for q in p.questions):
    if f"{[p.name for p in parts if q in p.questions][0]}.{q['id']}" not in ids:
        fail.append(f"the question {q['id']} is not on the screen")
flow.apply(o)
cmd = flow.command().split()[3:]
o2, errors = installer.parse_args(cmd, all_parts)
if errors:
    fail.append(f"the printed command line is refused: {errors}: {cmd}")
else:
    for k in ("STYLE", "SCHEME", "HINTS", "COOKIE", "LOGO"):
        if o2.look.get(k) != o.look.get(k) and not (
            k in ("COOKIE", "LOGO") and o2.look.get(k) is None and o.look.get(k) == "on"
        ):
            fail.append(f"the printed command line gives {k}={o2.look.get(k)}, the screen {o.look.get(k)}")
    if (o2.seed, o2.seed_mode) != (o.seed, o.seed_mode):
        fail.append("the printed command line gives another seed colour")
print("equivalent command:", flow.command())
if fail:
    print("FAIL:\n  " + "\n  ".join(fail))
    sys.exit(1)
print("ALL OK")
