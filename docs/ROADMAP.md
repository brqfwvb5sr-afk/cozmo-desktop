# Roadmap and scope

## Implemented first milestone

- Native dark Qt shell with Home, Control, Expressions, Animations, Camera,
  Connection information, Settings and diagnostic export.
- Asynchronous simulator contract, conservative speed cap, drive lease, cancellation,
  latched stop, keyboard/mouse control, synthetic camera and robot state.
- Original expressions, simulated speech events, synthetic animations, favorites and
  one saved sequence. Camera snapshot destination is configurable.
- Unit/Qt tests, Linux CI, wheel/source build, Ubuntu 24.04 package recipe.

## Next: hardware bridge

Prove c64 SDK compatibility with modern Python, add a real adapter, ADB discovery,
connection wizard states, disconnection tests and capability discovery. Record
hardware results. Do not substitute the simulator on a hardware connection failure.

## Experience and intelligence

Add real animation enumeration, cube controls, face tracking, activities and a
separate personality engine. Introduce optional STT and API/local AI services,
conversation state and a deterministic voice-command router. Keep weather/music
optional. No docking/return-to-charger claim without an implemented capability.

## Direct connection and distribution

Evaluate PyCozmo adapters, source/resource licenses and Python compatibility; verify
protocol/session/motor safety with hardware before enabling. Add more Ubuntu versions,
ARM, AppImage, reproducible dependency locking and signed releases after validation.
