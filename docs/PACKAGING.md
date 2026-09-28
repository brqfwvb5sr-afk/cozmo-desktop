# PrimTux and Ubuntu packaging

PrimTux is the primary target, but the owner's variant, base libraries and CPU
architecture are not yet inspected. Do not install the Ubuntu 24.04 `.deb` on PrimTux
as if it were validated. Run the inventory in [PRIMTUX.md](PRIMTUX.md), then build
and test a package against that actual base. The existing project-owned SVG icon
and `cozmo-desktop.desktop` menu entry can be reused. Optional Vosk and Ollama
models are not bundled. No PrimTux package has been built or validated yet.

Source install targets Ubuntu 22.04 with Python 3.11 and Ubuntu 24.04 with Python
3.12. The initial `.deb` recipe targets **Ubuntu 24.04 amd64 only**, using its system
Python 3.12 and a private virtual environment. Ubuntu 26.04, ARM and AppImage are
not validated targets yet. PyCozmo and its Python dependencies are bundled; no mobile app assets are included.
The separate Ubuntu source setup script installs Python 3.12 with uv, allowing
installation on hosts with newer system Python without replacing it.

Build on Ubuntu 24.04:

```bash
sudo apt install python3-venv python3-pip python3-build
bash scripts/build-deb.sh
sudo apt install ./dist/cozmo-desktop_0.3.0_amd64.deb
cozmo-desktop
```

The build downloads Python wheels from PyPI. Installation through apt uses the
already-bundled runtime; there is no post-install network script. The launcher
explicitly invokes `/opt/cozmo-desktop/venv/bin/python` so it does not depend on
build-directory shebangs. Qt libraries remain dynamically linked and replaceable.
An original SVG icon and application menu entry are installed under `/usr/share`.

CI builds the package, installs it on Ubuntu 24.04, runs the application smoke test
both offscreen and with the X11/xcb plugin under Xvfb,
and uploads the `.deb`, Python source archive/wheel and dependency manifest. Download
the matching artifact from the repository's Actions page; this is a development
artifact, not a signed stable release. Keep a copy of the source archive with binaries.

`dist/runtime-dependencies.json` records actual bundled versions. Installed wheels
retain their license metadata. Before a public binary release, review all bundled
Qt components/transitive notices and provide the complete corresponding source
required by their licenses (including upstream library sources and build information),
not only this application's source. See THIRD_PARTY.md for upstream source locations.
The packaging job is a technical install check, not a substitute for that release review.

Uninstall using `sudo apt remove cozmo-desktop`. User settings and snapshots remain
in their normal user directories; package scripts do not remove them.
