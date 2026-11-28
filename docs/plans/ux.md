# One product, one way in: how a person installs and uses Material Boot

**Status: decided by the maintainer on 2026-11-28 (section 6); no code yet.** Written after the first real runs of 1.1.x on a Fedora 45 machine (an update from 0.7.1), whose owner said: it is a mess of different TUIs, the old `material-grub` command and launcher icon are still there, the web editor is gone, GRUB asked nothing while Plymouth asked questions, and customisation should be in one place: the web editor, after the install. That is right, and it is the result of building the parts one at a time. This plan starts from what a person sees.

## 1. What a person sees today (honestly)

**Installing (`./install.sh` from the bundle), four voices in three formats:**
1. A full-screen curses screen (parts, look, questions). It leaves **nothing in the scrollback**, so afterwards there is no record of what was chosen or what was found.
2. Plain text from the core: `== Existing install`, `== The look`.
3. Material GRUB's **own installer banner and six steps** (`[1/6] Checking the system ...`), printed by the engine the GRUB part runs.
4. Plymouth's own lines, then a closing `Installed: ...`.

**The questions are inconsistent.** The look and a part's questions are asked only on a *fresh* install (so an update asks about a new part, Plymouth, and nothing about GRUB). To the person that looks arbitrary.

**Using it afterwards, five ways in:** `material-boot` (a curses menu), `material-grub` (the older front end with its **own** menu and its own `help`), `material-grub-*` helper scripts, `material-boot grub|plymouth ...` module commands, and `material-grub gui` (the web editor) with its own desktop icon. The editor is **not known to `material-boot`**: it is not a part, has no command and is not in the menu, so after a move to `material-boot` it looks like it vanished.

**Old installs are not cleaned.** The `material-grub` command, the "Material GRUB" launcher icon and the 0.7.x editor files stay (the command on purpose: hooks, the path unit and the polkit helper call it; the icon and the old editor tree because nothing removes them). An old editor may even be running against a newer core.

**`--help` is partial**: some commands list their options, the installer's options are scattered (`--grub-*`, `--plymouth-*`, bare names), and nothing checks the help against the options that exist.

## 2. Principles

