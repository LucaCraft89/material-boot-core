#!/bin/sh
# The whole unified installer, for real, in a Fedora, Debian, Ubuntu or Arch container with a fake /boot: install from a bundle that holds the REAL parts (material-grub and
# material-plymouth, built by scripts/build_bundle.py from their checkouts), look at what is on the system, and remove it again.   usage: sh bundle_smoke.sh
# /bundle: the unpacked bundle   /src: this repository (read-only)   /out: receives bundle-smoke.txt
# 1. dry run: nothing changes   2. a fresh install, default parts (GRUB): theme built, grub.cfg annotated, part registered and recorded
# 3. add Plymouth (--with plymouth): the theme applied for real, the initramfs rebuilt and checked, the part registered   4. doctor lists both
# 5. uninstall Plymouth then GRUB: the initramfs and grub.cfg are as before, the core stays
set -e
R=/out/bundle-smoke.txt; : > $R
say() { echo "$*" | tee -a $R; }
# only behind a TLS-intercepting proxy (a sandbox)
if [ -n "${MG_CA:-}" ]; then
  for d in /etc/pki/ca-trust/source/anchors /etc/ca-certificates/trust-source/anchors /usr/share/pki/trust/anchors /usr/local/share/ca-certificates; do
    [ -d "$d" ] && { cp "$MG_CA" "$d/mg-ca.crt"; break; }
  done
  update-ca-trust 2>/dev/null || update-ca-certificates >/dev/null 2>&1 || true
