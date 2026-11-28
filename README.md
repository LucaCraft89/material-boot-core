# Material Boot

Material You for your boot: a **GRUB menu theme** and a **Plymouth boot splash** with one look (a Material 3 palette, a style, a colour for every entry, names and icons), installed and edited from one place.

This repository is the **core**: the shared code, the `material-boot` command, the installer, and the editor. The two parts are their own repositories:
[Material GRUB](https://github.com/LucaCraft89/material-grub) (the menu) and [Material Plymouth](https://github.com/LucaCraft89/material-plymouth) (the splash).

## Install

Download `material-boot-<version>.tar.gz` from the [latest release](https://github.com/LucaCraft89/material-boot-core/releases/latest), unpack it and run:

```sh
sudo ./install.sh
```

On a terminal it shows a screen: which parts, the look (with a preview), and each part's questions. On a machine that is set up already it first asks whether to **keep the current look and settings or edit them now**, and it only touches what changes. Without a terminal, or with `--yes`, it asks nothing (`./install.sh --help` lists every option). Packages: `material-boot-core`, `material-grub`, `material-plymouth` (rpm, deb, Arch).

## Change it afterwards: one place

```sh
material-boot ui        # the editor in your browser, with a live preview
material-boot help      # every command, with its options and examples (also: man material-boot)
```

The editor changes everything (style, colours, names, icons and order of the entries, Ventoy sticks, the boot splash, presets) and applies it with one password prompt. The same things in a terminal: `material-boot core conf | colour | presets | overrides | apply | doctor`, and each part's own commands (`material-boot grub apply`). The full reference is [docs/commands.md](docs/commands.md) and [docs/editor.md](docs/editor.md).

## Coming from 1.1 or older

The `material-grub` command and the old graphical editor are gone: `material-boot grub ...` and `material-boot ui` replace them. The installer lists what it removes, backs it up first, and keeps all your settings. See [docs/releases/1.2.0.md](docs/releases/1.2.0.md).

## For developers

[docs/architecture.md](docs/architecture.md) (how it fits together), [docs/plugins.md](docs/plugins.md) (writing a part), [docs/installer.md](docs/installer.md) (the unified installer), [docs/plans/ux.md](docs/plans/ux.md) (the design of the install and customise experience).

Code: MIT, see [LICENSE](LICENSE).
