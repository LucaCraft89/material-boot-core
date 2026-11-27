#!/bin/sh
# The installer installs what it needs: a system with Python and NOTHING else (no Pillow, no SVG rasteriser) gets them from its own package manager.
#   usage: sh deps_smoke.sh      /bundle: the unpacked bundle   /src: this repository (read-only)   /out: receives deps-smoke.txt
# 1. Pillow is really absent before   2. `install.sh --only core --yes` succeeds and says it installed the dependencies   3. Pillow imports, an SVG rasteriser
# exists, the command works and the shared data is built   4. running it again installs nothing
set -e
R=/out/deps-smoke.txt; : > $R
say() { echo "$*" | tee -a $R; }
fail() { say "FAIL: $*"; exit 1; }
if [ -n "${MG_CA:-}" ]; then
  for d in /etc/pki/ca-trust/source/anchors /etc/ca-certificates/trust-source/anchors /usr/share/pki/trust/anchors /usr/local/share/ca-certificates; do
    [ -d "$d" ] && { cp "$MG_CA" "$d/mg-ca.crt"; break; }
  done
  update-ca-trust 2>/dev/null || update-ca-certificates >/dev/null 2>&1 || true
fi
. /etc/os-release
export DEBIAN_FRONTEND=noninteractive
case $ID in
  fedora) command -v python3 >/dev/null || dnf -y install -q python3 >/dev/null 2>&1 ;;
  debian|ubuntu) apt-get update -qq >/dev/null; apt-get install -y -qq --no-install-recommends python3 >/dev/null 2>&1 ;;
  arch) pacman -Sy --noconfirm --needed python >/dev/null 2>&1 ;;
  opensuse*) command -v python3 >/dev/null || zypper --non-interactive install --no-recommends python3 >/dev/null 2>&1 ;;
  *) fail "unknown distribution $ID" ;;
esac
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || fail "this image has no Python 3.9+"
if python3 -c 'import PIL' 2>/dev/null; then fail "Pillow is already there: the test starts from a system without it"; fi
say "1. Pillow is absent: ok"

out=$(sh /bundle/install.sh --only core --yes 2>&1) || { echo "$out" | tee -a $R; fail "the install failed"; }
echo "$out" | tee -a $R >/dev/null
echo "$out" | grep -q "installed the build dependencies" || fail "it did not say it installed the dependencies"
say "2. install --only core: ok, and it says what it installed"

python3 -c 'import PIL' || fail "Pillow still does not import"
command -v rsvg-convert >/dev/null || command -v magick >/dev/null || command -v convert >/dev/null || fail "no SVG rasteriser"
material-boot version >/dev/null 2>&1 || /usr/local/bin/material-boot version >/dev/null 2>&1 || fail "the command does not work"
[ -s /usr/share/material-boot/data/palettes.json ] || fail "the shared data was not built"
say "3. Pillow, the rasteriser, the command and the data: ok"

out=$(sh /bundle/install.sh --only core --yes 2>&1) || { echo "$out"; fail "the second run failed"; }
echo "$out" | grep -q "installed the build dependencies" && fail "the second run installed dependencies again"
say "4. a second run installs nothing: ok"
say "ALL OK"
