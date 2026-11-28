# sourced by the smoke scripts: a distro container with a fake /boot, GRUB's tools and a kernel with an initramfs. Needs $R and say() from the caller;
# sets ID, CFG, MK, PROBE, LISTER, IMG, kver, cfg0, img0 and snap().
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
