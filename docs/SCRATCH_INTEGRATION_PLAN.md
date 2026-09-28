# Cozmo Code Lab: Scratch integration plan

Research date: 2026-09-28. This is an implementation record, not a claim of physical validation.

## Upstream and legal inventory

The current upstream is [Scratch Foundation's `scratch-editor` monorepo](https://github.com/scratchfoundation/scratch-editor), not the archived standalone `scratch-gui` and `scratch-vm` repositories. The reviewed `develop` commit is `ec153a14c78cf95df60f333975bbde8d4f031531` (root package version 15.1.2). Its npm workspaces include `@scratch/scratch-gui`, `@scratch/scratch-vm`, `@scratch/scratch-paint`, `@scratch/scratch-render`, `@scratch/scratch-storage`, `@scratch/scratch-svg-renderer`, `@scratch/scratch-media-lib-scripts`, and `@scratch/task-herder`. The reviewed package manifests identify version 15.1.2 and `AGPL-3.0-only` for each of these. The resolved `scratch-blocks` package is version 2.1.19, licensed Apache-2.0 according to its installed manifest and LICENSE file.

Sources: [monorepo README](https://github.com/scratchfoundation/scratch-editor/blob/develop/README.md), [root package manifest](https://github.com/scratchfoundation/scratch-editor/blob/develop/package.json), [GUI manifest](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-gui/package.json), [VM manifest](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/package.json), [AGPL license](https://github.com/scratchfoundation/scratch-editor/blob/develop/LICENSE), [trademark notice](https://github.com/scratchfoundation/scratch-editor/blob/develop/TRADEMARK).

The Scratch Foundation's trademark notice says its name, logo and character graphics may not be used to endorse or promote derived products without prior written permission. The product is named **Cozmo Code Lab**, is unofficial, and must not use upstream logos or character graphics for product branding. An attribution such as “Built with open-source Scratch editor technology; not affiliated with the Scratch Foundation” is descriptive, not an endorsement. Distribution must include the upstream license, notices, exact source/patch provenance and complete corresponding source for any AGPL-covered modified editor. This plan does not assume that the GPL license of the Python application relicenses Scratch code.

## Architecture

Build the real upstream editor from its pinned monorepo commit using `npm ci`; keep local extension and small integration changes as a separate overlay. Node/npm are build dependencies, not end-user runtime dependencies. A production frontend bundle is served by the Python application from loopback only. On Linux it opens in the system browser because the original embedded QtWebEngine path was reported to close Cozmo Desktop on PrimTux; Windows keeps the embedded view. The existing application header retains its STOP control, and the browser editor has a separate emergency STOP. QtWebEngine can be opted into on Linux for supervised compatibility testing, but is not required for normal Code Lab use.

The Scratch VM extension is registered in the upstream extension manager and made available in the extension library. It uses browser `fetch` to the same-origin local API. No block speaks the Cozmo protocol. Messages use a fixed command allowlist, bounded values, a per-session capability token, and JSON-only responses. The Python bridge calls the existing `RobotController` and backend; it never instantiates a second direct backend. The bridge binds `127.0.0.1` and rejects foreign Origin and Host headers. The token is generated per launch and not stored in `.sb3` projects. Scratch project JSON persists the extension ID/opcodes; at reload the editor must load the local extension before execution.

Control priority remains safety, emergency STOP, manual commands, Scratch, Freeplay and idle. Scratch commands require explicit motor arming on physical hardware and floor mode for movement. STOP latches synchronously, cancels in-flight Scratch operations and backend motion. The extension handles API failures without crashing the editor. Freeplay yields before Scratch robot commands and resumes only under an explicit setting. Ollama is used only on demand via the existing conversation service; it cannot supply arbitrary commands.

Scratch GUI already supports `.sb3` upload and download via its project file controls. The integration must preserve that native format and test save/reopen. All editor assets, translations and source maps required at runtime must resolve locally. The default Scratch storage configuration, extension library cards, example projects and asset libraries require an offline audit before the bundle is marked offline-ready. In particular, external extension entries, cloud storage, telemetry and upstream character assets must not silently create network dependencies or imply Scratch affiliation.

In the Windows development check, the production editor loaded from the local
Code Lab server in headless Chrome; seven original `.sb3` lessons opened, and an
exported lesson preserved its Cozmo extension blocks. The Hello Cozmo green-flag
script spoke, displayed a happy face and raised the simulator lift. Browser
request logging observed no external requests in this tested path. This does not
establish full offline coverage of every upstream extension, costume or sound
library, and Linux/PrimTux embedding remains untested.

## Build and release gates

1. Build the pinned upstream GUI unmodified and verify it renders locally.
2. Apply only tracked Cozmo overlay files/patches; verify upstream source and lockfile hashes.
3. Build a production bundle, test offline with all external network disabled, and exercise native `.sb3` save/reopen.
4. Test the local bridge against malformed input, origin/host attacks, STOP, cliff, pickup, watchdog and disconnected state using the simulator.
5. Package the bundle with attribution, source provenance and all required third-party notices; verify on a real PrimTux installation and Ubuntu.

No physical robot, PrimTux hardware, final package, or offline editor is considered validated solely from Windows/CI tests.
