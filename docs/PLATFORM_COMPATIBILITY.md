# Platform compatibility matrix

✅ means tested on the named physical target; ⚠️ means implemented but hardware or
distribution validation is incomplete. Automated Windows/Ubuntu CI is not a physical
Cozmo or PrimTux test.

| Feature | PrimTux target | Ubuntu |
| --- | --- | --- |
| Application startup / Qt | ⚠️ not tested on target | ✅ automated Ubuntu CI |
| Simulator | ⚠️ not tested on target | ✅ automated Ubuntu CI |
| Ollama localhost provider | ⚠️ mocked HTTP only | ⚠️ mocked HTTP only |
| Push-to-talk microphone / Vosk | ⚠️ untested on target | ⚠️ untested with real audio |
| Direct Cozmo Wi-Fi | ⚠️ no physical test | ⚠️ no physical test |
| Cozmo camera / cubes / Freeplay | ⚠️ no physical test | ⚠️ no physical test |
| Autonomous floor movement | ⚠️ experimental | ⚠️ experimental |
| Table-edge driving | 🔒 disabled | 🔒 disabled |
| `.deb` installation | ⚠️ target base unknown | ✅ Ubuntu 24.04 CI only |
| Code Lab editor / browser | ⚠️ Linux browser fallback implemented; target retest pending | ⚠️ Linux CI tests passed; Code page retest pending |
| Code Lab simulator commands | ⚠️ target not tested | ⚠️ automated simulator test only |
| Scratch `.sb3` save/reopen | ⚠️ target not tested | ⚠️ Windows browser round-trip tested; Linux retest pending |

See [PrimTux inventory](PRIMTUX.md) and [physical validation](PHYSICAL_VALIDATION.md).
