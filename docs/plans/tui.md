# The installer screen (TUI), redesigned

**Status: T0 to T3 implemented** (pull request "The installer screen"; the parts declare their questions in material-grub and material-plymouth). The sections below are the proposal as written; section 10 says what was built, what was decided about the open questions, and what is left. Written after the first real install of 1.0.0, which showed that the unified installer had no screen at all.

## 1. Where we are, honestly

- The design confirmed in [installer.md](../installer.md) says: in a terminal with no choice given, **a checklist asks which parts**; **the shared look is asked once**; GRUB's own TUI runs inside GRUB's install.
- What 1.0.0 does: none of that. It takes options on the command line (`--with plymouth`) and asks one question (`Continue? [Y/n]`). GRUB's part runs its engine with `--yes --no-tui`, so the old TUI can never show. A fresh install gets defaults; an update keeps what is there.
- The old TUI (`install/tui.py` in material-grub, about 1,100 lines, curses with a plain-prompt fallback) works and is well tested. Its steps: resolution (detected monitors, or typed), style (rail, clean, list, split), scheme (dark or light), seed colour (one colour for everything, with a preview), cookie, logo and hints, raw names, countdown and timeout, the optional GUI, immutable systems, and the Ventoy stick questions. Every option has a help text; answers given by flags are not asked again.

## 2. What we want

The same idea, **better**: one screen flow for the whole of Material Boot, in colour, with a real preview, and with the customisation that today needs flags or the GUI.

Constraints to keep (they are why the old one works): the installer runs before anything is installed, as root, on any distribution, so **stdlib only** (curses), a **plain-prompt fallback** (no colours, no curses, a pipe or a tiny terminal), **every answer is also a flag** (so a script can do the same without a screen), and **nothing is written until the last confirmation**.

## 3. The flow

1. **Parts.** A checklist built from the manifests: core (always), Material GRUB, Material Plymouth, the GUI (needs GRUB); what is installed is ticked and marked "installed 0.7.1, will update", what a part `needs` is ticked for you with a line saying why. Skipped when `--with`, `--without` or `--only` were given, or on an update with nothing new to offer.
2. **Look (shared).** Style, scheme (dark or light), **seed colour**, cookie, logo and hints: the keys every part reads, asked once. A live **preview** on the right (section 4).
3. **Each part's own questions**, in order: GRUB (resolution, countdown and timeout, raw names, Ventoy stick, immutable), Plymouth (on or off, bar style, motion, the command-line edit), GUI (install or not). A part describes its questions in data (section 5); the screen draws them.
4. **Summary.** The exact command line that would do the same (`material-boot core install --with plymouth --grub-style split ...`), what will change, where the backup goes, and `Install`, `Back`, or `Save as a preset`.

Keys: arrows or `j/k`, `Enter`, `Space` to tick, `Esc` or `b` for back, `?` for the help of the option, `q` to cancel. The terminal is restored on any exit.

## 4. Better graphics

- **Colour.** The seed colour drives the screen's own accent: borders, the selected row and the swatches use the real Material 3 palette computed from the seed (the core already has it), in truecolor when `COLORTERM` says so, else 256 colours, else plain.
- **A real preview.** The core's renderer already draws the exact scene. A small render (for example 320 pixels wide) is turned into **half-block characters** (two pixels per cell, truecolor or 256 colours) beside the questions, and redrawn when the style, scheme or seed changes. This is the actual theme, not a sketch. If the terminal has no colour, or is narrower than about 100 columns, the preview is replaced by a one-line description.
- **Colour pickers.** The seed step shows the 32 named seeds as a grid of swatches plus a `#RRGGBB` box with a live swatch.
- **No image protocols** (sixel, kitty): not reliable across terminals, and the installer must not depend on them.

## 5. More customisation

Everything below already exists in the GUI or in `overrides.json` and presets; the screen only exposes it at install time:
- **Presets**: pick a saved preset (or a file) as the starting point; save the answers as one at the end.
- **Per entry** (optional step, off by default): name, colour, icon, hidden, order, written to `overrides.json`.
- **Plymouth**: style, motion level (full, calm, off), the loading bar.
- **GRUB**: countdown, timeout, cookie, logo, hints, resolution per monitor.
- The summary always prints the equivalent flags, so what is chosen here can be repeated.

## 6. How it is built