1. **One name, one door.** `material-boot` is the product and the only thing a person has to remember.
2. **The installer sets you up, once, and asks the same way every time.** It asks which parts, and the initial look (style, scheme, colour, cookie and logo, the parts' own questions). On a machine that is set up already it first asks **"Keep your current look and settings, or edit them now?"** (default: keep). It never decides by itself that a question is not worth asking.
3. **After the install, customising has one home: the web editor**, with a live preview, for GRUB and Plymouth together. A terminal route exists for machines without a browser, and it is fully documented.
4. **One voice in the terminal**: one progress view, one style for headings and results, and a record that stays on screen.
5. **Upgrades clean up after themselves**: what an older layout left behind is found, listed, backed up and removed (or replaced), never silently kept.
6. **Help is generated from the same table as the options**, and a test fails when they differ.

## 3. The design

### 3.1 Installing
`./install.sh` (or a package) is **two screens and one progress view**:
1. **What to install and what is here.** The parts (GRUB, Plymouth, the Editor) with what is installed already, its version and what the run will do, plus the few system choices (an immutable system, a Ventoy stick).
2. **The look**, the same questions the screen asks today (style, scheme, seed colour or one per entry, cookie and logo, hints) and each part's own (resolution, countdown, timeout, Plymouth bar and motion), with the preview. **Fresh machine: asked.** **Already set up: one question first, "Keep your current look and settings, or edit them now?"**, and only if the answer is *edit* do the questions follow, pre-filled with what is set. A part that is new to the machine always asks its own questions.
3. **Progress, one view for all parts.** The core already can consume a part's progress as events (`--progress json` is what the editor reads); GRUB's engine and Plymouth report through it and the core draws it: `Step 3 of 7, Rendering the theme`, with the log kept below. The engine's own banner is not shown.
4. **A closing screen that stays in the scrollback**: what was installed or changed, what was found and removed from an older install (3.4), and the next step: *"Customise further in your browser: `material-boot ui`"*, with an "open it now?" when a graphical session is detected.

Non-interactive stays as it is: `--yes`, `--dry-run`, `--no-tui`, `--progress json`, the options per part. `--tui` is no longer needed (the screen always asks, by the rule above). The summary still prints the equivalent command line.

### 3.2 Using it
- **`material-boot`** with no arguments: a short status (what is installed, health in one line, whether the editor is available) and a menu: *Open the editor*, *Health check*, *Apply changes*, *Update*, *Parts*, and, for terminal-only use, *Colour*, *Entries (names, colours, icons)*, *Presets*, *Settings*. One menu, with the style of the installer screens.
- **`material-boot ui`** opens the editor (starts its local server, opens the browser, prints the address when there is no browser).
- **`material-boot <module> <command>`** for scripts: `core` (shared), `grub`, `plymouth`, `ui`. `material-boot help [module [command]]` and `--help` everywhere.
- **`material-grub` is removed** (decided). It is a breaking change, so it belongs to a major release (section 5). Before it goes, everything that calls it moves to `material-boot`: the GRUB hooks (`05_material`, `15_material_menu`, `90_material_system`), the systemd path unit, the polkit helper, the package scriptlets, the editor. The update rewrites the installed hooks (the GRUB engine already does), and a test updates a 0.7.x machine and checks that `grub-mkconfig` and a kernel-update run still work without `material-grub` on the path. The legacy helper scripts `material-grub-*` go with it.

### 3.3 The editor
It exists (`gui/` in the material-grub repository: a local server, a Material 3 web page with live preview, per-entry colours, names, icons, order, presets, a Boot splash page when Plymouth is installed, a polkit helper so it never runs as root) but is **not part of the product**: `material-boot` does not know it. Decided: **it moves into material-boot-core.**
- The core owns the **server, the web assets and the helper**; the shared pages (look, colours, entries, presets, health) are the core's. **A part brings its own page** through its manifest (GRUB: resolution, countdown, timeout, Ventoy; Plymouth: bar, motion, command line), the same way a part brings its questions today.
- **`material-boot ui`** starts it and opens the browser (or prints the address); the menu lists it; **one launcher icon, "Material Boot"**, replaces "Material GRUB". It listens on the loopback address only, as before.
- It is installed **by default when a graphical session is detected** (`--without ui` skips it), is version-matched to the core by construction, and the old editor package and tree are removed by the migration (3.4).
- Cost: the code, its tests (it has its own end-to-end browser tests) and CI move to the core; material-grub stops shipping `gui/` and the `material-grub-gui` package.

### 3.4 Cleaning up after older installs
A migration step finds what the 0.7.x layout left: the old launcher `.desktop`, the old editor tree and its helper, `material-grub-*` scripts nobody calls, stale backups over a limit. It **lists them in the notice before the screen** ("Found from an older install: ..."), backs them up, removes or replaces them, and says so at the end. The `material-grub` command and the `material-grub-*` scripts are in that list once the hooks have moved (3.2). A test installs 0.7.1 in a container and checks that only the new files are left and that GRUB still regenerates.

### 3.5 Help and documentation
One table per module (command, summary, options with their values and defaults, examples) generates `--help`, `material-boot help`, the menu text, the install options and a man page. Tests: every option the code accepts is in the table; every option in the table is accepted; every example runs (`--dry-run`). The installer's `--help` lists its options by part.

## 4. What changes for whom
- **Someone installing**: parts and the initial look in one screen flow (or "keep / edit" on an update), one progress view, a closing page that says what to do next.
- **Someone customising**: the editor (live preview, both parts, one icon); in a terminal, `material-boot` and `material-boot core colour|overrides|presets|conf`, all documented.
- **Someone with 0.7.x**: the update lists, backs up and removes the old icon, editor tree and `material-grub` command, and moves the hooks.
- **Scripts and packages**: flags unchanged; anything that called `material-grub` calls `material-boot grub ...` (the same arguments).

## 5. Phases (each a release, each tested end to end in a container first)
1. **One install flow (1.2.0).** The two screens and the progress view, the "keep or edit" step, the closing page, the leftovers listed in the notice, the Plymouth package fix (found on this machine). Nothing is removed yet, so it can be tested on the real machine soon.
2. **2.0.0, the breaking release:** the editor moves into the core with `material-boot ui` and the one launcher; **`material-grub` and its helper scripts are removed** and every hook, unit, helper and scriptlet that called it moves to `material-boot`; the migration removes the old icon, editor and command; help generated from one table (3.5). Tested on a real 0.7.1 to 2.0.0 update in a container, including a kernel-update regeneration without `material-grub`.

Why two: removing a command is a breaking change (a major version), and phase 1 is useful on its own and smaller to verify. If you would rather have a single big release, 1 and 2 can be one 2.0.0.

## 6. Decisions (the maintainer, 2026-11-28)
1. **Customising:** the installer keeps the initial look and part questions, and on a machine that is set up already asks **"keep your current look and settings, or edit them now?"** first; after the install, everything further is in the web editor.
2. **`material-grub`:** removed in the next release (so, with the hooks and units moved first: section 3.2).
3. **The editor:** moves into material-boot-core.
4. **Default:** the editor is installed by default when a graphical session is detected (`--without ui` skips it).

## 7. Not decided here
A native desktop app instead of a local web page; remote access to the editor (it listens on the loopback address only, and stays that way); immutable systems (still unsupported, and the installer should say so up front).
