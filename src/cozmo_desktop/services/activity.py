"""Plain-language face/sound output diagnostics for the Home page; no Qt here."""

from cozmo_desktop.robot.base import OutputActivity, RobotState

# A refusal older than this is history, not an explanation for what happens now.
RECENT_REFUSAL = 60.0


def ago(moment: float | None, now: float) -> str:
    if moment is None:
        return "not yet"
    seconds = max(0.0, now - moment)
    return f"{seconds:.0f} s ago" if seconds < 120 else f"{seconds / 60:.0f} min ago"


def describe_output(
    output: OutputActivity, state: RobotState, now: float, *, simulation: bool
) -> str:
    """Say what really left the desktop and what Cozmo confirmed, without jargon."""
    if not state.connected:
        return "Face and sound output: not connected."
    parts = [
        f"Last face sent {ago(output.last_face, now)}",
        f"last sound sent {ago(output.last_sound, now)}",
    ]
    if simulation:
        parts.append("simulator only, nothing reaches a robot")
    elif output.stream_running is False:
        parts.append("face/sound stream to Cozmo is NOT running; reconnect")
    elif output.robot_audio_frames is None:
        parts.append("no playback confirmation from Cozmo yet")
    else:
        parts.append(f"Cozmo confirms playback ({output.robot_audio_frames} audio frames)")
    if not state.motors_enabled or state.surface_mode != "floor":
        parts.append("head moves need Clear floor + Enable motors")
    if (
        output.rejected
        and output.last_rejected is not None
        and now - output.last_rejected < RECENT_REFUSAL
    ):
        parts.append(f"last refused {ago(output.last_rejected, now)}: {output.rejected}")
    return " · ".join(parts) + "."