- The screen lives **in the core** (`material_boot/tui/`), because it asks about several parts. The old `install/tui.py` is not discarded: its question text and validation move over (it is the one tested source of truth for the wording), one step at a time.
- **A part describes questions in data**, through the hook the design already reserved, `hook_questions(ctx)`: a list of `{key, title, kind (choice, toggle, text, colour), options, help, default, flag, when}`. GRUB's and Plymouth's questions become data in their repositories; the core draws them and turns the answers into the part's options. A part without the hook asks nothing.
- **Non-interactive parity**: the answers are exactly the options the installer already has, so `--yes` or no terminal means no screen and the same result as today.
- The GRUB part stops passing `--no-tui`; the screen collects the answers once and hands them to the engine as options. (The engine's own TUI stays for the legacy `material-grub` front end.)

## 7. How it is tested

- **Pty-driven tests** (the way the old TUI is tested): type a path through the screens and check the resulting command line and files; the old TUI's own tests are the model.
- **Golden screens**: each screen drawn into a fixed 80x24 and 120x40 grid as text and compared with a stored copy, so a change in wording or layout is a deliberate diff.
- **Plain fallback** tested with a non-tty and with `TERM=dumb`; a terminal that is too small says so instead of drawing garbage.
- **Mutation checks** as for every other test here, and a CI job that drives the real screen in a container (Fedora and Debian).
- What cannot be tested in CI and needs a person: how it looks in real terminals (colour fidelity, fonts). Said plainly in the release notes.

## 8. Phases (each its own pull request)

| | What | Release |
|---|---|---|
| T0 | The parts checklist and the plain prompts, `hook_questions` in the plugin contract, GRUB's part stops forcing `--no-tui` | 1.1.0 |
| T1 | GRUB's questions as data, drawn by the new screen (curses), the summary with the equivalent command | 1.1.0 |
| T2 | Plymouth's and the GUI's questions, presets in and out | 1.1.0 |
| T3 | Colour, swatches and the half-block preview | 1.2.0 |
| T4 | Per-entry customisation | 1.2.0 |

## 9. Open questions for the maintainer

1. Is the preview worth its cost (a render of a few hundred milliseconds per change, and a bigger screen)? My view: yes, it is the point of a visual theme, and it can be switched off with `--no-preview`.
2. Per-entry customisation at install time, or only in the GUI? My view: the GUI is the right place for something this fiddly; the installer can offer "open the GUI afterwards". It is in T4 and can be dropped.
3. Should an **update** show the screen? My view: only if a part has new questions (for example Plymouth's), never to re-ask what was answered.
4. Is `1.1.0` right for T0 to T2, with 1.0.x kept for fixes?

Not decided here: a graphical (non-terminal) installer. The GUI already covers that after install.

## 10. What was built (2026-11-27, overnight) and what was decided

**Built:** `material_boot/tui.py` (the state machine `Flow`, curses with a plain-prompt fallback, the summary with the equivalent command line), `install.questions` in a part's manifest (plugins.md), the parts' own questions (grub: resolution, raw names, countdown, timeout, the editor; plymouth: loading bar, motion, the command line), the preview and the colour chips, scrolling, and these tests: unit tests of the questions, the state machine and the preview; golden screens at 80x24 and 120x40; the real curses screen on a pty (keys in, 256-colour escapes out); the screen against the real parts' manifests of a built bundle; and a container test in which a person-like driver installs GRUB with the keyboard and the result is checked (settings, grub.cfg, removal).

**Decisions on section 9, taken by me while the maintainer slept (each is easy to reverse):**
1. **The preview**: kept, but it is a *drawing of the layout* in the chosen colours (from the palette), not a render of the real scene: the real renderer needs the shared data, which does not exist before the install. A render of the real scene stays a possible later step (build the data first, then preview).
2. **Per-entry customisation at install time**: not built. The GUI is the place for it; the screen does not offer it. (T4 is dropped.)
3. **An update** shows only the parts question (and the questions of a part that is new); `--tui` shows the whole screen.
4. **1.1.0** for T0 to T3, with 1.0.x kept for fixes (1.0.1 was one).

**Found while building it:** curses sends only the cells that changed, so a test that waits for a whole sentence on the screen fails at random; `MATERIAL_BOOT_TUI_REPAINT=1` repaints everything every time and the tests use it. The installer asked `Continue?` after the screen's own summary (twice the same question): confirming the summary now counts as the confirmation.

**Not built:** presets in and out (start from a saved preset, save the answers as one); a render of the real scene as the preview; a check of how it looks in real terminals (only xterm-256color on a pty was seen, rendered by an emulator).
