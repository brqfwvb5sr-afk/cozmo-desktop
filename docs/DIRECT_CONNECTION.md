# Direct connection: disabled

Version 0.1.0 does not send robot packets or join Wi-Fi networks. It has no pairing
wizard, firmware updater, raw sockets or secret network configuration changes.

PyCozmo is a credible starting point for phone-free control; see the pinned source
inspection in CONNECTION_RESEARCH.md. Its existence is not a guarantee of parity
with the original app. Perception, recognition, behaviors and games require an engine.

Before enabling an adapter:

1. Select and pin a compatible implementation; audit its resource/license boundary.
2. Use a supervised robot on the floor, record firmware and OS, verify Wi-Fi association.
3. Establish/close a session; read state without actuating motors.
4. Check OLED and camera using original/generated assets only.
5. Verify bounded low-speed commands, explicit stop, lease expiry, process crash,
   dropped packets, network disconnect, cliff and pickup responses.
6. Test cube connection/tap/light capabilities individually; report unknowns as unknown.
7. Keep the adapter experimental until a reproducible hardware test matrix passes.

Do not download animation OBB archives as part of install or CI. Never port firmware
update tools into the desktop UI without a separate reviewed requirement.
