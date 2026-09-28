# PrimTux: primary target, exact machine not yet inspected

The owner's actual PrimTux PC has not been accessible to this development session.
**Do not infer its version or compatibility from the distribution name.** PrimTux
publishes different bases: its [PrimTux8 technical page](https://documentation.primtux.fr/books/manuel-de-ladministrateur/page/caracteristiques-techniques)
describes Linux Mint 21.3 / Ubuntu 22.04 and Xfce; its
[PrimTux9 contributor page](https://primtux.fr/participer-au-projet/) mentions both
Linux Mint 22.3 and Debian-based builds. These are upstream examples, not observations
of the owner's machine.

Run this **read-only** inventory on the target PC and record the output before claiming
support:

```bash
cd ~/cozmo-desktop
bash scripts/primtux-info.sh
```

| Required fact | Actual target observation | How checked |
| --- | --- | --- |
| PrimTux version | Unknown | `/etc/os-release`; PrimTux-specific release file if present |
| CPU architecture | Unknown | `uname -m` |
| Underlying distribution | Unknown | `/etc/os-release` ID and ID_LIKE |
| Kernel | Unknown | `uname -r` |
| Python version | Unknown | `python3 --version` |
| Desktop environment | Unknown | `XDG_CURRENT_DESKTOP` |
| Qt compatibility | Unverified | launch and offscreen/X11 smoke test on target |
| NetworkManager | Unknown | `nmcli` and device types |
| PulseAudio/PipeWire | Unknown | `pactl info` |
| Microphone support | Unverified | `arecord`, then supervised push-to-talk recording |
| USB support | Unknown | `lsusb` availability and actual adapter recognition |
| USB Wi-Fi support | Unverified | Wi-Fi device in `nmcli`, route to Cozmo |
| Package manager | Unknown | `apt-get` presence; inspect OS before package choice |
| Ollama compatibility | Unverified | architecture, `ollama --version`, localhost `/api/tags`, model inference |

The inventory avoids SSIDs, IPs, USB serial numbers and audio recordings. It prints
network **types and states** only. The system's exact hardware, Qt plugin behavior,
speaker and microphone fidelity still require a supervised run.

## Source installation on a compatible Linux host

While connected to the Internet, run `bash scripts/setup-primtux.sh`. It checks the
platform, creates a project-local Python 3.12 environment and installs dependencies.
It does not replace system Python, install Ollama, or change network settings. The
current installer supports x86_64 and aarch64 as candidate architectures, but
aarch64 wheel availability has not been verified on PrimTux. For local microphone
recognition, run `bash scripts/setup-primtux.sh --with-voice` and download Vosk models;
see [OLLAMA.md](OLLAMA.md). Start with `bash scripts/start-primtux.sh`.

PrimTux-specific `.deb` packaging is **pending inspection** of the actual base and
target architecture. The Ubuntu 24.04 `.deb` must not be assumed compatible.
