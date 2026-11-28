# One product, one way in: how a person installs and uses Material Boot

**Status: a plan for the maintainer to decide on. No code.** Written after the first real runs of 1.1.x on a Fedora 45 machine (an update from 0.7.1), whose owner said: it is a mess of different TUIs, the old `material-grub` command and launcher icon are still there, the web editor is gone, GRUB asked nothing while Plymouth asked questions, and customisation should be in one place: the web editor, after the install. That is right, and it is the result of building the parts one at a time. This plan starts from what a person sees.

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
2. **The installer installs.** It asks only what must be decided before anything exists: which parts, and system facts (an immutable system, a Ventoy stick). It does **not** ask about the look.
3. **Customising has one home: the web editor**, with a live preview, for GRUB and Plymouth together. A terminal route exists for machines without a browser, and it is fully documented.
4. **One voice in the terminal**: one progress view, one style for headings and results, and a record that stays on screen.
5. **Upgrades clean up after themselves**: what an older layout left behind is found, listed, backed up and removed (or replaced), never silently kept.
6. **Help is generated from the same table as the options**, and a test fails when they differ.

## 3. The design

### 3.1 Installing
`./install.sh` (or a package) is **two screens and one progress view**:
1. **What to install and what is here.** The parts (GRUB, Plymouth, the Editor) with what is installed already, its version and what the run will do, plus the few system choices. A fresh system gets the defaults; an update keeps the look. This is the only question screen.
2. **Progress, one view for all parts.** The core already can consume a part's progress as events (`--progress json` is what the GUI reads); GRUB's engine and Plymouth report through it and the core draws it: `Step 3 of 7, Rendering the theme`, with the log kept below. The engine's own banner is not shown.
3. **A closing screen that stays in the scrollback**: what was installed or changed, what was removed (section 3.4), and the next step: *"Customise your look: `material-boot ui` (opens the editor in your browser)"*, with an "open it now?" when a graphical session is detected.

Non-interactive stays as it is: `--yes`, `--dry-run`, `--no-tui`, `--progress json`, the options per part. `--tui` goes (nothing is asked about the look any more). The summary still prints the equivalent command line.

### 3.2 Using it
- **`material-boot`** with no arguments: a short status (what is installed, health in one line, whether the editor is available) and a menu: *Open the editor*, *Health check*, *Apply changes*, *Update*, *Parts*, and, for terminal-only use, *Colour*, *Entries (names, colours, icons)*, *Presets*, *Settings*. One menu, with the style of the installer screens.
- **`material-boot ui`** opens the editor (starts its local server, opens the browser, prints the address when there is no browser).
- **`material-boot <module> <command>`** for scripts: `core` (shared), `grub`, `plymouth`, `ui`. `material-boot help [module [command]]` and `--help` everywhere.
- **`material-grub`** becomes a thin alias that runs the same thing and prints one line saying `material-boot` is the command now. Kept through 1.x because hooks and units use it; they are moved to `material-boot grub apply` in 1.x and the alias goes in 2.0.

### 3.3 The editor
It exists (`gui/` in the material-grub repo: a local server, a Material 3 web page with live preview, per-entry colours, names, icons, order, presets, a Boot splash page when Plymouth is installed, a polkit helper so it never runs as root). What is missing is that it is **not part of the product**. Proposed:
- It becomes a **part** (`ui`) with a manifest, installed and updated by the same installer, version-matched to the core so an old editor never runs against a new core.
- **`material-boot ui`** is its command and the menu lists it; **one launcher icon, "Material Boot"**, replaces "Material GRUB".
- Where it lives, three options (decision 3): keep it in the material-grub repository and declare it as a part there (cheapest, a little odd for Plymouth's page), move it to its own repository (cleanest, one-off cost), or fold it into the core (the core grows a web server).

### 3.4 Cleaning up after older installs
A migration step finds what the 0.7.x layout left: the old launcher `.desktop`, the old editor tree and its helper, `material-grub-*` scripts nobody calls, stale backups over a limit. It **lists them in the notice before the screen** ("Found from an older install: ..."), backs them up, removes or replaces them, and says so at the end. The `material-grub` alias stays (3.2). A test installs 0.7.1 in a container and checks nothing but the alias and the new files is left.

### 3.5 Help and documentation
One table per module (command, summary, options with their values and defaults, examples) generates `--help`, `material-boot help`, the menu text, the install options and a man page. Tests: every option the code accepts is in the table; every option in the table is accepted; every example runs (`--dry-run`). The installer's `--help` lists its options by part.

## 4. What changes for whom
- **Someone installing**: one screen of choices, one progress view, a closing page that says what to do next. No look questions.
- **Someone customising**: the editor (live preview, both parts); in a terminal, `material-boot` and `material-boot core colour|overrides|presets|conf`, all documented.
- **Someone with 0.7.x**: the update removes the old icon and editor tree after listing them, and `material-grub` still works with a hint.
- **Scripts and packages**: unchanged flags; the alias keeps hooks working.

## 5. Phases (each a release, each tested end to end in a container first)
1. **One install flow (1.2.0).** One question screen, the progress view for all parts, the closing page, the leftovers migration, the Plymouth package fix (found on this machine), look questions removed from the installer. Biggest change; tested by driving the real screens and an upgrade from a real 0.7.1.
2. **The editor as a part (1.3.0).** `material-boot ui`, one launcher, version-matched; the polkit and path units follow.
3. **Help from one table (1.4.0).**
4. **Hooks and units move to `material-boot` (1.5.0);** the `material-grub` alias goes in 2.0.

## 6. Decisions needed (my recommendation first)
1. **Where does customising live?** Editor only, with the terminal commands for headless machines (recommended), or keep a look step in the installer too.
2. **`material-grub`**: alias with a hint through 1.x (recommended), or remove it in the next release (breaks hooks until they are moved).
3. **Where does the editor live?** Declared as a part inside the material-grub repository now, moved later (recommended); its own repository now; or in the core.
4. **Is the editor installed by default** when a graphical session is detected? It was always off by default; with the editor as the home of customising, on-by-default on a desktop is more useful (recommended, still `--without ui`).

## 7. Not decided here
A native desktop app instead of a local web page; remote access to the editor (it listens on the loopback address only, and stays that way); immutable systems (still unsupported, and the installer should say so up front).
