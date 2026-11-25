# The unified installer (design)

**Status: the framework is implemented** (`material_boot/installer.py`, `detect.py`, `events.py`, tested with fake parts in `tests/test_installer.py`); the bundle builder and the packages are not (C5b, C5c). The decisions below were confirmed by the maintainer: part options as `--<part>-<name>` and bare when unambiguous, no cross-part rollback, package scriptlets calling `material-boot core install --from-package --only <part>`, and the default part set from `install.default`. The contract between the installer and a part is the hooks of [plugins.md](plugins.md) (provisional until this is built); the state record and the migration runner it uses are `material_boot/state.py` and `material_boot/migrate.py`.

## What exists today (material-grub 0.8 / 1.0)

One class, `install/installer.py` (about 1,300 lines), does everything: system check, the existing-install notice, the TUI questions, dependencies, resolution, the scene build, `grub-install`, Ventoy, the optional GUI, `--dry-run`, `--preview`, `--stage-only`, the JSON event stream the GUI reads, and the log. The packages ship the **sources** (`/usr/share/material-grub-src`) and their scriptlets run `install.sh --from-package`, so the theme is built on the target. A source install is `sudo ./install.sh`.

The generic part of that is small (events, log, dry-run, existing-install notice, state record, migrations); the rest is GRUB's and becomes the GRUB part's hooks.

## Shape

```
material-boot core install [--with PART]... [--without PART]... [--only PART] [shared options] [part options]
material-boot core install --uninstall [--only PART]
```

and, for source installs, the bundle's `./install.sh` (a POSIX shell bootstrap that finds Python 3.9+, installing it with the package manager when needed, and runs the same command from the bundle). The bundle is one tarball built by this repository's release CI from the three tagged repositories:

```
material-boot-<version>/
  install.sh  VERSION  SHA256SUMS
  lib/material_boot/  bin/material-boot  data/               the core
  parts/grub/       manifest.json + the part's sources        (material-grub)
  parts/plymouth/   manifest.json + the part's sources        (material-plymouth)
  parts/gui/        ...
```

A part that is not installed yet has no manifest in `plugins.d`, so the installer also reads the manifests in `parts/*/manifest.json` of the bundle. In a manifest, `entry` may be **relative to the manifest's directory** (an installed manifest uses an absolute path, a bundle one cannot know it): `plugins.read_manifest` resolves both.

## The run, in order

1. **System check** (root or sudo, a supported system, the layout: normal or immutable). Generic.
2. **Existing installs.** The state record (`state.read`) plus every part's `hook_detect` give a finding per part. The installer prints one notice (what was found, what will change, where the backup goes), applies the policy per part (refuse a downgrade without `--force`, refuse a source install over package-owned files, adopt a source install by a package) and, in a terminal, asks `Continue? [Y/n]`. `--yes`, `--from-package`, `--progress json` and a dry run do not ask. `Finding`, `notice` and `policy` become generic: they take the product name and package from the part's manifest instead of "Material GRUB" and `material-grub`.
3. **Which parts.** The set is: `--only PART` alone; else the parts that are installed already (an update keeps what is there) plus those chosen with `--with`, minus `--without`, plus the parts whose manifest says `install.default` when nothing is installed yet and nothing is chosen. In a terminal with no choice given, a checklist asks. `install.needs` is followed (`gui` needs `grub`): a needed part that is not selected is added with a line saying so, or the run stops when it was excluded with `--without`.
4. **Shared questions, asked once.** Style, scheme, seed colour and the cookie, logo and hints toggles: they are the keys every part reads (`STYLE`, `SCHEME`, `COOKIE`, `LOGO`, `HINTS` in `/etc/material-grub.conf`, and the seed in `overrides.json`). The installer writes them through `conf.write_conf` and `overrides.save` **before** any part runs, so every part sees the same look. Options that belong to one part (`--res`, `--ventoy`, `--mode`, `--stage-only`, `--pkg`, `--immutable` for GRUB; the command-line edit for Plymouth) are that part's.
5. **Migrations.** The core's steps (`migrate.steps_for`) and each part's `hook_migrate`, backed up and rolled back by the runner that exists.
6. **Plan or install.** With `--dry-run`, every part's `hook_plan(ctx)` is printed and nothing changes. Otherwise parts run **in dependency order**: `hook_install(ctx)`, then `hook_verify(ctx)`, then the state record is updated for that part.
7. **Done.** One summary: what was installed, what changed, what is left to do (reboot, `material-boot core apply`), where the backups are.

