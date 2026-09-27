# Connection research

Inspected 2026-09-27, before implementation. **No physical robot or mobile device was
available.** Verified below means documentation/source verified, not hardware tested.

## Version 0.2.0 implementation update

The initial decisions below describe the simulator milestone. At the owner's
request, 0.2.0 adds an explicit experimental PyCozmo 0.8.0 adapter. No mobile assets
are used. Current behavior, limits and pending physical checks are documented in
[DIRECT_CONNECTION.md](DIRECT_CONNECTION.md). Fake transport tests are not evidence
of successful physical connection or firmware stopping behavior.

Additional source inspection: `client.py`, `anim_controller.py`, `audio.py`,
`robot.py`, `examples/cube_lights.py` at the PyCozmo revision above. `drive_wheels`
with `duration` sleeps on the host; it does not implement a firmware command lease.
Our worker therefore owns independent expiry and attempts STOP, with no delivery
guarantee on a broken link. `Enable` may trigger firmware motor calibration.

## Primary sources inspected

| Project | Immutable revision | Files examined |
| --- | --- | --- |
| [Cozmo.AI](https://github.com/c64-dev/Cozmo.AI/tree/c8646f0a84faabd1b7f8f195bed416cf20bdcf67) | c8646f0a84faabd1b7f8f195bed416cf20bdcf67 | LICENSE, README, main.py, voice_commands.py |
| [c64-dev SDK](https://github.com/c64-dev/cozmo-python-sdk/tree/d2a5f7f4b2e5613ed8b1b51e9d4d546300eedec7) | d2a5f7f4b2e5613ed8b1b51e9d4d546300eedec7 | LICENSE.txt, run.py, event.py |
| [Anki SDK](https://github.com/anki/cozmo-python-sdk/tree/dd29edef18748fcd816550469195323842a7872e) | dd29edef18748fcd816550469195323842a7872e | LICENSE.txt, setup.py, run.py |
| [PyCozmo](https://github.com/zayfod/pycozmo/tree/1b6dcd9b869a3784f1d8b02e820bb033f95fd13a) | 1b6dcd9b869a3784f1d8b02e820bb033f95fd13a | LICENSE.md, NOTICE, client.py, protocol.md, architecture.md, resource tool |
| [nexo-pycozmo](https://github.com/nexo-robot/nexo-pycozmo/tree/55206051567c9f3228faaf2fe6221b65a9babfb3) | 55206051567c9f3228faaf2fe6221b65a9babfb3 | README, pyproject.toml |

## Verified documentation facts

**Mode A: SDK bridge.** A computer SDK application talks to the engine inside the
official mobile app. The phone connects to Cozmo over Wi-Fi; the computer connects
to the phone via USB. The documented flow is: connect phone over USB, authorize
debugging (Android), connect the phone to Cozmo Wi-Fi, open the Cozmo app, enable
SDK mode, then start the desktop client. iOS uses usbmux rather than ADB.
Sources: Cozmo.AI README and Anki SDK `src/cozmo/run.py` at revisions above.

**Mode B: direct communication.** PyCozmo explicitly replaces the mobile engine
and implements UDP communication. Its documented Wi-Fi flow uses the robot's
displayed PSK; Wi-Fi association precedes its protocol session. Thus phone-free
control has a public implementation, but does not follow from installing the old SDK.
Source: [PyCozmo README](https://github.com/zayfod/pycozmo/blob/1b6dcd9b869a3784f1d8b02e820bb033f95fd13a/README.md).

## Findings from source code

### Bridge transport and compatibility

The SDK has Android, iOS and TCP connectors. `COZMO_PORT = 5106` is an engine-side
port. A TCP connector is **not** a raw robot Wi-Fi driver. `cozmoclad` encodes
engine messages, with an SDK-pinned version dependency. The c64 fork still contains
`asyncio.wait(..., loop=...)` in `event.py`; its presence is a compatibility risk
for modern Python, not proof that all paths fail. Do not import this SDK into the
Qt process until Python 3.11/3.12 compatibility has been tested. A separate legacy
worker process with a narrow local IPC contract is a fallback, not implemented here.

### Direct protocol and pairing

PyCozmo `docs/protocol.md` describes robot address `172.31.1.1`, UDP port `5551`,
sequence/ack frames, resets and periodic pings. Its documented connection setup
is a reset/connect exchange after Wi-Fi authentication. Packet contents depend
on firmware. This is reverse-engineered documentation, not a manufacturer guarantee.
No additional account-token pairing requirement was established by this inspection;
do not infer compatibility with every firmware or newer product called Cozmo.

### Camera, state, cubes and expressions

PyCozmo `client.py` assembles image chunks, decodes images using Pillow, emits
camera events, and updates pose, wheel speeds, head/lift, battery voltage and
status from `RobotState`. It tracks available/connected objects and exposes
head/lift, OLED, wheel and camera methods. Packet declarations include cube lights
and object connections. This does not establish complete cube games, battery
reporting, spatial reasoning or face recognition. Computer vision and behavioral
intelligence require engine/application work above this transport layer.

### Animations and resource restrictions

`load_anims()` checks external resources and loads clip metadata; procedural face
generation is separate. The resource download tool refers to an archived app OBB
and disables default TLS certificate verification. **We do not run that tool, ship
those resources, disable TLS, or treat their availability as permission to redistribute.**
First-milestone expressions, camera imagery and animation names are original
simulator content. They are not claims about available robot triggers.

### Cozmo.AI and newer forks

Cozmo.AI uses Google recognition via SpeechRecognition, synchronous SDK actions,
Freeplay switching, text command checks, a weather helper, photo/music/dance/song
commands and Selenium chatbot interaction. `bored_anim` exists; scheduling bored
events is also listed as a TODO. See COZMO_AI_INTEGRATION.md for modernization.

nexo-pycozmo is a relevant newer fork, but its inspected metadata requires Python
>=3.13, alongside newer numerical/image dependencies. It is not a drop-in choice
for this project's Python 3.11/3.12 target. We have not installed or hardware-tested it.

## Assumptions and design decisions

- Start with Python 3.11/3.12, PySide6 6.8, qasync and Pillow; do not install obsolete
  robot dependencies just to launch a simulator.
- An asynchronous backend contract will permit a future bridge or PyCozmo adapter.
- Prefer a minimal direct prototype without external animation assets for the first
  supervised hardware test; low-level transport feasibility is established by source.
- No phone is needed for simulation. Mode A requires the official phone app. Mode B
  aims to remove that dependency but is disabled in this application.

## Unresolved questions and verification gates

1. Which robot firmware, app version and phone OS are available to the user?
2. Can the c64 fork connect and complete/cancel actions on modern Python, or does
   it need fixes/isolation? Test disconnect and USB removal, not merely import.
3. Can a maintained direct library reproduce pairing/session establishment,
   telemetry, camera, bounded drive and stop on the user's hardware?
4. What are actual cliff/pickup/watchdog semantics across firmware? A desktop
   process cannot send STOP after power or network loss; robot-side expiry matters.
5. Which cube features and redistributable animation assets are available?
6. Does current Ubuntu networking keep Internet access on a second interface while
   associated with Cozmo? Do not silently alter routing or network configuration.

## Milestone outcome

Simulator is implemented independently. Both physical modes are deliberately
unavailable in the UI. Research shows direct control is technically plausible and
already implemented upstream, **not** that this project can yet connect directly.
