#!/bin/sh
# An update from the RELEASED 1.1.x bundle (the `material-grub` command, the old editor, Plymouth) to this bundle, in a distro container with a fake /boot. This is what
# a person who installed 1.1.x runs next: nothing of theirs may be lost, the old command and the old editor must go (backed up first), and everything must keep working.
# usage: sh upgrade_bundle_smoke.sh      /old: the unpacked old bundle   /bundle: the new one   /src: this repository (read-only)   /out: receives upgrade-bundle-smoke.txt
set -e
R=/out/upgrade-bundle-smoke.txt; : > $R
say() { echo "$*" | tee -a $R; }
. /src/tests/containers/prep.sh

say "== the old release: $(cat /old/VERSION)"
cp -r /old /o; cd /o
sh install.sh --yes --with grub,plymouth --grub-res 1920x1080 --grub-with-gui --plymouth-no-cmdline > /tmp/old.log 2>&1 && say "install: ok" || { say "old install FAILED"; tail -40 /tmp/old.log | tee -a $R; exit 1; }
[ -x /usr/local/bin/material-grub ] && say "it has the material-grub command" || { say "no material-grub command in the old install"; exit 1; }
[ -d /usr/share/material-grub-gui ] && [ -e /usr/libexec/material-grub-gui-helper ] && say "it has the old editor" || { say "no old editor in the old install"; exit 1; }
material-grub conf STYLE=list >/dev/null && material-grub colour '#7E57C2' >/dev/null && say "settings made with the old command: style list, one seed colour" || { say "old settings FAILED"; exit 1; }
printf '{"version":1,"seed":{"mode":"single","color":"#7E57C2"},"entries":[{"match":{"key":"tux"},"name":"Penguin","color":"#E95420"}]}' > /etc/material-grub/overrides.json
echo "# my own line" >> /etc/material-grub.conf
material-grub apply > /tmp/oldapply.log 2>&1 && say "applied with the old command" || { say "old apply FAILED"; tail -20 /tmp/oldapply.log | tee -a $R; exit 1; }
grep -q "classes applied" $CFG && say "grub.cfg annotated by the old version"

say "== the update to $(cat /bundle/VERSION), dry run first"
cp -r /bundle /b; cd /b
snap > /tmp/s0
sh install.sh --dry-run > /tmp/dry.log 2>&1 && say "dry run: ok" || { say "dry run FAILED"; tail -30 /tmp/dry.log | tee -a $R; exit 1; }
grep -q "remove /usr/local/bin/material-grub" /tmp/dry.log && grep -q "remove /usr/share/material-grub-gui" /tmp/dry.log && say "the plan names the old command and the old editor" || { say "the plan does not name the leftovers"; cat /tmp/dry.log | tee -a $R; exit 1; }
snap > /tmp/s1; cmp -s /tmp/s0 /tmp/s1 && say "SYSTEM UNCHANGED by the dry run" || { say "the dry run changed the system"; diff /tmp/s0 /tmp/s1 | head | tee -a $R; exit 1; }