`--uninstall` runs `hook_uninstall` in reverse dependency order. The core itself is installed first and removed last; `--without core` does not exist.

## Events

The `--progress json` stream keeps the names the GUI already parses: `step`, `info`, `ok`, `warn`, `error`, `progress`, `log`, `done`, `existing_install`. New fields are added, none are renamed, and a part reports through `ctx.progress(event)`, which the installer tags with the part's name. The log (`open_log`, `LineEvents`, `Tee`) moves as it is.

## Options

- **Generic:** `--with`, `--without`, `--only`, `--yes`, `--dry-run`, `--force`, `--from-package`, `--root DIR` (a staged tree, for tests and packaging), `--progress json`, `--uninstall`, `--keep-build`.
- **Shared look:** `--style`, `--scheme`, `--seed`, `--seed-mode`, `--cookie/--no-cookie`, `--logo/--no-logo`, `--hints/--no-hints`.
- **Part options** are declared in the part's manifest (`install.options`: name, whether it takes a value, one line of help). **Decision (naming):** an option is always accepted as `--<part>-<name>` (`--grub-res 1920x1080`), and also bare (`--res 1920x1080`) when exactly one selected part declares it, so today's commands keep working in the bundle's `install.sh`. An ambiguous bare option is an error that says which prefix to use; two parts that declare the same bare name are reported by `core doctor`. `--help` lists the options of the parts in the bundle.
- `install.layouts` in the manifest lists the layouts a part supports (`["normal"]` for Plymouth, which is not offered on immutable systems yet); the installer refuses with a sentence instead of letting the part fail.

## Failure

**Decision (cross-part rollback): none.** Each part's `hook_install` is already atomic for that part (GRUB's guarded rewrite, Plymouth's backup-and-restore, the migration runner); the installer stops at the first part that fails, leaves the parts that succeeded installed and recorded, and says exactly that:

> Installed: grub. Failed: plymouth (rolled back, nothing of it changed). Not run: gui. Run again to retry the rest.

All-or-nothing across parts would mean uninstalling a working GRUB theme because the splash failed, which is worse for the user than a clear half result, and it needs every part to undo a *completed* install (a different, riskier operation than undoing a failed one). A part whose `hook_install` raises or returns a failure is rolled back by that part; a part that crashes **outside** its guard is the part's bug and is reported as such. Interrupted runs (power loss) follow the rule of the plan: the backup and "old keeps working until the swap" leave the old or the new complete state, `doctor` detects a half state, the next run repairs it.

## Packages

Each package ships its part's sources and installs its manifest. **Decision (scriptlets):** a part's scriptlet calls `material-boot core install --from-package --only <part> --yes`, so a package upgrade and a source install go through the same code (detection, notice, migrations, hooks). material-grub's packages keep calling `install.sh --from-package` until G3 switches them; the core package requires nothing from the parts, and a part requires the core at the same major. A part is never installed by the core's package.

## Tests

- The framework with **fake parts** (done: 40 tests, and seven deliberate breakages of the installer each fail them) (a manifest, an entry file, hooks that record what they were asked): selection rules, `needs`, `--with/--without/--only`, option routing and ambiguity, dry-run changes nothing, failure in the middle (first part kept, second rolled back by itself, third not run), uninstall order, the state record after each part, the JSON event stream against a recorded one.
- A **staged tree** (`--root`) install of the real parts once they register (G2, P2): the matrix of the plan's section 10 (grub only, plymouth only, both, none of the optional parts; upgrade from 0.7.x; uninstall each part).
- material-grub's own installer suites keep running against the GRUB part (the gate in `tests/gate`).

## Open points

- The TUI (`install/tui.py`, 1,100 lines) asks GRUB's questions. The unified one asks which parts and the shared look and lets a part add questions through a future `hook_questions`; until then GRUB's TUI runs inside GRUB's `hook_install` when a terminal is present.
- Ventoy sticks are a GRUB-only mode (`--ventoy`); the stick's version marker and `doctor` warning from the plan are still to do.
- Whether a part's migration steps register through `hook_migrate` or through `migrate.STEPS` (only the core's `ConfSamples` is there today).
