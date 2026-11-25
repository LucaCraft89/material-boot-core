#!/bin/sh
# The whole unified installer, for real, in a Fedora container with a fake /boot: install from a bundle that holds the REAL parts (material-grub and
# material-plymouth, built by scripts/build_bundle.py from their checkouts), look at what is on the system, and remove it again.   usage: sh bundle_smoke.sh
# /bundle: the unpacked bundle   /src: this repository (read-only)   /out: receives bundle-smoke.txt
# 1. dry run: nothing changes   2. a fresh install, default parts (GRUB): theme built, grub.cfg annotated, part registered and recorded
# 3. add Plymouth (--with plymouth): the theme applied for real, the initramfs rebuilt and checked, the part registered   4. doctor lists both
# 5. uninstall Plymouth then GRUB: the initramfs and grub.cfg are as before, the core stays
set -e
R=/out/bundle-smoke.txt; : > $R
say() { echo "$*" | tee -a $R; }
# only behind a TLS-intercepting proxy (a sandbox)
if [ -n "${MG_CA:-}" ]; then cp "$MG_CA" /etc/pki/ca-trust/source/anchors/mg-ca.crt && update-ca-trust; fi
dnf -y install -q --setopt=tsflags=noscripts kernel-core >/dev/null 2>&1
dnf -y install -q grub2-tools grub2-tools-extra librsvg2-tools python3 python3-pip python3-pillow plymouth plymouth-plugin-script plymouth-plugin-label plymouth-scripts dracut findutils kmod >/dev/null 2>&1
for k in /lib/modules/*; do depmod -a "$(basename "$k")"; done
kver=$(ls /lib/modules | head -n1)
mkdir -p /boot/grub2 /etc/default
cp "/lib/modules/$kver/vmlinuz" "/boot/vmlinuz-$kver"
dracut -f --no-hostonly "/boot/initramfs-$kver.img" "$kver" >/dev/null 2>&1
cp /src/tests/containers/probe /usr/sbin/grub2-probe 2>/dev/null || true
printf 'GRUB_TIMEOUT=5\nGRUB_DISTRIBUTOR=test\nGRUB_CMDLINE_LINUX="quiet"\nGRUB_GFXMODE=1920x1080\n' > /etc/default/grub
CFG=/boot/grub2/grub.cfg; grub2-mkconfig -o $CFG >/dev/null 2>&1
cfg0=$(sha256sum $CFG | cut -d' ' -f1); img0=$(sha256sum "/boot/initramfs-$kver.img" | cut -d' ' -f1)
snap() { find /boot /etc /usr/share /usr/libexec /usr/local /var/lib -type f 2>/dev/null | grep -v -e '/var/lib/rpm' -e '/var/lib/dnf' -e '/usr/lib/sysimage' -e '/etc/ld.so.cache' -e '/boot/initramfs' -e '__pycache__' | sort | xargs sha256sum 2>/dev/null || true; }
cp -r /bundle /b; cd /b

say "== dry run on a fresh system"
snap > /tmp/s0
sh install.sh --dry-run --with grub,plymouth > /tmp/dry.log 2>&1 && say "dry run: ok" || { say "dry run FAILED"; tail -30 /tmp/dry.log | tee -a $R; exit 1; }
grep -q "Plymouth boot splash" /tmp/dry.log && grep -q "Material GRUB theme" /tmp/dry.log && say "the plan names both parts" || { say "the plan misses a part"; cat /tmp/dry.log | tee -a $R; exit 1; }
snap > /tmp/s1; cmp -s /tmp/s0 /tmp/s1 && say "SYSTEM UNCHANGED by the dry run" || { say "the dry run changed the system"; diff /tmp/s0 /tmp/s1 | head | tee -a $R; exit 1; }

say "== install, default parts"
sh install.sh --yes --grub-res 1920x1080 > /tmp/i1.log 2>&1 && say "install: ok" || { say "install FAILED"; tail -40 /tmp/i1.log | tee -a $R; exit 1; }
grep -q "^Installed: core, grub" /tmp/i1.log && say "summary: core and grub installed" || { say "summary is wrong"; tail -5 /tmp/i1.log | tee -a $R; exit 1; }
grep -q "classes applied" $CFG && say "grub.cfg annotated" || { say "grub.cfg NOT annotated"; exit 1; }
material-boot core parts | grep -q "grub .*ok" && say "core parts lists grub" || { say "grub is not a part"; exit 1; }
python3 - <<'PY' && say "state record: core and grub, one history" || { say "state record is wrong"; cat /var/lib/material-grub/state.json | tee -a /out/bundle-smoke.txt; exit 1; }
import json
s = json.load(open("/var/lib/material-grub/state.json"))
assert set(s["parts"]) == {"core", "grub"}, s
assert [h["to"] for h in s["history"]] == ["1.0.0"], s["history"]
PY
[ -e /usr/share/plymouth/themes/material ] && { say "Plymouth was applied without being asked"; exit 1; } || say "Plymouth is not installed (not a default part)"

say "== add Plymouth"
sh install.sh --yes --with plymouth --plymouth-no-cmdline > /tmp/i2.log 2>&1 && say "install --with plymouth: ok" || { say "install --with plymouth FAILED"; tail -40 /tmp/i2.log | tee -a $R; exit 1; }
[ -f /usr/share/plymouth/themes/material/material.script ] && say "the theme is installed" || { say "no theme"; exit 1; }
[ "$(plymouth-set-default-theme)" = material ] && say "it is the default theme" || { say "default theme is $(plymouth-set-default-theme)"; exit 1; }
lsinitrd "/boot/initramfs-$kver.img" | grep -q "themes/material/material.script" && say "the initramfs holds the theme" || { say "the initramfs does not hold the theme"; exit 1; }
material-boot core parts | grep -q "plymouth .*ok" && say "core parts lists plymouth" || { say "plymouth is not a part"; material-boot core parts | tee -a $R; exit 1; }
material-boot plymouth status | grep -q "installed" && say "material-boot plymouth status: ok" || { say "plymouth status FAILED"; exit 1; }
material-boot core doctor > /tmp/doc.txt 2>&1 && say "core doctor: ok" || { say "core doctor FAILED"; cat /tmp/doc.txt | tee -a $R; exit 1; }
grep -q "Plymouth boot splash" /tmp/doc.txt && grep -q "Material GRUB theme" /tmp/doc.txt && say "doctor has a section per part" || { say "doctor lacks a section"; cat /tmp/doc.txt | tee -a $R; exit 1; }
sh install.sh --yes --with plymouth --plymouth-no-cmdline > /tmp/i3.log 2>&1 && say "installing again: ok" || { say "second install FAILED"; tail -30 /tmp/i3.log | tee -a $R; exit 1; }
grep -q "Unchanged\|Installed" /tmp/i3.log && say "second run says what it did"

say "== uninstall"
sh install.sh --uninstall --only plymouth --yes > /tmp/u1.log 2>&1 && say "uninstall plymouth: ok" || { say "uninstall plymouth FAILED"; tail -30 /tmp/u1.log | tee -a $R; exit 1; }
[ ! -e /usr/share/plymouth/themes/material ] && say "the theme is gone" || { say "theme still there"; exit 1; }
lsinitrd "/boot/initramfs-$kver.img" | grep -q "themes/material" && { say "the initramfs still holds the theme"; exit 1; } || say "the initramfs no longer holds the theme"
[ ! -e /usr/local/share/material-boot/plugins.d/plymouth.json ] && say "plymouth's manifest is gone" || { say "plymouth manifest left"; exit 1; }
sh install.sh --uninstall --only grub --yes > /tmp/u2.log 2>&1 && say "uninstall grub: ok" || { say "uninstall grub FAILED"; tail -30 /tmp/u2.log | tee -a $R; exit 1; }
[ "$(sha256sum $CFG | cut -d' ' -f1)" = "$cfg0" ] && say "grub.cfg is as before" || { say "grub.cfg differs from before"; exit 1; }
material-boot version >/dev/null && say "the core stays and works" || { say "the core is broken"; exit 1; }
python3 - <<'PY' && say "state record: only the core is left" || { say "state record after the removals:"; cat /var/lib/material-grub/state.json | tee -a /out/bundle-smoke.txt; exit 1; }
import json
s = json.load(open("/var/lib/material-grub/state.json"))
assert set(s["parts"]) == {"core"}, s
PY
say "ALL OK"
