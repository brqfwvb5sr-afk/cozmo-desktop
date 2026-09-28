# Code Lab architecture

The editor is a production build of [Scratch Foundation's `scratch-editor`](https://github.com/scratchfoundation/scratch-editor) at the commit pinned in `frontend/scratch/upstream.json`. `frontend/scratch/apply_overlay.py` copies the Cozmo extension into the Scratch VM and changes only a few upstream integration points. The compiled `gui.js`, worker, chunks and static assets are shipped in the Python package. Normal use needs no Node.js or Internet.

```
Qt Code page + persistent STOP
  -> system browser on Linux (embedded QtWebEngine on Windows)
  -> upstream Scratch GUI and VM + Cozmo extension
  -> same-origin JSON HTTP on 127.0.0.1 with random session token
  -> ScratchCommands (allowlist, bounds, one active command)
  -> existing RobotController (STOP, manual priority, Freeplay cancellation)
  -> existing simulator or direct backend (drive lease and hardware safety)
```

The server binds an ephemeral port on `127.0.0.1`, requires an exact loopback Host and same Origin, and requires an `X-Code-Token` on every API request. The token is passed only to the local editor URL for that launch; it is not saved in `.sb3`. API input is capped at 16 KiB. Only `GET /api/state`, `POST /api/command` and `POST /api/emergency-stop` exist. Every robot command is validated before reaching the existing backend; the emergency endpoint latches the existing desktop STOP. No Scratch code can send raw wheel speeds, robot packets, shell commands or a safety-disable command. The Content Security Policy blocks cross-origin connections by the bundled editor; Scratch's runtime requires inline/eval script allowances.

On Linux, opening Code starts the server and opens the same editor URL in the
system browser. This avoids a native QtWebEngine process failure observed by a
PrimTux user. The desktop process stays available for its STOP button; a second
project-owned emergency button is fixed above the browser editor and uses the
token-protected local emergency endpoint. The editor's ordinary Scratch stop icon
only stops scripts; it is not the emergency latch. If no default browser opens,
Code shows a retry button and a clear error. Embedded QtWebEngine can be opted into
on Linux with `COZMO_CODE_EMBEDDED=1` for supervised compatibility testing, but is
not the default until the target machine has been validated.

`POST /api/command` accepts `{"command":"head","arguments":{"angle":20}}`; it returns `{"status":"ok","result":null}` or `{"status":"error","error":"..."}`. Supported commands and ranges are in [SCRATCH_EXTENSION.md](SCRATCH_EXTENSION.md). The browser polls `GET /api/state` every 250 ms for connection, safety and cube events. This is a local structured state snapshot, never camera frames.

Robot movement needs a connected robot, armed motors and `surface_mode=floor`. Each short command renews the existing expiring drive lease at 100 ms intervals; the backend stops wheels independently on stale commands. Cliff, pickup, falling, charger, disconnect and STOP are checked during movement. Any exception or cancellation stops the backend. STOP cancels all in-flight Scratch tasks; manual controller submissions cancel Scratch and schedule a stop before proceeding. An active game or Freeplay run yields when a Scratch command starts. Neither automatically resumes afterward in this version.

Scratch's native project upload/download uses standard `.sb3` projects. The extension ID and opcodes are stored as standard VM blocks. Cozmo's control token and hardware state are never stored in a project. Upstream fonts, sprites, costume/sound libraries and worker scripts are included locally; external services are not needed for the basic editor. AI blocks call the existing validated Ollama conversation service only when used.

Known boundaries: the exact PrimTux machine, QtWebEngine performance, physical motion calibration, real cube timing, real Cozmo speech and offline operation on target hardware remain untested. Cube **connection** is available; cube **visual detection** is not exposed by the current backend and is therefore not claimed.