fi
. /etc/os-release
export DEBIAN_FRONTEND=noninteractive INITRD=No
case $ID in
  fedora)
    dnf -y install -q --setopt=tsflags=noscripts kernel-core >/dev/null 2>&1
    dnf -y install -q grub2-tools grub2-tools-extra librsvg2-tools python3 python3-pip python3-pillow plymouth plymouth-plugin-script plymouth-plugin-label plymouth-scripts dracut findutils kmod >/dev/null 2>&1
    for k in /lib/modules/*; do depmod -a "$(basename "$k")"; done
    kver=$(ls /lib/modules | head -n1); mkdir -p /boot/grub2 /etc/default
    cp "/lib/modules/$kver/vmlinuz" "/boot/vmlinuz-$kver"
    IMG="/boot/initramfs-$kver.img"; dracut -f --no-hostonly "$IMG" "$kver" >/dev/null 2>&1
    CFG=/boot/grub2/grub.cfg; MK=grub2-mkconfig; PROBE=/usr/sbin/grub2-probe; LISTER=lsinitrd ;;
  debian|ubuntu)
    apt-get update -qq >/dev/null
    case $ID in ubuntu) kernel=linux-image-virtual ;; *) kernel=linux-image-amd64 ;; esac
    apt-get install -y -qq --no-install-recommends grub-common os-prober python3 python3-pil python3-venv python3-pip librsvg2-bin plymouth plymouth-label initramfs-tools kmod "$kernel" >/dev/null 2>&1
    for k in /lib/modules/*; do depmod -a "$(basename "$k")"; done
    kver=$(ls /lib/modules | head -n1); mkdir -p /boot/grub /etc/default
    update-initramfs -c -k "$kver" >/dev/null 2>&1
    IMG="/boot/initrd.img-$kver"
    CFG=/boot/grub/grub.cfg; MK=grub-mkconfig; PROBE=/usr/sbin/grub-probe; LISTER=lsinitramfs ;;
  arch)
    pacman -Syu --noconfirm --needed --disable-sandbox >/dev/null 2>&1 || pacman -Syu --noconfirm --needed >/dev/null 2>&1
    pacman -S --noconfirm --needed grub librsvg python python-pip python-pillow plymouth mkinitcpio kmod linux >/dev/null 2>&1
    kver=$(ls /lib/modules | head -n1); mkdir -p /boot/grub /etc/default
    IMG=/boot/initramfs-linux.img; [ -f "$IMG" ] || mkinitcpio -k "$kver" -g "$IMG" >/dev/null 2>&1
    CFG=/boot/grub/grub.cfg; MK=grub-mkconfig; PROBE=/usr/bin/grub-probe; LISTER=lsinitcpio ;;
  opensuse*)
    zypper --non-interactive --gpg-auto-import-keys refresh >/dev/null
    zypper --non-interactive install --no-recommends grub2 rsvg-convert python3 python3-pip python3-Pillow plymouth plymouth-plugin-script plymouth-plugin-label plymouth-plugin-label-ft plymouth-scripts plymouth-dracut dracut findutils diffutils kmod kernel-default-base >/dev/null
    for k in /lib/modules/*; do depmod -a "$(basename "$k")"; done
    kver=$(ls /lib/modules | head -n1); mkdir -p /boot/grub2 /etc/default
    IMG="/boot/initrd-$kver"; dracut -f --no-hostonly "$IMG" "$kver" >/dev/null 2>&1
    CFG=/boot/grub2/grub.cfg; MK=grub2-mkconfig; PROBE=/usr/sbin/grub2-probe; LISTER=lsinitrd ;;
  *) echo "unknown distribution $ID"; exit 1 ;;
esac
cp /src/tests/containers/probe "$PROBE" 2>/dev/null || true
printf 'GRUB_TIMEOUT=5\nGRUB_DISTRIBUTOR=test\nGRUB_CMDLINE_LINUX="quiet"\nGRUB_GFXMODE=1920x1080\n' > /etc/default/grub
$MK -o $CFG >/dev/null 2>&1
cfg0=$(sha256sum $CFG | cut -d' ' -f1); img0=$(sha256sum "$IMG" | cut -d' ' -f1)
snap() { find /boot /etc /usr/share /usr/libexec /usr/local /var/lib -type f 2>/dev/null | grep -v -e '/var/lib/rpm' -e '/var/lib/dnf' -e '/usr/lib/sysimage' -e '/etc/ld.so.cache' -e '/boot/initramfs' -e '/boot/initrd' -e '/var/lib/dpkg' -e '/var/lib/pacman' -e '/var/cache' -e '/var/lib/apt' -e '__pycache__' | sort | xargs sha256sum 2>/dev/null || true; }
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
assert [h["to"] for h in s["history"]] == [open("/bundle/VERSION").read().strip()], s["history"]  # the core's version, whatever it is
PY
[ -e /usr/share/plymouth/themes/material ] && { say "Plymouth was applied without being asked"; exit 1; } || say "Plymouth is not installed (not a default part)"

say "== add Plymouth"
sh install.sh --yes --with plymouth --plymouth-no-cmdline > /tmp/i2.log 2>&1 && say "install --with plymouth: ok" || { say "install --with plymouth FAILED"; tail -40 /tmp/i2.log | tee -a $R; exit 1; }
[ -f /usr/share/plymouth/themes/material/material.script ] && say "the theme is installed" || { say "no theme"; exit 1; }
material-boot plymouth status --json | grep -Eq '"default_theme": "(material|[^"]*/material/material.plymouth)"' && say "it is the default theme" || { say "the default theme is not ours"; material-boot plymouth status --json | tee -a $R; exit 1; }
$LISTER "$IMG" | grep -q "themes/material/material.script" && say "the initramfs holds the theme" || { say "the initramfs does not hold the theme"; exit 1; }
material-boot core parts | grep -q "plymouth .*ok" && say "core parts lists plymouth" || { say "plymouth is not a part"; material-boot core parts | tee -a $R; exit 1; }
material-boot plymouth status | grep -q "installed" && say "material-boot plymouth status: ok" || { say "plymouth status FAILED"; exit 1; }
material-boot core doctor > /tmp/doc.txt 2>&1 && say "core doctor: ok" || { say "core doctor FAILED"; cat /tmp/doc.txt | tee -a $R; exit 1; }
grep -q "Plymouth boot splash" /tmp/doc.txt && grep -q "Material GRUB theme" /tmp/doc.txt && say "doctor has a section per part" || { say "doctor lacks a section"; cat /tmp/doc.txt | tee -a $R; exit 1; }
sh install.sh --yes --with plymouth --plymouth-no-cmdline > /tmp/i3.log 2>&1 && say "installing again: ok" || { say "second install FAILED"; tail -30 /tmp/i3.log | tee -a $R; exit 1; }
grep -q "Unchanged\|Installed" /tmp/i3.log && say "second run says what it did"

say "== uninstall"
sh install.sh --uninstall --only plymouth --yes > /tmp/u1.log 2>&1 && say "uninstall plymouth: ok" || { say "uninstall plymouth FAILED"; tail -30 /tmp/u1.log | tee -a $R; exit 1; }
[ ! -e /usr/share/plymouth/themes/material ] && say "the theme is gone" || { say "theme still there"; exit 1; }
$LISTER "$IMG" | grep -q "themes/material" && { say "the initramfs still holds the theme"; exit 1; } || say "the initramfs no longer holds the theme"
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
