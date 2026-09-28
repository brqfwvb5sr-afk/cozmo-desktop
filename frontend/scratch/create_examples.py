"""Create original, standard Scratch 3 projects for Code Lab lessons."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "examples/scratch"
BACKDROP = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">'
    b'<rect width="480" height="360" fill="#f7fafb"/></svg>'
)
SPRITE = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
    b'<circle cx="32" cy="32" r="25" fill="#087f8c"/>'
    b'<circle cx="24" cy="27" r="3" fill="white"/>'
    b'<circle cx="40" cy="27" r="3" fill="white"/></svg>'
)


def asset(data: bytes, name: str) -> dict[str, object]:
    digest = hashlib.md5(data).hexdigest()  # Scratch asset ID convention, not a security hash.
    return {
        "name": name,
        "assetId": digest,
        "md5ext": f"{digest}.svg",
        "dataFormat": "svg",
        "rotationCenterX": 32 if name == "Robot" else 240,
        "rotationCenterY": 32 if name == "Robot" else 180,
    }


def project() -> dict[str, object]:
    stage = {
        "isStage": True,
        "name": "Stage",
        "variables": {},
        "lists": {},
        "broadcasts": {},
        "blocks": {},
        "comments": {},
        "currentCostume": 0,
        "costumes": [asset(BACKDROP, "Classroom")],
        "sounds": [],
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None,
    }
    sprite = {
        "isStage": False,
        "name": "Robot",
        "variables": {},
        "lists": {},
        "broadcasts": {},
        "blocks": {},
        "comments": {},
        "currentCostume": 0,
        "costumes": [asset(SPRITE, "Robot")],
        "sounds": [],
        "volume": 100,
        "layerOrder": 1,
        "visible": True,
        "x": 0,
        "y": 0,
        "size": 100,
        "direction": 90,
        "draggable": False,
        "rotationStyle": "all around",
    }
    return {
        "targets": [stage, sprite],
        "monitors": [],
        "extensions": ["cozmo"],
        "meta": {"semver": "3.0.0", "vm": "15.1.2", "agent": "Cozmo Code Lab"},
    }


class Script:
    def __init__(self, blocks: dict[str, object], x: int = 80, y: int = 80) -> None:
        self.blocks = blocks
        self.x, self.y = x, y
        self.count = 0

    def add(
        self,
        opcode: str,
        inputs: dict[str, object] | None = None,
        fields: dict[str, object] | None = None,
        parent: str | None = None,
        top: bool = False,
        chain: bool = True,
    ) -> str:
        self.count += 1
        identifier = f"code_lab_{self.count:03d}"
        item: dict[str, object] = {
            "opcode": opcode,
            "next": None,
            "parent": parent,
            "inputs": inputs or {},
            "fields": fields or {},
            "shadow": False,
            "topLevel": top,
        }
        if top:
            item["x"], item["y"] = self.x, self.y
        self.blocks[identifier] = item
        if chain and parent and self.blocks[parent]["next"] is None:
            self.blocks[parent]["next"] = identifier
        return identifier


def text(value: str) -> list[object]:
    return [1, [10, value]]


def number(value: int) -> list[object]:
    return [1, [4, str(value)]]


def put(name: str, build) -> None:
    data = project()
    if name == "mood-machine":
        data["targets"][1]["variables"] = {"mood": ["mood", "happy"]}
    script = Script(data["targets"][1]["blocks"])
    build(script)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT / f"{name}.sb3", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(data, ensure_ascii=False))
        for payload in (BACKDROP, SPRITE):
            archive.writestr(f"{hashlib.md5(payload).hexdigest()}.svg", payload)


def hello(s: Script) -> None:
    hat = s.add("event_whenflagclicked", top=True)
    say = s.add("cozmo_say", {"TEXT": text("Hello, friend!")}, parent=hat)
    face = s.add("cozmo_expression", {"EXPRESSION": text("Happy")}, parent=say)
    s.add("cozmo_lift", {"PERCENT": number(50)}, parent=face)


def square(s: Script) -> None:
    hat = s.add("event_whenflagclicked", top=True)
    loop = s.add("control_repeat", {"TIMES": number(4)}, parent=hat)
    move = s.add("cozmo_move", {"DISTANCE": number(20)}, parent=loop, chain=False)
    s.blocks[loop]["inputs"]["SUBSTACK"] = [2, move]
    s.add("cozmo_turn", {"DEGREES": number(90)}, parent=move)


def cube_reaction(s: Script) -> None:
    hat = s.add("cozmo_whenCubeTapped", fields={"CUBE": ["1", None]}, top=True)
    say = s.add("cozmo_say", {"TEXT": text("Hey! You found my cube!")}, parent=hat)
    s.add("cozmo_expression", {"EXPRESSION": text("Surprised")}, parent=say)


def traffic_light(s: Script) -> None:
    current = s.add("event_whenflagclicked", top=True)
    for color in ("red", "green", "blue", "off"):
        current = s.add(
            "cozmo_cubeColor", {"CUBE": number(1), "COLOR": text(color)}, parent=current
        )
        if color != "off":
            current = s.add("control_wait", {"DURATION": number(1)}, parent=current)


def mood_machine(s: Script) -> None:
    hat = s.add("event_whenflagclicked", top=True)
    set_mood = s.add(
        "data_setvariableto",
        {"VALUE": text("happy")},
        fields={"VARIABLE": ["mood", "mood"]},
        parent=hat,
    )
    branch = s.add("control_if", parent=set_mood)
    condition = s.add(
        "operator_equals",
        {"OPERAND1": [1, [12, "mood", "mood"]], "OPERAND2": text("happy")},
        parent=branch,
        chain=False,
    )
    s.blocks[branch]["inputs"]["CONDITION"] = [2, condition]
    face = s.add("cozmo_expression", {"EXPRESSION": text("Happy")}, parent=branch, chain=False)
    s.blocks[branch]["inputs"]["SUBSTACK"] = [2, face]


def ai_conversation(s: Script) -> None:
    hat = s.add("event_whenflagclicked", top=True)
    s.add("cozmo_aiSay", {"QUESTION": text("Say hello in one short sentence.")}, parent=hat)


def safe_explorer(s: Script) -> None:
    hat = s.add("event_whenflagclicked", top=True)
    loop = s.add("control_repeat_until", parent=hat)
    sensor = s.add("cozmo_cliff", parent=loop, chain=False)
    s.blocks[loop]["inputs"]["CONDITION"] = [2, sensor]
    move = s.add("cozmo_move", {"DISTANCE": number(2)}, parent=loop, chain=False)
    s.blocks[loop]["inputs"]["SUBSTACK"] = [2, move]
    s.add("cozmo_stop", parent=loop)


def main() -> None:
    for name, builder in (
        ("hello-cozmo", hello),
        ("square-drive", square),
        ("cube-reaction", cube_reaction),
        ("traffic-light", traffic_light),
        ("mood-machine", mood_machine),
        ("ai-conversation", ai_conversation),
        ("safe-explorer", safe_explorer),
    ):
        put(name, builder)
    print(f"Created seven Scratch projects in {OUTPUT}")


if __name__ == "__main__":
    main()
