"""PyCozmo adapter, isolated in a worker. No copied code or mobile app assets.

API evidence: PyCozmo 0.8.0 client.py, robot.py, audio.py, examples/cube_lights.py.
"""

import io
import math
import threading
import time
import wave
from typing import Any

from PIL import Image

from cozmo_desktop.robot.base import CubeState, RobotError, RobotState


class PyCozmoTransport:
    def __init__(self) -> None:
        import pycozmo

        self.api = pycozmo
        self.client = pycozmo.Client(enable_animations=False, enable_procedural_face=False)
        self.lock = threading.Lock()
        self.ready = False
        self.last_state = 0.0
        self.last_camera = 0.0
        self.hazard = False
        self.image: Image.Image | None = None
        self._state = RobotState(battery=None, backend_name="direct", motors_enabled=False)
        self._taps: dict[int, float] = {}
        self._moved: dict[int, float] = {}
        self.started = False

    def start(self) -> None:
        api, cli = self.api, self.client
        cli.add_handler(api.event.EvtRobotReady, self._ready)
        cli.add_handler(api.event.EvtRobotStateUpdated, self._on_state)
        cli.add_handler(api.event.EvtNewRawCameraImage, self._on_camera)
        cli.add_handler(api.protocol_encoder.ObjectTapped, self._on_tap)
        cli.add_handler(api.protocol_encoder.ObjectMoved, self._on_move)
        cli.start()
        self.started = True
        cli.connect()

    def _ready(self, cli: Any) -> None:
        cli.conn.send(self.api.protocol_encoder.EnableStopOnCliff(enable=True))
        cli.stop_all_motors()
        cli.enable_animations(True)
        cli.enable_camera(True, color=False)
        self.ready = True

    def _on_camera(self, cli: Any, image: Image.Image) -> None:
        with self.lock:
            self.image = image.copy()
            self.last_camera = time.monotonic()

    def _on_tap(self, cli: Any, packet: Any) -> None:
        self._taps[packet.object_id] = time.monotonic()

    def _on_move(self, cli: Any, packet: Any) -> None:
        self._moved[packet.object_id] = time.monotonic()

    def _on_state(self, cli: Any) -> None:
        flags = self.api.robot.RobotStatusFlag
        now = time.monotonic()
        hazard = bool(
            cli.robot_status
            & (flags.IS_PICKED_UP | flags.IS_FALLING | flags.CLIFF_DETECTED | flags.IS_ON_CHARGER)
        )
        cubes = []
        objects = dict(cli.connected_objects)
        for number in range(1, 4):
            object_id = next(
                (key for key, value in objects.items() if int(value["object_type"]) == number), -1
            )
            cubes.append(
                CubeState(
                    number,
                    connected=object_id != -1,
                    tapped=now - self._taps.get(object_id, -10.0) < 1,
                    moved=now - self._moved.get(object_id, -10.0) < 1,
                )
            )
        state = RobotState(
            connected=self.ready,
            battery=None,
            battery_voltage=float(cli.battery_voltage),
            backend_name="direct",
            motors_enabled=False,
            charging=bool(cli.robot_status & flags.IS_CHARGING),
            head_angle=math.degrees(cli.head_angle.radians),
            lift_height=cli.lift_position.ratio,
            left_speed=cli.left_wheel_speed.mmps,
            right_speed=cli.right_wheel_speed.mmps,
            x=cli.pose.position.x,
            y=cli.pose.position.y,
            heading=cli.pose.rotation.angle_z.radians,
            camera_available=now - self.last_camera < 2,
            cubes=tuple(cubes),
        )
        with self.lock:
            self._state = state
            self.last_state = now
            self.hazard = hazard

    def snapshot(self) -> RobotState:
        with self.lock:
            return self._state

    def camera_jpeg(self) -> bytes | None:
        with self.lock:
            frame = self.image.copy() if self.image is not None else None
        if frame is None:
            return None
        output = io.BytesIO()
        frame.convert("RGB").save(output, format="JPEG", quality=75)
        return output.getvalue()

    def stop(self) -> None:
        if self.started:
            self.client.cancel_anim()
            self.client.stop_all_motors()

    def drive(self, left: float, right: float) -> None:
        # Upstream duration= is a host sleep, NOT firmware-side command expiry.
        self.client.drive_wheels(left, right, lwheel_acc=100, rwheel_acc=100)

    def head(self, degrees: float) -> None:
        self.client.set_head_angle(math.radians(degrees), accel=2, max_speed=1)

    def lift(self, ratio: float) -> None:
        self.client.set_lift_height(32 + 60 * ratio, accel=2, max_speed=1)

    def face(self, pixels: bytes) -> None:
        image = Image.frombytes("L", (128, 64), pixels)
        image = image.resize((128, 32)).point(lambda value: 255 if value >= 100 else 0).convert("1")
        self.client.display_image(image)

    def audio(self, wav_bytes: bytes) -> None:
        packets = []
        with wave.open(io.BytesIO(wav_bytes), "rb") as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (
                1,
                2,
                22050,
            ):
                raise RobotError("Speech audio must be 22050 Hz mono 16-bit PCM.")
            while chunk := stream.readframes(744):
                samples = self.api.audio.bytes_to_cozmo(chunk, 1, 1)
                packets.append(self.api.protocol_encoder.OutputAudio(samples=samples))
                if len(packets) > 900:
                    raise RobotError("Speech is limited to 30 seconds.")
        self.client.anim_controller.play_audio(packets)

    def cube_lights(self, number: int) -> None:
        cli, api = self.client, self.api
        object_id = next(
            (
                key
                for key, value in dict(cli.connected_objects).items()
                if int(value["object_type"]) == number
            ),
            None,
        )
        if object_id is None:
            factory_id = next(
                (
                    key
                    for key, obj in dict(cli.available_objects).items()
                    if int(obj.object_type.value) == number
                ),
                None,
            )
            if factory_id is None:
                raise RobotError("Cube not detected. Wake the cube and bring it close to Cozmo.")
            cli.conn.send(api.protocol_encoder.ObjectConnect(factory_id=factory_id, connect=True))
            return
        cli.conn.send(api.protocol_encoder.CubeId(object_id=object_id))
        light = api.lights.green_light
        cli.conn.send(api.protocol_encoder.CubeLights(states=(light, light, light, light)))

    def close(self) -> None:
        if not self.started:
            self.client.conn.sock.close()
            return
        self.stop()
        self.client.enable_animations(False)
        self.client.enable_camera(False)
        time.sleep(0.1)  # Allow queued STOP to be sent before disconnect; no ACK guarantee.
        self.client.disconnect()
        time.sleep(0.1)
        self.client.stop()