say "== the update"
sh install.sh --yes > /tmp/up.log 2>&1 && say "update: ok" || { say "update FAILED"; tail -60 /tmp/up.log | tee -a $R; exit 1; }
hash -r 2>/dev/null; [ ! -e /usr/local/bin/material-grub ] && ! command -v material-grub >/dev/null 2>&1 && say "the old material-grub command is gone" || { say "the old command is still there"; ls -l /usr/local/bin | tee -a $R; exit 1; }
[ ! -e /usr/share/material-grub-gui ] && [ ! -e /usr/libexec/material-grub-gui-helper ] && [ ! -e /usr/share/applications/material-grub-gui.desktop ] && say "the old editor is gone" || { say "the old editor is still there"; exit 1; }
b=$(ls -d /var/backups/material-grub/upgrade-* 2>/dev/null | tail -n1)
[ -n "$b" ] && [ -f "$b/usr/local/bin/material-grub" ] && [ -d "$b/usr/share/material-grub-gui" ] && say "both were backed up first ($b)" || { say "no backup of the leftovers"; ls /var/backups/material-grub | tee -a $R; exit 1; }
for v in version; do material-boot $v | head -1 | grep -q "material-boot $(cat /bundle/VERSION)" && say "core is $(cat /bundle/VERSION)" || { say "wrong core version"; material-boot version | tee -a $R; exit 1; }; done
material-boot version | grep -q "^grub $(cat /bundle/VERSION)" && material-boot version | grep -q "^plymouth $(cat /bundle/VERSION)" && say "grub and plymouth are updated" || { say "parts not updated"; material-boot version | tee -a $R; exit 1; }
grep -q "^STYLE=list" /etc/material-grub.conf && grep -q "# my own line" /etc/material-grub.conf && say "settings kept (style, own line)" || { say "settings LOST"; cat /etc/material-grub.conf | tee -a $R; exit 1; }
material-boot core colour | grep -q "#7E57C2" && say "the seed colour kept" || { say "the seed colour LOST"; exit 1; }
grep -q '"Penguin"' /etc/material-grub/overrides.json && say "the per-entry overrides kept" || { say "overrides LOST"; exit 1; }
grep -q "classes applied" $CFG && say "grub.cfg annotated" || { say "grub.cfg NOT annotated"; exit 1; }
material-boot grub doctor > /tmp/d1.txt 2>&1 && say "material-boot grub doctor: ok" || { say "grub doctor FAILED"; cat /tmp/d1.txt | tee -a $R; exit 1; }
material-boot core doctor > /tmp/d2.txt 2>&1 && say "material-boot core doctor: ok" || { say "core doctor FAILED"; cat /tmp/d2.txt | tee -a $R; exit 1; }
grep -qi "old command" /tmp/d1.txt && { say "doctor still reports an old command"; cat /tmp/d1.txt | tee -a $R; exit 1; } || say "doctor reports no leftover"
[ -f /usr/share/plymouth/themes/material/material.script ] && $LISTER "$IMG" | grep -q "themes/material/material.script" && say "Plymouth is still applied and in the initramfs" || { say "Plymouth lost"; exit 1; }
python3 - <<'PY' && say "state record: core, grub, plymouth; no 'gui'" || { say "state record is wrong"; cat /var/lib/material-grub/state.json | tee -a /out/upgrade-bundle-smoke.txt; exit 1; }
import json
s = json.load(open("/var/lib/material-grub/state.json"))
assert set(s["parts"]) == {"core", "grub", "plymouth"}, s["parts"]
PY

say "== the commands that replaced the old one"
material-boot core conf STYLE=clean >/dev/null && grep -q "^STYLE=clean" /etc/material-grub.conf && say "material-boot core conf: ok" || { say "core conf FAILED"; exit 1; }
material-boot core colour forest >/dev/null && material-boot core colour | grep -qi "forest\|#" && say "material-boot core colour: ok" || { say "core colour FAILED"; exit 1; }
material-boot grub apply > /tmp/a1.log 2>&1 && say "material-boot grub apply: ok" || { say "grub apply FAILED"; tail -20 /tmp/a1.log | tee -a $R; exit 1; }
material-boot core apply > /tmp/a2.log 2>&1 && say "material-boot core apply (every part): ok" || { say "core apply FAILED"; tail -30 /tmp/a2.log | tee -a $R; exit 1; }
material-boot grub gui 2>&1 | grep -q "material-boot ui" && say "the old word 'gui' points to material-boot ui" || { say "no hint for gui"; exit 1; }
material-boot core apply --help | grep -q "^usage:" && say "material-boot core apply --help explains and does not apply" || { say "apply --help FAILED"; exit 1; }

