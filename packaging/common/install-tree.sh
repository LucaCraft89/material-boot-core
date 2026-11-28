#!/bin/sh
# Lays out the files a package of the core ships (used by the spec, the PKGBUILD and debian/rules).
# The shared DATA is not part of the package: it depends on the scheme, so it is built on the target machine by
# `material-boot core install --from-package --only core` (the package's post-install step).
# usage: install-tree.sh SRCDIR DESTDIR
set -e
src=$1; dest=$2; p=$dest/usr/share/material-boot
install -d "$p/lib" "$p/scripts" "$p/plugins.d" "$dest/usr/bin"
cp -a "$src/material_boot" "$p/lib/material_boot"
find "$p" -name __pycache__ -type d -prune -exec rm -rf {} +
install -m644 "$src/VERSION" "$p/lib/material_boot/VERSION"
install -m755 "$src/scripts/build_data.py" "$p/scripts/build_data.py"
cp -a "$src/assets" "$p/assets"
install -m755 "$src/bin/material-boot" "$dest/usr/bin/material-boot"
# the editor's launcher, its helper and the polkit policy (what `ui` installs from a bundle)
install -d "$dest/usr/libexec" "$dest/usr/share/polkit-1/actions" "$dest/usr/share/applications"
install -m755 "$src/packaging/ui/material-boot-ui-helper" "$dest/usr/libexec/material-boot-ui-helper"
install -m644 "$src/packaging/ui/org.material-boot.ui.policy" "$dest/usr/share/polkit-1/actions/org.material-boot.ui.policy"
install -m644 "$src/packaging/ui/material-boot.desktop" "$dest/usr/share/applications/material-boot.desktop"
