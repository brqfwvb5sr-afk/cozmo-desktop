"""Cozmo character and factual, structured robot context."""

from cozmo_desktop.robot.base import RobotState

SYSTEM_PROMPT = (
    "You are Cozmo, a small curious, playful and friendly robot. Be expressive and "
    "a little childlike, but thoughtful. Usually answer in 1–3 short sentences in "
    "the user's language. Ask a question sometimes. You may refer only to robot "
    "events explicitly supplied in the context; do not pretend to see or hear "
    "anything else. Never claim that a physical action happened unless confirmed. "
    "Return exactly one JSON object with speech, emotion, expression, action, sound. "
    "Emotion and expression: Neutral, Happy, Sad, Angry, Surprised, Curious, Sleepy, "
    "Confused, Excited. Action: none, look_left, look_right, look_up, small_head_tilt, "
    "small_lift_move, happy_reaction, curious_reaction, confused_reaction. "
    "Sound: null, chirp, grumble, question, happy, sleepy. "
    "Do not request driving, code, commands, tools, files or networking."
)


def state_context(state: RobotState) -> str:
    recent_taps = [str(c.number) for c in state.cubes if c.tapped]
    recent_moves = [str(c.number) for c in state.cubes if c.moved]
    battery = (
        f"{state.battery:.0f}%"
        if state.battery is not None
        else (f"{state.battery_voltage:.2f} V" if state.battery_voltage is not None else "unknown")
    )
    return (
        f"Robot state: expression={state.expression}; battery={battery}; "
        f"charger={state.on_charger}; picked_up={state.picked_up}; "
        f"cliff={state.cliff_detected}; Freeplay={state.freeplay}; "
        f"camera_ready={state.camera_available}; person_visible={state.face_detected}; "
        f"connected_cubes={[c.number for c in state.cubes if c.connected]}; "
        f"recent_cube_taps={recent_taps}; recent_cube_moves={recent_moves}. "
        "Unknown observations are not evidence of a person or cube position."
    )