say "== a kernel update does not need the old command"
# what runs after a kernel change: grub-mkconfig writes a plain grub.cfg, then the hook of the distribution's kernel package (deb: /etc/kernel/postinst.d, Arch: a pacman
# hook, both from the GRUB package; here its file is run by hand) calls `material-boot grub apply`; a systemd path unit does the same on a real machine
touch /boot/vmlinuz-9.9.9-test
$MK -o $CFG >/tmp/mk.log 2>&1 && say "grub-mkconfig after a new kernel: ok" || { say "grub-mkconfig FAILED"; tail -20 /tmp/mk.log | tee -a $R; exit 1; }
grep -q "classes applied" $CFG && say "(grub.cfg is annotated already: the path unit or a hook ran)" || say "grub.cfg is plain after grub-mkconfig, as expected without systemd"
HOOK=/b/parts/grub/packaging/debian/kernel-hook
if [ -f "$HOOK" ]; then
  sh "$HOOK" && say "the kernel hook ran" || { say "the kernel hook FAILED"; exit 1; }
else
  material-boot grub apply >/tmp/hook.log 2>&1 && say "material-boot grub apply (what the hooks run): ok" || { say "grub apply FAILED"; tail -20 /tmp/hook.log | tee -a $R; exit 1; }
fi
grep -q "classes applied" $CFG && say "grub.cfg annotated again after the kernel change" || { say "grub.cfg still plain after the kernel hook"; exit 1; }
material-boot grub doctor > /tmp/d3.txt 2>&1 && say "doctor after the kernel change: ok" || { say "doctor FAILED after the kernel change"; cat /tmp/d3.txt | tee -a $R; exit 1; }
rm -f /boot/vmlinuz-9.9.9-test

say "== running the update again changes nothing"
sh install.sh --yes > /tmp/up2.log 2>&1 && say "second run: ok" || { say "second run FAILED"; tail -30 /tmp/up2.log | tee -a $R; exit 1; }
grep -q "already installed at this version" /tmp/up2.log && say "every part says it is up to date" || { say "second run did not skip"; tail -30 /tmp/up2.log | tee -a $R; exit 1; }
grep -q "material-grub-gui\|usr/local/bin/material-grub" /tmp/up2.log && { say "second run talks about leftovers again"; grep -n "material-grub-gui\|usr/local/bin/material-grub" /tmp/up2.log | tee -a $R; exit 1; } || say "no leftover is mentioned again"

say "== the editor"
material-boot ui --help | grep -q "^usage: material-boot ui" && say "material-boot ui --help: ok" || { say "ui --help FAILED"; exit 1; }
python3 /src/tests/containers/ui_probe.py > /tmp/uiprobe.txt 2>&1 && say "the installed editor answers (state, previews in 4 styles, security checks)" || { say "EDITOR PROBE FAILED"; tail -25 /tmp/uiprobe.txt | tee -a $R; exit 1; }
sh install.sh --yes --with ui > /tmp/ui.log 2>&1 && say "install --with ui: ok" || { say "install --with ui FAILED"; tail -30 /tmp/ui.log | tee -a $R; exit 1; }
for f in /usr/libexec/material-boot-ui-helper /usr/share/polkit-1/actions/org.material-boot.ui.policy /usr/share/applications/material-boot.desktop; do [ -e "$f" ] || { say "editor file missing: $f"; exit 1; }; done
say "the launcher, helper and polkit policy are in place"
echo '{"verb":"nope"}' | /usr/libexec/material-boot-ui-helper | grep -q '"event": "error"' && say "the helper refuses an unknown request" || { say "helper did not refuse"; exit 1; }
sh install.sh --uninstall --only ui --yes > /tmp/uiu.log 2>&1 && [ ! -e /usr/libexec/material-boot-ui-helper ] && [ ! -e /usr/share/applications/material-boot.desktop ] && say "uninstall --only ui removes them" || { say "ui uninstall FAILED"; tail -20 /tmp/uiu.log | tee -a $R; exit 1; }

say "== removal"
sh install.sh --uninstall --only plymouth --yes > /tmp/u1.log 2>&1 && say "uninstall plymouth: ok" || { say "uninstall plymouth FAILED"; tail -30 /tmp/u1.log | tee -a $R; exit 1; }
sh install.sh --uninstall --only grub --yes > /tmp/u2.log 2>&1 && say "uninstall grub: ok" || { say "uninstall grub FAILED"; tail -30 /tmp/u2.log | tee -a $R; exit 1; }
material-boot version >/dev/null && say "the core stays and works" || { say "the core is broken"; exit 1; }
say "ALL OK"
