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

## Supervised idle-life sequence (owner, on the real Cozmo)

Automated evidence so far: fake-transport worker tests and simulator/Qt tests only.
Run these steps in order; stop at the first failure and report what the Home page
shows. Keep one hand near Cozmo. No step drives near a table edge.

1. **Connect, eyes, sound (Cozmo on the charger or held still, motors locked).**
   Connect Cozmo. Within ~5 s the Home page should read *Idle life is running* and
   *Last face sent … s ago*. Watch 30 s: blinks every 3–7 s, eyes glancing sideways,
   at least one short sound within ~20 s.
   Report: what the OLED did, whether a sound was audible, and the two Home lines
   (*Idle life …* and *Last face sent … · last sound sent … · …*), especially whether
   it says *Cozmo confirms playback (N audio frames)* and whether N rises.
2. **Resume after a manual action.** Open *Expressions*, choose one, return to Home.
   About 2 s later idle life should say *running* again. Report the Home lines.
3. **Head and lift (Cozmo on a clear floor, not on the charger).** *Connection →
   Clear floor → Enable motors*. Move head and lift slightly with the sliders. Then wait
   30 s: small head glances every 7–12 s. Report whether they happen and whether a
   sound cut any head move short.
4. **Slow wheels (floor only, supervised).** On *Control*, keep the speed at 20 mm/s,
   hold W for 1 s and release. Then try 40 mm/s. Report the observed motion, whether
   motors stayed enabled after release, and any *last refused* text.
5. **Only after 1–4 pass:** tick *Let Cozmo roam on a clear floor* in the middle of a
   free floor area, watch one minute and press STOP once. Report stop behavior.

Useful extra evidence: *Settings → Export diagnostics* (contains only the listed safe
fields: idle-life status, face/sound counts and ages, stream status, Cozmo's audio
frame counter, last refused command) and the `robot_command_rejected`,
`personality_output_refused` and `ambient_failed` lines from `app.log`.
