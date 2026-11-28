# The RPM ships the library, the command and the build inputs; the shared data (palettes, glyphs, the font) is built on the target machine in %posttrans,
# for the configured scheme (material-boot core install --from-package --only core), so nothing prebuilt is downloaded. COPR builds this spec from the tag.
Name:           material-boot-core
Version:        1.1.1
Release:        1%{?dist}
Summary:        The code and the command that Material GRUB and Material Plymouth share
License:        MIT
URL:            https://github.com/LucaCraft89/material-boot-core
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3
Requires:       python3-pillow
Requires:       librsvg2-tools
Recommends:     polkit
Obsoletes:      material-grub-gui

%description
The shared code of the Material boot parts (palettes, the scene renderer, the conf and overrides formats, presets, the state record and the
migrations), the shared data built from the distro catalog, and the `material-boot` command that the parts plug into. It installs no theme by itself:
Material GRUB and Material Plymouth are separate packages that require it.

%prep
%autosetup -n %{name}-%{version}

%install
sh packaging/common/install-tree.sh . %{buildroot}

%posttrans
/usr/bin/material-boot core install --from-package --only core --yes || :

%preun
if [ $1 -eq 0 ]; then /usr/bin/material-boot core install --from-package --uninstall --only core --yes || :; fi

%files
%license LICENSE
%doc README.md
%{_bindir}/material-boot
%dir %{_datadir}/material-boot
%{_datadir}/material-boot/lib
%{_datadir}/material-boot/scripts
%{_datadir}/material-boot/assets
%dir %{_datadir}/material-boot/plugins.d
%{_libexecdir}/material-boot-ui-helper
%{_mandir}/man1/material-boot.1*
%{_datadir}/polkit-1/actions/org.material-boot.ui.policy
%{_datadir}/applications/material-boot.desktop

%changelog
* Sat Nov 28 2026 LucaCraft89 <noreply@users.noreply.github.com> - 1.1.1-1
- Fix: a part named in the state record that nobody provides (the 0.7.x graphical editor) no longer crashes the installer; the screen lists what is installed and where to customise further.

* Fri Nov 27 2026 LucaCraft89 <noreply@users.noreply.github.com> - 1.1.0-1
- The installer screen: parts checklist, the shared look with a preview, each part's questions (install.questions).

* Fri Nov 27 2026 LucaCraft89 <noreply@users.noreply.github.com> - 1.0.1-1
- install.sh uses the distribution's python3; the installer installs the build dependencies it needs.

* Wed Nov 25 2026 LucaCraft89 <noreply@users.noreply.github.com> - 1.0.0-1
- Release 1.0.0.
