import json
from dataclasses import dataclass

from PIL import Image, ImageDraw

from cozmo_desktop.robot.base import RobotError
from cozmo_desktop.services.controller import RobotController

NAMES = (
    "Neutral",
    "Happy",
    "Sad",
    "Angry",
    "Surprised",
    "Curious",
    "Confused",
    "Sleepy",
    "Excited",
)


@dataclass(frozen=True)
class Expression:
    name: str
    head_angle: float = 10
    lift: float = 0

    @classmethod
    def from_json(cls, text: str) -> "Expression":
        data = json.loads(text)
        if not isinstance(data, dict) or set(data) - {"name", "head_angle", "lift"}:
            raise ValueError("Unsupported expression fields.")
        if data.get("name") not in NAMES:
            raise ValueError("Unknown expression.")
        head, lift = data.get("head_angle", 10), data.get("lift", 0)
        if type(head) not in (float, int) or not -25 <= head <= 44.5:
            raise ValueError("Invalid head angle.")
        if type(lift) not in (float, int) or not 0 <= lift <= 1:
            raise ValueError("Invalid lift position.")
        return cls(data["name"], head, lift)


def render_face(name: str) -> Image.Image:
    if name not in NAMES:
        raise RobotError("Unknown expression.")
    image = Image.new("RGB", (128, 64), "#10252d")
    draw = ImageDraw.Draw(image)
    for x in (22, 76):
        height = 8 if name == "Sleepy" else 26
        y = 20 if name != "Curious" or x == 22 else 12
        if name == "Happy":
            draw.arc((x, 18, x + 28, 49), 180, 350, fill="#5ceac6", width=7)
        elif name in ("Surprised", "Excited"):
            draw.ellipse((x, 12, x + 28, 49), fill="#5ceac6")
        else:
            draw.rounded_rectangle((x, y, x + 28, y + height), radius=6, fill="#5ceac6")
        if name == "Angry":
            draw.polygon([(x, 12), (x + 28, 24), (x + 28, 12)], fill="#10252d")
        if name == "Sad":
            draw.polygon([(x, 12), (x, 30), (x + 28, 12)], fill="#10252d")
        if name == "Confused" and x == 76:
            draw.rectangle((x, 20, x + 28, 32), fill="#10252d")
    return image


async def apply_expression(controller: RobotController, expression: Expression) -> None:
    if controller.latched:
        return
    frame = render_face(expression.name)
    await controller.backend.display_face(frame, expression.name)
    await controller.backend.set_head_angle(expression.head_angle)
    await controller.backend.set_lift_height(expression.lift)
