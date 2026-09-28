# Physical validation ledger

No supervised test on the owner's PrimTux computer or a real Cozmo has been recorded.
Automated mocks and Ubuntu CI do not satisfy this ledger.

| Check | Result | Evidence needed |
| --- | --- | --- |
| PrimTux system inventory | Pending | `bash scripts/primtux-info.sh` output |
| Qt/desktop launch | Pending | actual target launch and menu entry |
| USB Wi-Fi route to Cozmo | Pending | `nmcli device status`, route, direct preflight |
| PyCozmo session/status | Pending | supervised connect and live telemetry |
| Camera, OLED, cubes, TTS | Pending | supervised functional checks |
| STOP, cliff, pickup, watchdog | Pending | cautious physical timing/behavior evidence |
| Floor Freeplay | Pending | clear floor, supervision and stop behavior |
| Table-edge safety | Locked | raw sensor and stopping-distance study; never infer safe driving |
| Ollama without Internet | Pending | installed local model while only Cozmo Wi-Fi is active |
| Microphone German/English | Pending | real device audio with local Vosk models |

Do not enable table driving on the basis of simulated sensor values or this document.
